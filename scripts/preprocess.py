"""Reproducible annual NPA preprocessing. Python 3.11 or newer required."""
from __future__ import annotations

import argparse
import calendar
import hashlib
import io
import json
import re
import sys
import time
import zipfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from utils.cleaning import AGE_REASONS, RAW_COLUMNS, SIX_CITIES, build_tables, regions

SOURCE_PAGES = {2021:158865, 2022:161199, 2023:167905, 2024:172969, 2025:177136}
VERSION = "2025-a-v1"


def dump_json(path, data):
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)


def write_tables(directory, accidents, participants, metadata, quality=None):
    directory.mkdir(parents=True, exist_ok=True)
    for name, frame in [("accidents", accidents), ("participants", participants)]:
        temp = directory / (name + ".parquet.tmp")
        frame.to_parquet(temp, engine="pyarrow", compression="zstd", index=False)
    for name in ("accidents", "participants"):
        (directory / (name + ".parquet.tmp")).replace(directory / (name + ".parquet"))
    dump_json(directory / "metadata.json", metadata)
    if quality is not None:
        dump_json(directory / "data_quality.json", quality)


def compact(frame):
    for col in frame.select_dtypes(include="object").columns:
        if frame[col].nunique(dropna=False) < 200:
            frame[col] = frame[col].astype("category")
        else:
            frame[col] = frame[col].astype("string[pyarrow]")
    return frame


def find_archive(raw_dir, year):
    candidates = [p for p in raw_dir.glob("*.zip") if str(year) in p.name or f"{year-1911}年" in p.name]
    if len(candidates) != 1:
        raise ValueError(f"Expected one {year} ZIP in {raw_dir}; found {len(candidates)}. Download the annual ZIP from data.gov.tw.")
    return candidates[0]


def run(args):
    started = time.perf_counter()
    accidents_parts, participant_parts, manifests, audits, coverage = [], [], [], [], []
    totals = Counter()
    for year in sorted(set(args.years)):
        archive_path = find_archive(args.raw_dir, year)
        with archive_path.open("rb") as source_file:
            digest = hashlib.file_digest(source_file, "sha256").hexdigest()
        month_dates = {month:set() for month in range(1,13)}
        a1_file_present, a2_months = False, set()
        year_manifest = {"year":year, "archive":archive_path.name, "sha256":digest, "source_page":f"https://data.gov.tw/dataset/{SOURCE_PAGES[year]}", "members":[]}
        with zipfile.ZipFile(archive_path, metadata_encoding="cp950") as archive:
            for member in archive.infolist():
                if not member.filename.lower().endswith(".csv") or not any(kind in member.filename for kind in ("A1", "A2")):
                    continue
                a1_file_present |= "A1" in member.filename
                month_match = re.search(r"A2.*_(\d{1,2})\.csv$", member.filename, re.IGNORECASE)
                if month_match and 1 <= int(month_match.group(1)) <= 12:
                    a2_months.add(int(month_match.group(1)))
                selected_parts = []
                counts = Counter()
                offset = 0
                with archive.open(member) as raw:
                    reader = pd.read_csv(raw, encoding="utf-8-sig", dtype=str, usecols=RAW_COLUMNS, keep_default_na=False, chunksize=args.chunk_size)
                    for chunk in reader:
                        chunk["source_record"] = range(offset+1, offset+len(chunk)+1)
                        offset += len(chunk)
                        counts["csv_rows"] += len(chunk)
                        row_year = chunk["發生年度"].str.strip()
                        footers = row_year.str.startswith(("資料提供日期", "事故類別"))
                        counts["footer_rows"] += int(footers.sum())
                        valid = row_year.eq(str(year))
                        if (~(valid | footers)).any():
                            raise ValueError(f"Unexpected source-year or malformed row in {member.filename}")
                        chunk = chunk.loc[valid].copy()
                        counts["source_records"] += len(chunk)
                        dates = pd.to_datetime(chunk["發生日期"], format="%Y%m%d", errors="coerce")
                        if "A2" in member.filename:
                            a2_months.update(int(month) for month in dates.dt.month.dropna().unique())
                        for month in dates.dt.month.dropna().unique():
                            month_dates[int(month)].update(dates[dates.dt.month.eq(month)].dt.strftime("%Y-%m-%d").dropna())
                        region, _, _ = regions(chunk)
                        counts["region_unresolved_rows"] += int(region.isna().sum())
                        mask = region.isin(SIX_CITIES)
                        counts["other_region_rows"] += int((region.notna() & ~mask).sum())
                        selected_parts.append(chunk.loc[mask].copy())
                selected = pd.concat(selected_parts, ignore_index=True)
                totals.update(counts)
                if selected.empty:
                    year_manifest["members"].append({"name":member.filename, "uncompressed_bytes":member.file_size, **dict(counts), "selected_records":0, "accidents":0})
                    continue
                source_name = f"{year}/{member.filename}"
                acc, part, audit = build_tables(selected, source_name, year)
                accidents_parts.append(acc)
                participant_parts.append(part)
                audits.append(audit)
                year_manifest["members"].append({"name":member.filename, "uncompressed_bytes":member.file_size, **dict(counts), "selected_records":len(part), "accidents":len(acc)})
                print(f"{source_name}: {len(acc):,} cases; {len(part):,} source party records", flush=True)
        manifests.append(year_manifest)
        for month, observed in month_dates.items():
            days = calendar.monthrange(year, month)[1]
            covered = a1_file_present and month in a2_months
            coverage.append({"year":year, "month":month, "period_start":f"{year}-{month:02d}-01", "period_end":f"{year}-{month:02d}-{days:02d}", "calendar_days":days, "covered_calendar_days":days if covered else 0, "observed_source_dates":len(observed), "source_month_present":covered, "a1_annual_file_present":a1_file_present, "a2_month_file_present":month in a2_months, "calendar_basis":"annual A1 file and A2 monthly source period, not city accident dates"})

    if not accidents_parts:
        raise ValueError("No six-city records in the requested source files")
    accidents = pd.concat(accidents_parts, ignore_index=True)
    participants = pd.concat(participant_parts, ignore_index=True)
    if not accidents["accident_id"].is_unique or not participants["participant_id"].is_unique:
        raise ValueError("Duplicate IDs across source files")
    if not participants["accident_id"].isin(accidents["accident_id"]).all():
        raise ValueError("Orphan participant records")
    if len(participants) != int(accidents["participant_records"].sum()):
        raise ValueError("Participant record reconciliation failed")
    if len(accidents) != sum(a["source_rank_one"] for a in audits):
        raise ValueError("Case/source ordinal reconciliation failed")
    metadata = {"pipeline_version":VERSION, "generated_at_utc":datetime.now(timezone.utc).isoformat(), "is_sample":False, "years":sorted(set(args.years)), "cities":SIX_CITIES, "accident_count":len(accidents), "participant_records":len(participants), "person_records":int(participants["is_person"].sum()), "non_person_records":int((~participants["is_person"]).sum()), "valid_age_records":int(participants["age_valid"].sum()), "deaths":int(accidents["deaths"].sum()), "injuries":int(accidents["injuries"].sum()), "date_start":str(accidents["date"].min().date()), "date_end":str(accidents["date"].max().date()), "coverage":coverage, "sources":manifests, "case_id_method":"derived composite key plus validated source ordinal reset; not official case ID", "age_rule":"identified person, integer 0..120; raw retained; zero and age>=100 flagged for review; unidentified hit-and-run excluded from age analysis"}
    quality = {"pipeline_version":VERSION, "source_totals":dict(totals), "age_reason_counts":{str(k):int(v) for k,v in participants["age_invalid_reason"].value_counts().items()}, "age_reason_labels":AGE_REASONS, "age_review_records":int(participants["age_review_required"].sum()), "same_key_split_groups":sum(a["same_key_split_groups"] for a in audits), "ordinal_repeated_rows":int(participants["ordinal_repeated"].sum()), "invalid_coordinate_cases":int((~accidents["coordinate_valid"]).sum()), "invalid_date_cases":int((~accidents["date_valid"]).sum()), "invalid_time_cases":int((~accidents["time_valid"]).sum()), "per_source":audits, "checks":{"unique_accident_id":True,"unique_participant_id":True,"all_participants_linked":True,"source_records_reconciled":True,"case_boundaries_shared_fields_consistent":True,"casualties_counted_once_per_case":True}}
    accidents = compact(accidents)
    participants = compact(participants)
    write_tables(args.output_dir, accidents, participants, metadata, quality)
    pd.DataFrame(coverage).to_parquet(args.output_dir / "coverage.parquet", engine="pyarrow", compression="zstd", index=False)
    sample_acc = accidents.sort_values("accident_id").groupby(["year","city","accident_type"], observed=True, sort=False).head(args.sample_per_group).copy()
    sample_part = participants[participants["accident_id"].isin(sample_acc["accident_id"])].copy()
    sample_meta = dict(metadata, is_sample=True, accident_count=len(sample_acc), participant_records=len(sample_part), person_records=int(sample_part["is_person"].sum()), non_person_records=int((~sample_part["is_person"]).sum()), valid_age_records=int(sample_part["age_valid"].sum()), deaths=int(sample_acc["deaths"].sum()), injuries=int(sample_acc["injuries"].sum()), sample_method=f"deterministic hash-order {args.sample_per_group} cases per year/city/type; all linked party rows retained", parent_accident_count=len(accidents), scope_note="Development sample only; source coverage calendar describes the full source, not sample completeness")
    write_tables(args.sample_dir, sample_acc, sample_part, sample_meta)
    metadata["processing_seconds"] = round(time.perf_counter()-started,2)
    metadata["output_bytes"] = {p.name:p.stat().st_size for p in args.output_dir.glob("*.parquet")}
    dump_json(args.output_dir / "metadata.json", metadata)
    print(json.dumps({k:metadata[k] for k in ["years","accident_count","participant_records","person_records","non_person_records","valid_age_records","deaths","injuries","processing_seconds","output_bytes"]}, ensure_ascii=False, indent=2))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--years", nargs="+", type=int, choices=sorted(SOURCE_PAGES), default=[2025])
    parser.add_argument("--raw-dir", type=Path, default=ROOT/"data"/"raw")
    parser.add_argument("--output-dir", type=Path, default=ROOT/"data"/"processed")
    parser.add_argument("--sample-dir", type=Path, default=ROOT/"data"/"samples")
    parser.add_argument("--chunk-size", type=int, default=25000)
    parser.add_argument("--sample-per-group", type=int, default=30)
    args=parser.parse_args()
    if args.chunk_size < 1 or args.sample_per_group < 1:
        parser.error("chunk sizes and sample counts must be positive")
    run(args)


if __name__ == "__main__":
    main()
