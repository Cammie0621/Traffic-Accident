import streamlit as st
from components import city_comparison
from utils.data_loader import load_data
from utils.filters import render_sidebar_filters

st.title("總覽")

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

st.divider()

# B 的模組：六都事故件數長條圖
city_comparison.render(
    filtered_acc,
    filtered_part,
    key_prefix="overview_city",
    selected_cities=info["cities"],
)

st.divider()
st.info("此處預留給 C：總覽指標卡與月別折線圖。")