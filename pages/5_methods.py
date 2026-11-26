import streamlit as st
from utils.data_loader import load_data

st.title("結論與限制")
accidents, participants, is_sample = load_data()
metadata = accidents.attrs.get("metadata", {})
st.subheader("資料來源與處理方法")
if is_sample:
    st.warning("目前使用開發樣本；本頁筆數不代表全年資料。")
st.write(f"目前載入年度：{metadata.get('years', sorted(accidents['year'].unique().tolist()))}")
sources = metadata.get("sources", [])
if sources:
    source_links = [f"[{source['year']} 年傷亡道路交通事故資料]({source['source_page']})" for source in sources]
    st.markdown("資料來源：" + "、".join(source_links) + "。")
else:
    st.caption("資料來源與實際涵蓋年度請見專案 README。")
st.write("原始資料按當事者記錄，同一案件的全案傷亡會重複出現。前處理產生每案一列的事故表，以及保留原始當事者紀錄的當事者表，使用衍生事故 ID 連接。")
st.write("衍生事故 ID 使用日期、時間、地點、經緯度、警局與事故類別，並驗證來源順位重新起始及同案欄位一致性。它不是官方案件編號，同時同地的不同事故會保留為不同來源案件組。")
st.write("當事者表保留『無或物』及無人駕駛紀錄，以 is_person 標記。年齡圖使用人的有效年齡紀錄；負值、未查獲、不合法數值與非人紀錄均保留清理原因。0 歲不自動視為缺值。")
if not is_sample:
    a, b, c = st.columns(3)
    a.metric("事故件數", f"{len(accidents):,}")
    b.metric("當事者原始紀錄", f"{len(participants):,}")
    c.metric("可分析年齡", f"{int(participants['age_valid'].sum()):,} 人次" if "age_valid" in participants else "—")
st.subheader("假設對照與主要觀察")
st.info("A 的年齡分析說明已提供於專案文件；全組結論由 B 整合 C～F 的分析後補齊。")
st.subheader("分析限制")
st.markdown("""
- A1／A2 傷亡事故不涵蓋所有道路事故。
- 衍生案件識別依賴來源欄位與原始紀錄順序；來源更新或欄位誤填會影響結果。
- 縣市由地點文字判定，再與警局名稱核對；經緯度只做粗略有效性檢查，並非行政市界空間驗證。
- 缺少車流量、人口與行駛里程，事故件數或年齡分布不能直接解讀為個人風險。
- 警方肇因分類不能單憑圖表證明因果關係。
- 當事者年齡不是傷亡者年齡；乘客依原始分類記為乘客，無法由該欄推定乘坐車種。
- 0 歲及 100 歲以上的原始值另標待覆核；圖表可選擇排除，並顯示有效樣本數。
""")
