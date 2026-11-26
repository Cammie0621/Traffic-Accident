# 開發與模組介面說明

本文件由 B 維護，提供全組開發 Streamlit 圖表模組時的統一介面與規範。

## 1. 本機啟動方式

```bash
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

## 2. A 部分資料交接

專題預設分析範圍為 2021–2025 五年，依 2025、2024、2023、2022、2021 的順序完成各年度資料清理、驗證與整合。目前已完成並驗證 2024、2025 年。

本版以 Python 3.11 驗證。可從 [2024–2025 年資料 Release](https://github.com/Cammie0621/Traffic-Accident/releases/tag/data-2024-2025-v1) 下載完整清理資料，將包內整個 data/processed 放入專案即可開發。若需重建，將 2024、2025 年 ZIP 放在 data/raw，檔名需包含 113年或2024、114年或2025；執行 `python scripts/preprocess.py --years 2024 2025`。原始檔不解壓、不改寫，讀取必要欄位並分批處理。補齊 110–114 年的五份年度 ZIP 後，執行 `python scripts/preprocess.py --years 2021 2022 2023 2024 2025`，各年度皆須核對品質紀錄。

完整表及 metadata.json、data_quality.json、coverage.parquet 保存在 data/processed，此目錄不提交 Git。兩年共 542,483 件推定事故、1,225,376 筆來源當事者紀錄，開發樣本保留 720 個整案。data/samples 是固定且保留整案的真實小樣本，可以供組員開發；不可當作正式全年數據。

load_data() 保持原本回傳 `(accidents, participants, is_sample)`；完整資料優先，其次真實開發樣本，最後舊模擬樣本。快取包含兩表與中繼檔的更新時間及大小，重跑後會更新。年份條件若仍保留舊模擬年度，會依新的可用年度調整。

頁面先執行 render_sidebar_filters，再依共用車種選出參與紀錄與涉及事故 ID。A、F 模組都應接收同一份局部篩選結果。age_distribution.render(accidents, participants, *, key_prefix) 不自行讀原始 CSV。車種涉及事故採聯集，年齡分析只使用所選車種的人的有效年齡。

參數與回傳欄位以 [資料字典](data_dictionary.md)為準，清理口徑見 [清理紀錄](data_quality.md)。F 的箱型圖請共用 age_valid 及 age_review_required，避免另訂年齡規則；E 的地圖請只繪製 coordinate_valid，並列出無座標件數；C 的每日平均分母請使用 coverage 的涵蓋日曆；D 的有效星期與時段需核對 date_valid 及 time_valid。

測試指令為 `python -m unittest discover -s tests -v`，不需額外測試套件。操作及報告講解見 [A 部分說明](a_report.md)。
