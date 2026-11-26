"""Shared, explicit cleaning rules for the NPA participant-level source."""
from __future__ import annotations

import hashlib
import json
import re
from collections import Counter

import pandas as pd

SIX_CITIES = ["臺北市", "新北市", "桃園市", "臺中市", "臺南市", "高雄市"]
REGIONS = SIX_CITIES + ["基隆市", "新竹市", "新竹縣", "苗栗縣", "彰化縣", "南投縣", "雲林縣", "嘉義市", "嘉義縣", "屏東縣", "宜蘭縣", "花蓮縣", "臺東縣", "澎湖縣", "金門縣", "連江縣"]
REGION_PATTERN = r"^(" + "|".join(REGIONS) + r")"
RAW_COLUMNS = ["發生年度", "發生月份", "發生日期", "發生時間", "事故類別名稱", "處理單位名稱警局層", "發生地點", "經度", "緯度", "當事者順位", "死亡受傷人數", "當事者事故發生時年齡", "當事者區分-類別-大類別名稱-車種", "當事者區分-類別-子類別名稱-車種", "當事者屬-性-別名稱", "當事者行動狀態大類別名稱", "當事者行動狀態子類別名稱", "肇因研判大類別名稱-主要", "肇因研判子類別名稱-主要"]
AGE_REASONS = {"valid": "可用年齡", "non_person": "非人紀錄", "unidentified_person": "肇逃尚未查獲", "missing": "未填年齡", "not_numeric": "無法解析", "negative": "負值代碼", "not_integer": "非整數", "over_120": "超出專案檢查範圍"}


def text(series: pd.Series) -> pd.Series:
    return series.fillna("").astype(str).str.strip()


def regions(frame: pd.DataFrame) -> tuple[pd.Series, pd.Series, pd.Series]:
    place = text(frame["發生地點"]).str.replace("台", "臺", regex=False)
    police = text(frame["處理單位名稱警局層"]).str.replace("台", "臺", regex=False)
    location_region = place.str.extract(REGION_PATTERN, expand=False)
    police_region = police.str.extract(REGION_PATTERN, expand=False)
    return location_region.fillna(police_region), location_region, police_region


def clean_age(age_raw: pd.Series, sex_raw: pd.Series) -> pd.DataFrame:
    """Preserve source values; zero is retained for identified people."""
    raw, sex = text(age_raw), text(sex_raw)
    value = pd.to_numeric(raw, errors="coerce")
    reason = pd.Series("valid", index=raw.index, dtype="object")
    reason.loc[value.gt(120)] = "over_120"
    reason.loc[value.notna() & value.mod(1).ne(0)] = "not_integer"
    reason.loc[value.lt(0)] = "negative"
    reason.loc[value.isna()] = "not_numeric"
    reason.loc[raw.eq("")] = "missing"
    reason.loc[sex.eq("肇事逃逸尚未查獲")] = "unidentified_person"
    non_person = sex.isin(["無或物(動物、堆置物)", "無人駕駛自動車"])
    reason.loc[non_person] = "non_person"
    valid = reason.eq("valid")
    return pd.DataFrame({"age_raw": raw, "age": value.where(valid).astype("Int16"), "age_valid": valid, "age_invalid_reason": reason, "age_review_required": valid & (value.eq(0) | value.ge(100)), "is_person": ~non_person}, index=raw.index)


def vehicle_types(frame: pd.DataFrame, is_person: pd.Series) -> pd.Series:
    major = text(frame["當事者區分-類別-大類別名稱-車種"])
    minor = text(frame["當事者區分-類別-子類別名稱-車種"])
    result = major.replace({"小客車(含客、貨兩用)": "小客車", "": "未知／未填"})
    people = major.eq("人")
    result.loc[people] = minor.loc[people].replace({"": "其他人"})
    # Preserve an unmanned vehicle's actual type for accident-involvement
    # filtering; exclude non-person records through is_person in age analysis.
    result.loc[~is_person & major.eq("")] = "非人紀錄"
    return result


def _case_hash(values: tuple[str, ...]) -> str:
    payload = json.dumps(values, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()[:32]


def build_tables(source: pd.DataFrame, source_file: str, expected_year: int):
    """Build both levels from one complete source file in its original order.

    A source ordinal reset splits otherwise identical location/time keys. This
    is permitted only after the complete file passes shared-field checks.
    IDs are derived identifiers, never official case numbers.
    """
    frame = source.copy().reset_index(drop=True)
    if frame.empty:
        raise ValueError("No selected records")
    for column in RAW_COLUMNS:
        if column not in frame:
            raise ValueError(f"Missing required source column: {column}")
        frame[column] = text(frame[column])
    frame["source_file"] = source_file
    if "source_record" not in frame:
        frame["source_record"] = range(1, len(frame) + 1)
    frame["source_record"] = pd.to_numeric(frame["source_record"], errors="raise").astype("int32")
    region, region_location, region_police = regions(frame)
    frame["city"] = region
    if not region.isin(SIX_CITIES).all():
        raise ValueError("build_tables expects six-city source records")
    frame["city_method"] = region_location.notna().map({True: "location", False: "police_fallback"})
    frame["city_conflict"] = region_location.notna() & region_police.notna() & region_location.ne(region_police)
    frame["year"] = pd.to_numeric(frame["發生年度"], errors="raise").astype("int16")
    if not frame["year"].eq(expected_year).all():
        raise ValueError("Source year does not match the requested year")
    frame["accident_type"] = frame["事故類別名稱"]
    if not frame["accident_type"].isin(["A1", "A2"]).all():
        raise ValueError("Unknown accident category")

    rank = pd.to_numeric(frame["當事者順位"], errors="coerce")
    if rank.isna().any() or rank.lt(1).any() or rank.mod(1).ne(0).any():
        raise ValueError("Invalid participant ordinal requires source review")
    frame["participant_order"] = rank.astype("int16")
    key_fields = ["發生日期", "發生時間", "事故類別名稱", "處理單位名稱警局層", "發生地點", "經度", "緯度"]
    # Hash distinct tuples once, not every participant row.
    keys = frame[key_fields].apply(tuple, axis=1)
    key_codes, unique_keys = pd.factorize(keys, sort=False)
    hashes = {i: _case_hash(key) for i, key in enumerate(unique_keys)}
    if len(set(hashes.values())) != len(hashes):
        raise ValueError("Generated identifier hash collision")
    frame["_base"] = pd.Series(key_codes, index=frame.index)
    frame["_instance"] = rank.eq(1).groupby(frame["_base"]).cumsum().astype("int16")
    if frame["_instance"].eq(0).any():
        raise ValueError("A candidate case starts without ordinal 1; review before counting")
    frame["accident_id"] = [f"{expected_year}-{hashes[base]}-{instance}" for base, instance in zip(frame["_base"], frame["_instance"])]

    casualties = frame["死亡受傷人數"].str.extract(r"^死亡\s*(?P<deaths>\d+)\s*[;；]\s*受傷\s*(?P<injuries>\d+)\s*$")
    if casualties.isna().any().any():
        raise ValueError("Unparseable casualty text; no zero imputation is allowed")
    frame[["deaths", "injuries"]] = casualties.astype("int16")
    frame["main_cause"] = frame["肇因研判大類別名稱-主要"].replace("", "未知／未填")
    frame["main_cause_detail"] = frame["肇因研判子類別名稱-主要"].replace("", "未知／未填")
    shared = ["year", "city", "accident_type", "死亡受傷人數", "main_cause", "main_cause_detail"]
    conflict = frame.groupby("accident_id", sort=False)[shared].nunique(dropna=False).gt(1).any(axis=1)
    if conflict.any():
        raise ValueError(f"{int(conflict.sum())} cases have conflicting shared fields; output was stopped")
    starts = rank.eq(1).groupby(frame["accident_id"]).sum()
    if not starts.eq(1).all():
        raise ValueError("Case boundary validation failed")

    date = pd.to_datetime(frame["發生日期"], format="%Y%m%d", errors="coerce", exact=True)
    date = date.where(date.dt.year.eq(expected_year))
    clock_text = frame["發生時間"].str.zfill(6)
    clock = pd.to_datetime(clock_text, format="%H%M%S", errors="coerce", exact=True)
    frame["date"] = date
    frame["datetime"] = pd.to_datetime(frame["發生日期"] + clock_text, format="%Y%m%d%H%M%S", errors="coerce", exact=True).where(date.notna())
    frame["date_valid"] = date.notna()
    frame["time_valid"] = clock.notna()
    frame["datetime_valid"] = frame["datetime"].notna()
    frame["month"] = date.dt.month.astype("Int8")
    frame["weekday"] = date.dt.dayofweek.astype("Int8")
    frame["hour"] = clock.dt.hour.astype("Int8")
    frame["location_raw"] = frame["發生地點"]
    frame["location"] = frame["發生地點"].str.replace("台", "臺", regex=False).str.replace(r"\s+", " ", regex=True).str.replace(r"\s*/\s*", " / ", regex=True).str.strip()
    frame["longitude"] = pd.to_numeric(frame["經度"], errors="coerce")
    frame["latitude"] = pd.to_numeric(frame["緯度"], errors="coerce")
    # Broad Taiwan-area sanity check, not a municipal-boundary classifier.
    frame["coordinate_valid"] = frame["longitude"].between(118, 124) & frame["latitude"].between(20, 27)
    frame["longitude_raw"], frame["latitude_raw"] = frame["經度"], frame["緯度"]
    frame["date_raw"], frame["time_raw"] = frame["發生日期"], frame["發生時間"]
    frame["police_unit"] = frame["處理單位名稱警局層"]

    age = clean_age(frame["當事者事故發生時年齡"], frame["當事者屬-性-別名稱"])
    frame = pd.concat([frame, age], axis=1)
    frame["vehicle_type"] = vehicle_types(frame, frame["is_person"])
    frame["vehicle_type_raw"] = frame["當事者區分-類別-大類別名稱-車種"]
    frame["vehicle_subtype_raw"] = frame["當事者區分-類別-子類別名稱-車種"]
    frame["sex_raw"] = frame["當事者屬-性-別名稱"]
    frame["action_type_raw"] = frame["當事者行動狀態大類別名稱"]
    frame["action_detail_raw"] = frame["當事者行動狀態子類別名稱"]
    repeated = frame.duplicated(["accident_id", "participant_order"], keep=False)
    frame["ordinal_repeated"] = repeated
    sequence = frame.groupby("accident_id", sort=False).cumcount() + 1
    frame["participant_id"] = frame["accident_id"] + "-p" + sequence.astype(str)

    accident_columns = ["accident_id", "year", "city", "accident_type", "deaths", "injuries", "date", "datetime", "month", "weekday", "hour", "date_valid", "time_valid", "datetime_valid", "location", "location_raw", "longitude", "latitude", "coordinate_valid", "longitude_raw", "latitude_raw", "date_raw", "time_raw", "police_unit", "city_method", "city_conflict", "main_cause", "main_cause_detail", "source_file", "source_record"]
    accidents = frame.loc[rank.eq(1), accident_columns].copy()
    sizes = frame.groupby("accident_id", sort=False).size()
    accidents["participant_records"] = accidents["accident_id"].map(sizes).astype("int16")
    accidents["person_records"] = accidents["accident_id"].map(frame.groupby("accident_id")["is_person"].sum()).astype("int16")
    split_counts = frame.groupby("_base")["_instance"].max()
    split_bases = split_counts[split_counts.gt(1)].index
    accidents["same_key_multiple_cases"] = frame.loc[rank.eq(1), "_base"].isin(split_bases).to_numpy()
    participant_columns = ["participant_id", "accident_id", "participant_order", "vehicle_type", "vehicle_type_raw", "vehicle_subtype_raw", "age_raw", "age", "age_valid", "age_invalid_reason", "age_review_required", "is_person", "sex_raw", "action_type_raw", "action_detail_raw", "ordinal_repeated", "source_file", "source_record"]
    participants = frame[participant_columns].copy()
    audit = {"file": source_file, "selected_rows": len(frame), "accidents": len(accidents), "source_rank_one": int(rank.eq(1).sum()), "base_keys": len(unique_keys), "same_key_split_groups": len(split_bases), "ordinal_repeated_rows": int(repeated.sum()), "shared_conflicts": 0, "city_conflicts": int(frame["city_conflict"].sum()), "date_invalid_cases": int((~accidents["date_valid"]).sum()), "time_invalid_cases": int((~accidents["time_valid"]).sum()), "coordinate_invalid_cases": int((~accidents["coordinate_valid"]).sum()), "age_reasons": dict(Counter(participants["age_invalid_reason"])), "split_case_ids": accidents.loc[accidents["same_key_multiple_cases"], "accident_id"].tolist(), "ordinal_repeated_case_ids": participants.loc[repeated, "accident_id"].unique().tolist()}
    return accidents.reset_index(drop=True), participants.reset_index(drop=True), audit
