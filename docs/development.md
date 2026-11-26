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

本版已完成 2021–2025 五年六都資料清理與 A 的年齡圖整合。使用 Python 3.11；組員可從 [五年資料 Release](https://github.com/Cammie0621/Traffic-Accident/releases/tag/data-2021-2025-v1) 下載完整資料，將包內整個 data/processed 放入專案即可開發。

若需重建，將 110–114 年五份年度 ZIP 放在 data/raw，執行 `python scripts/preprocess.py --years 2021 2022 2023 2024 2025`；省略 --years 也預設五年。原始檔不需解壓、不改寫，每個完整來源檔清理後先壓縮記憶體中的字串型別，再整合五年，以控制大型資料的記憶體需求。指定單年時，建議另指定 --output-dir 與 --sample-dir 保留正式五年輸出。

完整表、metadata.json、data_quality.json 與 coverage.parquet 保存在 data/processed，此目錄不提交 Git。五年共 1,309,477 件推定事故、2,953,984 筆來源當事者紀錄。data/samples 保留 1,800 個整案、4,355 筆來源紀錄，可供開發，不作正式分析。

案件識別會先核對每個候選鍵的順位 1 筆數；僅一筆時不要求來源列依順位排列，同鍵多案才使用經驗證的來源重啟順序。缺少順位 1、同案欄位衝突或多案邊界有歧義時停止，不補造當事者。此規則處理 2021 年 A1 的亂序列，仍保留事故表與當事者表的原介面。

load_data() 保持原本回傳 `(accidents, participants, is_sample)`；完整資料優先，其次真實開發樣本，最後舊模擬樣本。快取包含兩表與中繼檔的更新時間及大小，重跑後會更新。年份條件若仍保留舊模擬年度，會依新的可用年度調整。

頁面先執行 render_sidebar_filters，再依共用車種選出參與紀錄與涉及事故 ID。A、F 模組都應接收同一份局部篩選結果。age_distribution.render(accidents, participants, *, key_prefix) 不自行讀原始 CSV。車種涉及事故採聯集，年齡分析只使用所選車種的人的有效年齡。

參數與回傳欄位以 [資料字典](data_dictionary.md)為準，清理口徑見 [清理紀錄](data_quality.md)。F 的箱型圖請共用 age_valid 及 age_review_required，避免另訂年齡規則；E 的地圖請只繪製 coordinate_valid，並列出無座標件數；C 的每日平均分母請使用 coverage 的涵蓋日曆；D 的有效星期與時段需核對 date_valid 及 time_valid。

測試指令為 `python -m unittest discover -s tests -v`，不需額外測試套件。操作及報告講解見 [A 部分說明](a_report.md)。

## 3. 圖表設定的跨頁保存

年度、縣市、事故類別與車種會在同一次使用中保留；年齡組距、排除待覆核值及城市排序也會在切頁返回後還原，無資料而暫時隱藏排序元件時同樣保留。側邊欄「重設共用篩選」只將年度、縣市與事故類別恢復全選，不清除各頁的局部設定。

新增有固定選項的局部控制項時，可使用 `utils/widget_state.py` 的 `restore_widget_state(key, default)` 在建立元件前還原狀態，並設定 `on_change=save_widget_state, args=(key,)` 保存最新選擇。各模組仍須使用獨立的 `key_prefix`。此機制使用 `st.session_state`，保存範圍為同一工作階段，不提供重開瀏覽器後的永久記憶。
