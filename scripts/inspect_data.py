from pathlib import Path
from zipfile import ZipFile
import pandas as pd

# 依腳本位置取得專案根目錄，讓不同電腦與執行目錄都使用相同資料位置。
ROOT = Path(__file__).resolve().parents[1]
zip_path = ROOT / "data" / "raw" / "114年傷亡道路交通事故資料.zip"

# 直接讀取壓縮檔內的 A1 CSV
with ZipFile(zip_path, metadata_encoding="cp950") as archive:
    csv_name = next(
        name for name in archive.namelist()
        if "A1" in name and name.endswith(".csv")
    )

    with archive.open(csv_name) as file:
        df = pd.read_csv(
            file,
            encoding="utf-8-sig",
            dtype=str,
            nrows=10,
        )

columns = [
    "發生日期",
    "發生時間",
    "發生地點",
    "當事者順位",
    "當事者事故發生時年齡",
]

print(df[columns].to_string(index=False))
# 小樣本先用地點開頭辨識城市
city_pattern = r"^(臺北市|新北市|桃園市|臺中市|臺南市|高雄市)"

df["city"] = df["發生地點"].str.strip().str.extract(
    city_pattern, expand=False
)
sample = df.loc[df["city"].notna()].copy()

# 保留原始年齡，另外建立分析用的數值欄位
sample["age_raw"] = sample["當事者事故發生時年齡"]
age_numeric = pd.to_numeric(sample["age_raw"], errors="coerce")
sample["age"] = age_numeric.where(age_numeric >= 0).astype("Int64")

print("\n整理後的小樣本：")
print(sample[["city", "當事者順位", "age_raw", "age"]].to_string(index=False))

print("\n核對傷亡與車種：")

check_columns = [
    "city",
    "當事者順位",
    "死亡受傷人數",
    "當事者區分-類別-大類別名稱-車種",
]

print(sample[check_columns].to_string(index=False))

# 將「死亡1;受傷0」拆成兩個數值欄位
casualties = sample["死亡受傷人數"].str.extract(
    r"死亡\s*(?P<deaths>\d+)\s*[;；]\s*受傷\s*(?P<injuries>\d+)"
)

sample[["deaths", "injuries"]] = casualties.astype("Int64")

# 建立分析用車種欄位，原始欄位仍保留
sample["vehicle_type"] = sample[
    "當事者區分-類別-大類別名稱-車種"
].fillna("未知／未填")

print("\n轉換後的欄位：")
print(sample[
    ["city", "當事者順位", "deaths", "injuries", "vehicle_type", "age"]
].to_string(index=False))

sample["year"] = pd.to_numeric(sample["發生年度"]).astype("Int64")
sample["accident_type"] = sample["事故類別名稱"]

# 暫用日期、時間、地點、座標與類別辨識候選事故
group_columns = [
    "發生日期", "發生時間", "發生地點",
    "經度", "緯度", "事故類別名稱",
]

group_numbers = sample.groupby(
    group_columns, dropna=False, sort=False
).ngroup()

sample["accident_id"] = group_numbers.map(
    lambda number: f"demo_2025_{number + 1:04d}"
)

# 事故表：只取事故層級欄位，再移除重複列
accidents_demo = sample[
    ["accident_id", "year", "city", "accident_type", "deaths", "injuries"]
].drop_duplicates()

# 若同一 ID 留下多列，代表事故欄位不一致，需要檢查
if not accidents_demo["accident_id"].is_unique:
    raise ValueError("同一候選事故的欄位不一致，請檢查分組。")

# 當事者表：保留各位當事者的紀錄
participants_demo = sample[
    ["accident_id", "當事者順位", "vehicle_type", "age"]
].rename(columns={"當事者順位": "participant_order"}).copy()

print("\n事故表：")
print(accidents_demo.to_string(index=False))

print("\n當事者表：")
print(participants_demo.to_string(index=False))

print("\n候選事故分組數：", len(accidents_demo))
print("當事者紀錄列數：", len(participants_demo))
print("樣本死亡人數：", accidents_demo["deaths"].sum())
