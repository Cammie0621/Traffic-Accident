"""統一資料清理規則。"""

from __future__ import annotations

import hashlib
import json
from collections import Counter

import pandas as pd

# 建立辨識縣市的正規表示式
SIX_CITIES = ["臺北市", "新北市", "桃園市", "臺中市", "臺南市", "高雄市"]
REGIONS = SIX_CITIES + ["基隆市", "新竹市", "新竹縣", "苗栗縣", "彰化縣", "南投縣", "雲林縣", "嘉義市", "嘉義縣", "屏東縣", "宜蘭縣", "花蓮縣", "臺東縣", "澎湖縣", "金門縣", "連江縣"]
REGION_PATTERN = r"^(" + "|".join(REGIONS) + r")"
RAW_COLUMNS = ["發生年度", "發生月份", "發生日期", "發生時間", "事故類別名稱", "處理單位名稱警局層", "發生地點", "經度", "緯度", "當事者順位", "死亡受傷人數", "當事者事故發生時年齡", "當事者區分-類別-大類別名稱-車種", "當事者區分-類別-子類別名稱-車種", "當事者屬-性-別名稱", "當事者行動狀態大類別名稱", "當事者行動狀態子類別名稱", "肇因研判大類別名稱-主要", "肇因研判子類別名稱-主要"]
AGE_REASONS = {"valid": "可用年齡", "non_person": "非人紀錄", "unidentified_person": "肇逃尚未查獲", "missing": "未填年齡", "not_numeric": "無法解析", "negative": "負值代碼", "not_integer": "非整數", "over_120": "超出專案檢查範圍"}


def text(series: pd.Series) -> pd.Series:
    """統一文字欄位清理規則：空值轉空字串、去除前後空白。"""
    return series.fillna("").astype(str).str.strip()


def regions(frame: pd.DataFrame) -> tuple[pd.Series, pd.Series, pd.Series]:
    """判斷事故所在縣市；優先採發生地點，缺少時才使用警局。"""
    place = text(frame["發生地點"]).str.replace("台", "臺", regex=False)
    police = text(frame["處理單位名稱警局層"]).str.replace("台", "臺", regex=False)
    location_region = place.str.extract(REGION_PATTERN, expand=False)
    police_region = police.str.extract(REGION_PATTERN, expand=False)
    return location_region.fillna(police_region), location_region, police_region


def clean_age(age_raw: pd.Series, sex_raw: pd.Series) -> pd.DataFrame:
    """清理年齡，但保留原始值與原因。"""
    raw, sex = text(age_raw), text(sex_raw)
    value = pd.to_numeric(raw, errors="coerce") # 字串轉成數字

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
    """清理車種欄位，將大類別與子類別合併。"""
    major = text(frame["當事者區分-類別-大類別名稱-車種"])
    minor = text(frame["當事者區分-類別-子類別名稱-車種"])
    result = major.replace({"小客車(含客、貨兩用)": "小客車", "小貨車(含客、貨兩用)": "小貨車", "": "未知／未填"})
    people = major.eq("人")
    result.loc[people] = minor.loc[people].replace({"": "其他人"})
    # Preserve an unmanned vehicle's actual type for accident-involvement
    # filtering; exclude non-person records through is_person in age analysis.
    result.loc[~is_person & major.eq("")] = "非人紀錄"
    return result


def _case_hash(values: tuple[str, ...]) -> str:
    """把候選案件欄位轉成識別字串，用於生成事故 ID。"""
    payload = json.dumps(values, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()[:32]


def build_tables(source: pd.DataFrame, source_file: str, expected_year: int):
    """將一份來源 CSV 的六都紀錄整理成事故表、當事者表與品質紀錄。

    參數：
        source：已篩選六都的完整來源檔紀錄，保留原始列順序。
        source_file：來源檔識別文字，供日後追溯。
        expected_year：預期的西元年度，用來檢查來源是否正確。

    回傳：
        accidents：每個推定案件一列，傷亡人數在此表每案計一次。
        participants：保留每筆來源當事者紀錄，包含非人及無效年齡。
        audit：本檔的分案、重複順位、無效日期與座標等品質統計。

    同一候選鍵只有一筆順位 1 時，允許其他當事者列出現在它之前；
    多筆順位 1 則依來源順序分案，並驗證同案共同欄位是否一致。
    無法確認分組時拋出 ValueError；產生的 ID 不是官方案件編號。
    """
    # 1. 準備工作表：複製資料並重設索引，保留原本的列順序。
    frame = source.copy().reset_index(drop=True)
    if frame.empty:
        raise ValueError("No selected records")

    # 必要欄位先統一成去除頭尾空白的文字，後面再依用途轉成數字或日期。
    for column in RAW_COLUMNS:
        if column not in frame:
            raise ValueError(f"Missing required source column: {column}")
        frame[column] = text(frame[column])

    # 保留前處理傳入的來源紀錄序號；未提供時才從 1 開始補編。
    # 這是 CSV 資料紀錄的序號，不是包含標題或換行字元的實體文字行號。
    frame["source_file"] = source_file
    if "source_record" not in frame:
        frame["source_record"] = range(1, len(frame) + 1)
    frame["source_record"] = pd.to_numeric(frame["source_record"], errors="raise").astype("int32")

    # 2. 檢查分析範圍：地點優先判定縣市，缺少時以警局補判。
    # city_method 記錄判定來源；city_conflict 標出地點與警局判定不同的列。
    region, region_location, region_police = regions(frame)
    frame["city"] = region
    if not region.isin(SIX_CITIES).all():
        raise ValueError("build_tables expects six-city source records")
    frame["city_method"] = region_location.notna().map({True: "location", False: "police_fallback"})
    frame["city_conflict"] = region_location.notna() & region_police.notna() & region_location.ne(region_police)

    # 年度必須符合本次要求，事故類別只能是 A1 或 A2，否則停止處理。
    frame["year"] = pd.to_numeric(frame["發生年度"], errors="raise").astype("int16")
    if not frame["year"].eq(expected_year).all():
        raise ValueError("Source year does not match the requested year")
    frame["accident_type"] = frame["事故類別名稱"]
    if not frame["accident_type"].isin(["A1", "A2"]).all():
        raise ValueError("Unknown accident category")

    # 3. 驗證當事者順位：必須能轉成數字、至少為 1，且沒有小數。
    # errors="coerce" 會把無法解析的值轉成缺值，交給下方條件統一檢查。
    rank = pd.to_numeric(frame["當事者順位"], errors="coerce")
    if rank.isna().any() or rank.lt(1).any() or rank.mod(1).ne(0).any():
        raise ValueError("Invalid participant ordinal requires source review")
    frame["participant_order"] = rank.astype("int16")

    # 4. 建立候選鍵：同一列的時間、地點等欄位組成 tuple。
    # apply(..., axis=1) 逐列處理；factorize 讓相同 tuple 使用相同整數編碼。
    key_fields = [
        "發生日期", "發生時間", "事故類別名稱", "處理單位名稱警局層",
        "發生地點", "經度", "緯度",
    ]
    keys = frame[key_fields].apply(tuple, axis=1)
    key_codes, unique_keys = pd.factorize(keys, sort=False)

    # 每個不同候選鍵只計算一次雜湊，再檢查不同鍵是否意外產生相同值。
    hashes = {i: _case_hash(key) for i, key in enumerate(unique_keys)}
    if len(set(hashes.values())) != len(hashes):
        raise ValueError("Generated identifier hash collision")
    frame["_base"] = pd.Series(key_codes, index=frame.index)

    # 5. 將同一候選鍵細分為案件：每遇到順位 1，就累加案件序號。
    # 例如順位 [1, 2, 1, 2]，eq(1) 後按鍵 cumsum，得到 [1, 1, 2, 2]。
    frame["_instance"] = rank.eq(1).groupby(frame["_base"]).cumsum().astype("int16")
    starts_per_base = rank.eq(1).groupby(frame["_base"]).sum()
    unique_case = frame["_base"].map(starts_per_base).eq(1)

    # 若整個候選鍵只有一筆順位 1，將所有列歸為同一案，允許 [2, 1] 的順序。
    # 先記錄這種「順位 1 前還有當事者」的筆數，供 audit 追蹤；稍後仍驗證同案欄位。
    unordered_unique_rows = int((unique_case & frame["_instance"].eq(0)).sum())
    frame.loc[unique_case, "_instance"] = 1

    # 此時仍為 0，表示缺順位 1，或多案情境下有無法歸屬的前置紀錄。
    if frame["_instance"].eq(0).any():
        raise ValueError("A candidate case starts without ordinal 1; review before counting")

    # zip 將每列的候選鍵編碼與案件序號配對，組成「年度-雜湊-分案序號」。
    frame["accident_id"] = [
        f"{expected_year}-{hashes[base]}-{instance}"
        for base, instance in zip(frame["_base"], frame["_instance"])
    ]

    # 6. 解析全案傷亡，例如「死亡1;受傷2」轉成 deaths=1、injuries=2。
    # str.extract 由 pandas 處理正規表示式；命名群組會成為輸出欄名。
    casualties = frame["死亡受傷人數"].str.extract(
        r"^死亡\s*(?P<deaths>\d+)\s*[;；]\s*受傷\s*(?P<injuries>\d+)\s*$"
    )
    if casualties.isna().any().any():
        raise ValueError("Unparseable casualty text; no zero imputation is allowed")
    frame[["deaths", "injuries"]] = casualties.astype("int16")
    frame["main_cause"] = frame["肇因研判大類別名稱-主要"].replace("", "未知／未填")
    frame["main_cause_detail"] = frame["肇因研判子類別名稱-主要"].replace("", "未知／未填")

    # 每案的共同欄位應只有一種值。nunique 計算不同值個數，gt(1) 找出衝突；
    # any(axis=1) 表示這件案件只要有任一共同欄位衝突，就必須停止處理。
    shared = ["year", "city", "accident_type", "死亡受傷人數", "main_cause", "main_cause_detail"]
    conflict = frame.groupby("accident_id", sort=False)[shared].nunique(dropna=False).gt(1).any(axis=1)
    if conflict.any():
        raise ValueError(f"{int(conflict.sum())} cases have conflicting shared fields; output was stopped")

    # 各推定案件必須恰好有一筆順位 1，才能用它代表事故層級欄位。
    starts = rank.eq(1).groupby(frame["accident_id"]).sum()
    if not starts.eq(1).all():
        raise ValueError("Case boundary validation failed")

    # 7. 解析日期與時間，另外建立有效旗標；失敗者保留原列，值記為 NaT。
    # %Y%m%d 對應「年月日」；zfill(6) 讓 33500 補成 033500（03:35:00）。
    date = pd.to_datetime(frame["發生日期"], format="%Y%m%d", errors="coerce", exact=True)
    date = date.where(date.dt.year.eq(expected_year))
    clock_text = frame["發生時間"].str.zfill(6)
    clock = pd.to_datetime(clock_text, format="%H%M%S", errors="coerce", exact=True)
    frame["date"] = date
    frame["datetime"] = pd.to_datetime(
        frame["發生日期"] + clock_text,
        format="%Y%m%d%H%M%S", errors="coerce", exact=True,
    ).where(date.notna())
    frame["date_valid"] = date.notna()
    frame["time_valid"] = clock.notna()
    frame["datetime_valid"] = frame["datetime"].notna()

    # .dt 取得月份、星期與小時；星期 0=週一、6=週日。
    # 大寫 Int8 可以容納缺值，讓無效日期或時間仍可保留在表中。
    frame["month"] = date.dt.month.astype("Int8")
    frame["weekday"] = date.dt.dayofweek.astype("Int8")
    frame["hour"] = clock.dt.hour.astype("Int8")

    # 8. 整理地點與座標：統一臺字、連續空白及斜線兩側的空白。
    # 同時保留原始文字欄位，方便回查；不擅自合併不同方向的路口描述。
    frame["location_raw"] = frame["發生地點"]
    frame["location"] = (
        frame["發生地點"].str.replace("台", "臺", regex=False)
        .str.replace(r"\s+", " ", regex=True)
        .str.replace(r"\s*/\s*", " / ", regex=True)
        .str.strip()
    )
    frame["longitude"] = pd.to_numeric(frame["經度"], errors="coerce")
    frame["latitude"] = pd.to_numeric(frame["緯度"], errors="coerce")

    # 只做粗略臺灣範圍檢查，不代表已核對六都行政邊界。
    # 無效座標只標記，不刪除事故；非地圖統計仍可使用這些案件。
    frame["coordinate_valid"] = frame["longitude"].between(118, 124) & frame["latitude"].between(20, 27)
    frame["longitude_raw"], frame["latitude_raw"] = frame["經度"], frame["緯度"]
    frame["date_raw"], frame["time_raw"] = frame["發生日期"], frame["發生時間"]
    frame["police_unit"] = frame["處理單位名稱警局層"]

    # 9. 套用共用年齡與車種規則；concat(axis=1) 將年齡結果橫向加成新欄位。
    # 非人與無效年齡紀錄不刪除，由 is_person、age_valid 等旗標區分用途。
    age = clean_age(frame["當事者事故發生時年齡"], frame["當事者屬-性-別名稱"])
    frame = pd.concat([frame, age], axis=1)
    frame["vehicle_type"] = vehicle_types(frame, frame["is_person"])
    frame["vehicle_type_raw"] = frame["當事者區分-類別-大類別名稱-車種"]
    frame["vehicle_subtype_raw"] = frame["當事者區分-類別-子類別名稱-車種"]
    frame["sex_raw"] = frame["當事者屬-性-別名稱"]
    frame["action_type_raw"] = frame["當事者行動狀態大類別名稱"]
    frame["action_detail_raw"] = frame["當事者行動狀態子類別名稱"]

    # 同案順位相同不代表同一筆當事者；keep=False 將重複組內的每列都標記。
    # cumcount 依案內原始列順序從 0 編號，加 1 後建立獨立的 participant_id。
    repeated = frame.duplicated(["accident_id", "participant_order"], keep=False)
    frame["ordinal_repeated"] = repeated
    sequence = frame.groupby("accident_id", sort=False).cumcount() + 1
    frame["participant_id"] = frame["accident_id"] + "-p" + sequence.astype(str)

    # 10. 建立事故表：分組已驗證一致，每案取順位 1 的事故欄位。
    # 因此每案只留一列，後續傷亡加總應使用這張表，避免按當事者重複加總。
    accident_columns = [
        "accident_id", "year", "city", "accident_type", "deaths", "injuries",
        "date", "datetime", "month", "weekday", "hour",
        "date_valid", "time_valid", "datetime_valid",
        "location", "location_raw", "longitude", "latitude", "coordinate_valid",
        "longitude_raw", "latitude_raw", "date_raw", "time_raw",
        "police_unit", "city_method", "city_conflict", "main_cause", "main_cause_detail",
        "source_file", "source_record",
    ]
    accidents = frame.loc[rank.eq(1), accident_columns].copy()

    # size 計算每案來源紀錄數；布林 is_person 加總則是人的紀錄數。
    # map 依事故 ID 將各案統計對回事故表，包含非人紀錄的總數另行保留。
    sizes = frame.groupby("accident_id", sort=False).size()
    accidents["participant_records"] = accidents["accident_id"].map(sizes).astype("int16")
    accidents["person_records"] = accidents["accident_id"].map(frame.groupby("accident_id")["is_person"].sum()).astype("int16")

    # 同一候選鍵的最大分案序號 > 1，表示該鍵曾被分成多案。
    # to_numpy 讓旗標依目前列順序填入，不另外按索引標籤對齊。
    split_counts = frame.groupby("_base")["_instance"].max()
    split_bases = split_counts[split_counts.gt(1)].index
    accidents["same_key_multiple_cases"] = frame.loc[rank.eq(1), "_base"].isin(split_bases).to_numpy()

    # 11. 建立當事者表：每筆來源紀錄一列，保留車種、年齡、清理旗標與來源。
    participant_columns = [
        "participant_id", "accident_id", "participant_order",
        "vehicle_type", "vehicle_type_raw", "vehicle_subtype_raw",
        "age_raw", "age", "age_valid", "age_invalid_reason", "age_review_required",
        "is_person", "sex_raw", "action_type_raw", "action_detail_raw",
        "ordinal_repeated", "source_file", "source_record",
    ]
    participants = frame[participant_columns].copy()

    # 12. 彙整品質紀錄：True 加總可計算旗標筆數，~ 則取得無效的反向條件。
    # 年齡原因使用當事者表計筆數；無效日期、時間、座標則以事故表計案數。
    # 能執行到此處代表共同欄位驗證已通過，因此 shared_conflicts 為 0。
    audit = {
        "file": source_file,
        "selected_rows": len(frame),
        "accidents": len(accidents),
        "source_rank_one": int(rank.eq(1).sum()),
        "base_keys": len(unique_keys),
        "same_key_split_groups": len(split_bases),
        "ordinal_repeated_rows": int(repeated.sum()),
        "shared_conflicts": 0,
        "city_conflicts": int(frame["city_conflict"].sum()),
        "date_invalid_cases": int((~accidents["date_valid"]).sum()),
        "time_invalid_cases": int((~accidents["time_valid"]).sum()),
        "coordinate_invalid_cases": int((~accidents["coordinate_valid"]).sum()),
        "age_reasons": dict(Counter(participants["age_invalid_reason"])),
        "split_case_ids": accidents.loc[accidents["same_key_multiple_cases"], "accident_id"].tolist(),
        "ordinal_repeated_case_ids": participants.loc[repeated, "accident_id"].unique().tolist(),
    }
    audit["source_rows_before_unique_rank_one"] = unordered_unique_rows

    # 整理輸出索引後，依序回傳事故表、當事者表、品質紀錄。
    return accidents.reset_index(drop=True), participants.reset_index(drop=True), audit
