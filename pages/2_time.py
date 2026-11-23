import streamlit as st
from utils.data_loader import load_data
from utils.filters import render_sidebar_filters

st.title("時間規律") 

accidents, participants, is_sample = load_data()
filtered_acc, filtered_part, info = render_sidebar_filters(
    accidents, participants
)

if is_sample:
    st.caption("目前使用開發用模擬小樣本（待 A 提供正式資料後自動切換）。")

st.write(
    f"目前條件：年度 {info['years']}｜"
    f"縣市 {len(info['cities'])} 個｜類別 {info['types']}"
)
st.write(
    f"篩選後：事故 **{len(filtered_acc)}** 件、"
    f"當事者 **{len(filtered_part)}** 人次"
)