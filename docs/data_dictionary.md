# 六都事故資料字典

本版處理 2024–2025 年六都 A1／A2 傷亡事故，欄位介面沿用既有規格。事故表每案一列；當事者表每筆來源當事者紀錄一列，包含需要另外辨識的非人紀錄。兩表使用衍生 accident_id 連接。

資料來源為[113 年資料](https://data.gov.tw/dataset/172969)與[114 年資料](https://data.gov.tw/dataset/177136)。2024 年原始 CSV 有 51 欄，2025 年有 52 欄；兩年均具備程式採用的 19 個必要欄位。2025 年多出的共享經濟／外送平台欄位不影響目前圖表。保留來源檔案、紀錄序號及清理旗標，原始 ZIP 與 CSV 不改寫。

## 事故表

檔案為 data/processed/accidents.parquet，共 542,483 列（2024 年 268,662 列、2025 年 273,821 列）。accident_id 唯一。傷亡、事故數、時間、地圖及主要肇因以這張表為基礎。

| 欄位 | 儲存型別 | 定義 |
| --- | --- | --- |
| `accident_id` | `string` | 衍生案件 ID；日期、時間、類別、警局、地點、座標的 SHA256 前 32 碼加來源順位重新起始序號。不是官方案件編號。 |
| `year` | `int16` | 西元年度，例如 2025；用於全站年度篩選。 |
| `city` | `category` | 標準六都名稱，使用臺字；地點優先，缺少地點縣市時才採警局對應。 |
| `accident_type` | `category` | A1 或 A2。 |
| `deaths` | `int16` | 全案死亡人數，每案計一次。 |
| `injuries` | `int16` | 全案受傷人數，每案計一次。 |
| `date` | `datetime64[ns]` | 來源日期解析後的日期，保留臺灣本地日曆；無效為 NaT。 |
| `datetime` | `datetime64[ns]` | 來源本地日期時間，未轉換 UTC；日期或時間無效為 NaT。 |
| `month` | `Int8` | 有效日期的月份，1–12；無效可空。 |
| `weekday` | `Int8` | 有效日期的星期，0＝週一、6＝週日；無效可空。 |
| `hour` | `Int8` | 有效來源時間的小時，0–23；無效可空。 |
| `date_valid` | `bool` | 日期可解析且年度符合來源。 |
| `time_valid` | `bool` | 時間可解析；00:00:00 保留為有效午夜。 |
| `datetime_valid` | `bool` | 日期與時間皆可解析。 |
| `location` | `string` | 地點文字統一臺字及空白；保留路口兩側原有順序，不推定為同一精確事故點。 |
| `location_raw` | `string` | 原始地點文字；供追溯。 |
| `longitude` | `float64` | 解析後經度；不因無效座標刪除整案。 |
| `latitude` | `float64` | 解析後緯度。 |
| `coordinate_valid` | `bool` | 經度 118–124、緯度 20–27 的粗略臺灣範圍檢查；不是六都市界判定。 |
| `longitude_raw` | `string` | 來源經度字串。 |
| `latitude_raw` | `string` | 來源緯度字串。 |
| `date_raw` | `string` | 來源發生日期字串。 |
| `time_raw` | `string` | 來源發生時間字串，保留前導零。 |
| `police_unit` | `category` | 來源處理單位名稱警局層。 |
| `city_method` | `category` | location＝地點文字；police_fallback＝由警局名稱補判。 |
| `city_conflict` | `bool` | 地點與警局皆可對應縣市、但兩者不一致時為真；保留地點判定並明示。 |
| `main_cause` | `category` | 警方研判主要肇因大類；未填顯示未知／未填。 |
| `main_cause_detail` | `category` | 警方研判主要肇因子類；供 F 自行決定排行層級。 |
| `source_file` | `category` | 年度／ZIP 內原始 CSV 名稱。 |
| `source_record` | `int32` | CSV 資料紀錄的 1 起始序號，不含標題；不是物理文字行號。 |
| `participant_records` | `int16` | 此案原始當事者紀錄列數，包含明確非人紀錄。 |
| `person_records` | `int16` | 此案排除明確非人後的人的紀錄列數，包含未查獲者；是人次而非獨立個人數。 |
| `same_key_multiple_cases` | `bool` | 同一組時間地點等欄位有多次來源順位 1，經分組驗證後保留為多案。 |

## 當事者紀錄表

檔案為 data/processed/participants.parquet，共 1,225,376 列（2024 年 606,823 列、2025 年 618,553 列）。participant_id 唯一；accident_id 對應事故表。計算人的紀錄人次時須篩 is_person；年齡分析再篩 age_valid。

| 欄位 | 儲存型別 | 定義 |
| --- | --- | --- |
| `participant_id` | `string` | 衍生案件 ID 加該案來源紀錄順序；唯一，不能用當事者順位直接替代。 |
| `accident_id` | `string` | 衍生案件 ID；日期、時間、類別、警局、地點、座標的 SHA256 前 32 碼加來源順位重新起始序號。不是官方案件編號。 |
| `participant_order` | `int16` | 來源當事者順位；可能重複，不作唯一鍵，也不等於法律責任。 |
| `vehicle_type` | `category` | 分析分類：小客車與小貨車的兼用描述名稱各自統一為其大類；原始人類別依子類區分行人、乘客等；無車種的非人紀錄另標記；有車種的無人車保留原車種，人的年齡分析仍排除。 |
| `vehicle_type_raw` | `category` | 來源車種大類原值。 |
| `vehicle_subtype_raw` | `category` | 來源車種子類原值。 |
| `age_raw` | `category` | 來源年齡字串，包含負值與可疑值，不改寫原始值。 |
| `age` | `Int16` | 符合本專案年齡規則的整數；其餘為缺值。 |
| `age_valid` | `bool` | 可辨識人的紀錄、年齡為可解析的 0–120 整數；排除肇逃尚未查獲及明確非人紀錄。120 是專案門檻，不是官方代碼定義。 |
| `age_invalid_reason` | `category` | valid、non_person、unidentified_person、missing、not_numeric、negative、not_integer、over_120。 |
| `age_review_required` | `bool` | 年齡可用，但為 0 或 100 歲以上；原值保留，圖表提供排除選項。 |
| `is_person` | `bool` | 排除原始屬性明示無或物（動物、堆置物）及無人駕駛自動車；未查獲者仍保留於人的紀錄，但不進入年齡圖。 |
| `sex_raw` | `category` | 來源當事者屬性別文字，亦包含非人、未查獲等來源狀態。 |
| `action_type_raw` | `category` | 來源當事者行動狀態大類。 |
| `action_detail_raw` | `category` | 來源當事者行動狀態子類。 |
| `ordinal_repeated` | `bool` | 同一衍生案件中，來源順位重複；不因此刪除不同當事者。 |
| `source_file` | `category` | 年度／ZIP 內原始 CSV 名稱。 |
| `source_record` | `int32` | CSV 資料紀錄的 1 起始序號，不含標題；不是物理文字行號。 |

## 年齡與車種共用規則

年齡圖與 F 的年齡箱型圖都應使用 age 及 age_valid，不再自行套第二套清理規則。0 歲不直接當缺值；對非人紀錄、肇逃未查獲及年齡無效者保留原始資料與原因。0 歲及 100 歲以上另標待覆核。若圖表排除待覆核值，必須同步更新有效樣本數。

vehicle_type 保留原始分類意義；「小貨車(含客、貨兩用)」與「小貨車」統一顯示為小貨車，2024 年共有 4,536 筆紀錄套用此名稱規則，原始值仍保留在 vehicle_type_raw。乘客不推定為機車或汽車乘客；不同車種各自涉及的事故可能重疊，不能直接相加。車種條件由符合車種的紀錄取得事故 ID，回事故表去重計案；人的年齡圖則只取所選車種的當事者。

## 涵蓋期間與品質資料

coverage.parquet 及 metadata.json 的 coverage 提供月份起訖、calendar_days、covered_calendar_days、A1 年度檔及 A2 月份檔是否存在、全國來源實際出現日期數。完整月份的日平均分母取涵蓋日曆，不只計算所選城市有事故的日期；缺來源月份不可補成零事故。

metadata.json 記錄來源頁面、ZIP SHA256、資料範圍、筆數與版本。data_quality.json 記錄說明列、年齡排除原因、時間與座標品質、同鍵分案及順位重複案例。

data/samples 中是保留整案所有當事者的固定開發小樣本，與正式表同欄位，不能用於正式結論。CSV 來源欄位名稱與意義以來源頁面及保留的 raw 欄位核對。
