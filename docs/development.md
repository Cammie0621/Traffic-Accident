# 開發與模組介面說明

本文件由 B 維護，提供全組開發 Streamlit 圖表模組時的統一介面與規範。

## 1. 本機啟動方式

```bash
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m streamlit run app.py