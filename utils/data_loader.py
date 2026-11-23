from pathlib import Path
import pandas as pd
import streamlit as st

DATA_DIR = Path("data/processed")
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


@st.cache_data
def load_data() -> tuple[pd.DataFrame, pd.DataFrame, bool]:
    """讀取事故表與當事者表；第三個回傳值代表是否為模擬樣本。"""
    if ACCIDENTS_PATH.exists() and PARTICIPANTS_PATH.exists():
        accidents = pd.read_parquet(ACCIDENTS_PATH)
        participants = pd.read_parquet(PARTICIPANTS_PATH)
        return accidents, participants, False

    accidents, participants = _make_sample_data()
    return accidents, participants, True