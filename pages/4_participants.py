import streamlit as st
from components.age_distribution import render as render_age
from components.cause_and_age import render_causes, render_vehicle_ages
from utils.data_loader import load_data
from utils.filters import render_sidebar_filters

st.title("肇因與當事者")
accidents, participants, is_sample = load_data()
filtered_acc, filtered_part, info = render_sidebar_filters(accidents, participants)
metadata = accidents.attrs.get("metadata", {})
if is_sample:
    st.warning("目前使用開發小樣本，僅供操作測試；請勿將本頁數字當作全年分析結果。")
else:
    st.caption(f"資料範圍：{metadata.get('date_start', '—')} 至 {metadata.get('date_end', '—')}｜六都 A1／A2 清理資料。")
st.write(f"目前條件：年度 {info['years']}｜縣市 {len(info['cities'])} 個｜類別 {info['types']}")

all_vehicles = sorted(participants["vehicle_type"].dropna().unique().tolist())
previous_options = st.session_state.get("participants_vehicle_options")
previous_selection = st.session_state.get(
    "participants_selected_vehicles",
    st.session_state.get("participants_vehicles", all_vehicles),
)
if previous_options != all_vehicles:
    selection = all_vehicles if previous_options is None or set(previous_selection) == set(previous_options) else [value for value in previous_selection if value in all_vehicles]
    st.session_state["participants_vehicles"] = selection.copy()
    st.session_state["participants_vehicle_options"] = all_vehicles
elif "participants_vehicles" not in st.session_state:
    st.session_state["participants_vehicles"] = previous_selection.copy()
selected_vehicles = st.multiselect("車種篩選（A 與 F 圖表共用）", options=all_vehicles, key="participants_vehicles")
# 另存非 widget 狀態，避免切頁清除元件狀態後遺失車種選擇。
st.session_state["participants_selected_vehicles"] = selected_vehicles.copy()
vehicle_part = filtered_part.loc[filtered_part["vehicle_type"].isin(selected_vehicles)].copy()
involved_ids = vehicle_part["accident_id"].unique()
vehicle_acc = filtered_acc.loc[filtered_acc["accident_id"].isin(involved_ids)].copy()
st.write(f"已選車種：{len(selected_vehicles)} 類｜涉及事故 {len(vehicle_acc):,} 件｜符合條件的當事者原始紀錄 {len(vehicle_part):,} 筆")
st.caption("涉及事故採任一符合車種的當事者取得事故 ID，並以事故表計案；人的年齡分析另排除非人與無效年齡紀錄。")

st.divider()
render_causes(vehicle_acc, key_prefix="participants_cause")
st.divider()
valid_ages = render_age(vehicle_acc, vehicle_part, key_prefix="participants_age")
st.divider()
render_vehicle_ages(vehicle_part, valid_ages)
