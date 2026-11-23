import streamlit as st
from utils.data_loader import load_data
from utils.filters import render_sidebar_filters

st.title("肇因與當事者")

accidents, participants, is_sample = load_data()
filtered_acc, filtered_part, info = render_sidebar_filters(
    accidents, participants
)

if is_sample:
    st.caption("目前使用 2021–2025 開發用模擬小樣本。")

st.write(
    f"目前條件：年度 {info['years']}｜"
    f"縣市 {len(info['cities'])} 個｜類別 {info['types']}"
)

# 同頁共用車種控制（由頁面建立一次，之後傳給 A 與 F）
all_vehicles = sorted(
    participants["vehicle_type"].dropna().unique().tolist()
)
selected_vehicles = st.multiselect(
    "車種篩選（A 與 F 圖表共用）",
    options=all_vehicles,
    default=all_vehicles,
    key="participants_vehicles",
)

st.write(
    f"已選車種：{len(selected_vehicles)} 類｜"
    f"目前範圍事故 {len(filtered_acc):,} 件、"
    f"當事者 {len(filtered_part):,} 人次"
)

st.divider()
st.info("此處預留給 F：主要肇因水平長條圖。")
st.divider()
st.info("此處預留給 A：當事者年齡直方圖。")
st.divider()
st.info("此處預留給 F：車種年齡箱型圖。")