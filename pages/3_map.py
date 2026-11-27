import streamlit as st
from utils.data_loader import load_data
from utils.filters import render_sidebar_filters

st.title("空間熱點")

accidents, participants, is_sample = load_data()
filtered_acc, filtered_part, info = render_sidebar_filters(
    accidents, participants
)

if is_sample:
    st.caption("目前使用開發小樣本，僅供操作測試；不代表全年資料。")

st.write(
    f"目前條件：年度 {info['years']}｜"
    f"縣市 {len(info['cities'])} 個｜類別 {info['types']}"
)
st.write(f"篩選後事故：{len(filtered_acc):,} 件")

st.divider()
st.info("此處預留給 E：事故地圖、時段滑桿與熱點地點表格。")