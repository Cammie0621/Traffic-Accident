from pathlib import Path
import json
import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data" / "processed"
ACCIDENTS_PATH = DATA_DIR / "accidents.parquet"
PARTICIPANTS_PATH = DATA_DIR / "participants.parquet"


def _make_sample_data() -> tuple[pd.DataFrame, pd.DataFrame]:
    """A 尚未提供正式資料前使用的 2021-2025 暫時小樣本。"""
    acc_cols = [
        "accident_id", "year", "city",
        "accident_type", "deaths", "injuries",
    ]
    acc_rows = [
        ("A001", 2021, "臺北市", "A2", 0, 2),
        ("A002", 2021, "新北市", "A1", 1, 1),
        ("A003", 2021, "桃園市", "A2", 0, 1),
        ("A004", 2022, "新北市", "A2", 0, 2),
        ("A005", 2022, "臺中市", "A1", 1, 0),
        ("A006", 2022, "高雄市", "A2", 0, 1),
        ("A007", 2023, "臺北市", "A2", 0, 1),
        ("A008", 2023, "臺中市", "A2", 0, 2),
        ("A009", 2023, "臺南市", "A2", 0, 1),
        ("A010", 2024, "桃園市", "A2", 0, 3),
        ("A011", 2024, "臺中市", "A2", 0, 1),
        ("A012", 2024, "高雄市", "A1", 1, 2),
        ("A013", 2025, "新北市", "A2", 0, 1),
        ("A014", 2025, "臺南市", "A1", 1, 1),
        ("A015", 2025, "高雄市", "A2", 0, 1),
    ]
    accidents = pd.DataFrame(acc_rows, columns=acc_cols)

    part_cols = ["accident_id", "vehicle_type", "age"]
    part_rows = [
        ("A001", "機車", 24),
        ("A001", "小客車", 45),
        ("A002", "機車", 68),
        ("A003", "小客車", 33),
        ("A004", "機車", 31),
        ("A005", "大貨車", 41),
        ("A006", "機車", 27),
        ("A007", "行人", 73),
        ("A008", "機車", 22),
        ("A009", "機車", 29),
        ("A010", "小客車", 52),
        ("A011", "機車", 19),
        ("A012", "機車", 35),
        ("A013", "小客車", 48),
        ("A014", "大貨車", 55),
        ("A015", "機車", 26),
    ]
    participants = pd.DataFrame(part_rows, columns=part_cols)
    return accidents, participants


def _signature(paths):
    return tuple((str(path), path.stat().st_mtime_ns, path.stat().st_size) for path in paths if path.exists())


def _source_directory():
    for directory, mode in [(DATA_DIR, "processed"), (ROOT / "data" / "samples", "sample")]:
        paths = [directory / "accidents.parquet", directory / "participants.parquet"]
        if any(path.exists() for path in paths):
            if not all(path.exists() for path in paths):
                raise ValueError(f"事故表與當事者表必須一起提供：{directory}")
            return directory, mode
    return None, "mock"


@st.cache_data(max_entries=2, show_spinner="讀取整理後資料…")
def _load_cached(directory: str, mode: str, signature: tuple):
    folder = Path(directory)
    accidents = pd.read_parquet(folder / "accidents.parquet")
    participants = pd.read_parquet(folder / "participants.parquet")
    required_acc = {"accident_id", "year", "city", "accident_type", "deaths", "injuries"}
    required_part = {"accident_id", "vehicle_type", "age"}
    if not required_acc.issubset(accidents) or not required_part.issubset(participants):
        raise ValueError("資料缺少網站必要欄位，請依資料字典重新執行前處理。")
    if not accidents["accident_id"].is_unique:
        raise ValueError("事故表 ID 不唯一，已停止載入以避免重複計案。")
    if not participants["accident_id"].isin(accidents["accident_id"]).all():
        raise ValueError("當事者表含無法對應事故的紀錄。")
    metadata_path = folder / "metadata.json"
    metadata = json.loads(metadata_path.read_text(encoding="utf-8")) if metadata_path.exists() else {}
    metadata["source_mode"] = mode
    accidents.attrs["metadata"] = metadata
    participants.attrs["metadata"] = metadata
    return accidents, participants, mode != "processed"


def load_data() -> tuple[pd.DataFrame, pd.DataFrame, bool]:
    """Full processed tables, then a real development sample, then the old mock.

    Cache keys include both file timestamps/sizes, so adding or rebuilding data
    switches away from the previous sample without a manual cache clear.
    """
    directory, mode = _source_directory()
    if directory is None:
        accidents, participants = _make_sample_data()
        metadata = {"source_mode":"mock", "is_sample":True, "years":sorted(accidents["year"].unique().tolist())}
        accidents.attrs["metadata"] = metadata
        participants.attrs["metadata"] = metadata
        return accidents, participants, True
    paths = [directory / name for name in ("accidents.parquet", "participants.parquet", "metadata.json")]
    return _load_cached(str(directory), mode, _signature(paths))
