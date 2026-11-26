"""A's age histogram, operating only on the tables supplied by the page."""
from __future__ import annotations

import altair as alt
import pandas as pd
import streamlit as st
from utils.chart_style import PRIMARY_COLOR
from utils.cleaning import AGE_REASONS
from utils.widget_state import restore_widget_state, save_widget_state


def summarize_ages(participants: pd.DataFrame, bin_width: int, exclude_review: bool = False):
    if bin_width not in (5, 10):
        raise ValueError("Age bin width must be 5 or 10")
    age = pd.to_numeric(participants["age"], errors="coerce")
    person = participants.get("is_person", pd.Series(True, index=participants.index)).fillna(False).astype(bool)
    valid = person & age.notna() & age.between(0, 120) & age.mod(1).eq(0)
    if "age_valid" in participants:
        valid &= participants["age_valid"].fillna(False).astype(bool)
    review = participants.get("age_review_required", age.eq(0) | age.ge(100)).fillna(False).astype(bool)
    selected = valid & (~review if exclude_review else True)
    values = age.loc[selected].astype(int)
    counts = {"records":len(participants), "person_records":int(person.sum()), "non_person_records":int((~person).sum()), "invalid_age_records":int((person & ~valid).sum()), "review_excluded":int((valid & ~selected).sum()), "valid_age_records":len(values)}
    if values.empty:
        return pd.DataFrame(columns=["age_start","age_end","age_range","count"]), counts
    starts = values // bin_width * bin_width
    bins = list(range(0, int(starts.max()) + bin_width, bin_width))
    hist = starts.value_counts().reindex(bins, fill_value=0).rename_axis("age_start").reset_index(name="count")
    hist["age_end"] = hist["age_start"] + bin_width
    hist["age_range"] = hist.apply(lambda row: f"{int(row.age_start)}–{int(row.age_end)-1} 歲", axis=1)
    if int(hist["count"].sum()) != len(values):
        raise ValueError("Histogram total does not match selected valid-age records")
    return hist, counts


def render(accidents: pd.DataFrame, participants: pd.DataFrame, *, key_prefix: str = "age") -> None:
    st.subheader("當事者年齡分布")
    width_key = f"{key_prefix}_bin_width"
    review_key = f"{key_prefix}_exclude_review"
    restore_widget_state(width_key, 5)
    restore_widget_state(review_key, False)
    left, right = st.columns([1, 2])
    with left:
        width = st.radio(
            "年齡組距", [5, 10],
            format_func=lambda value: f"{value} 歲一組",
            horizontal=True, key=width_key,
            on_change=save_widget_state, args=(width_key,),
        )
    with right:
        exclude_review = st.checkbox(
            "排除待覆核年齡（0 歲及 100 歲以上）", key=review_key,
            help="預設保留符合分析範圍的原始年齡。此選項用於比較待覆核值是否影響分布；0 歲不自動視為缺值。",
            on_change=save_widget_state, args=(review_key,),
        )
    histogram, counts = summarize_ages(participants, width, exclude_review)
    first, second, third = st.columns(3)
    first.metric("可分析年齡", f"{counts['valid_age_records']:,} 人次")
    second.metric("人的紀錄未採用於年齡圖", f"{counts['invalid_age_records'] + counts['review_excluded']:,} 筆")
    third.metric("非人紀錄", f"{counts['non_person_records']:,} 筆")
    st.caption(f"統計單位：有效年齡當事者人次｜目前車種涉及 {len(accidents):,} 件事故｜當事者原始紀錄 {counts['records']:,} 筆。")
    if histogram.empty:
        st.info("目前條件下沒有可分析的年齡紀錄，請調整年度、城市、事故類別、車種或待覆核值選項。")
    else:
        chart = alt.Chart(histogram).mark_bar(color=PRIMARY_COLOR, orient="vertical").encode(
            x=alt.X("age_start:Q", title="年齡（歲）", scale=alt.Scale(domain=[0, int(histogram['age_end'].max())], nice=False)),
            x2="age_end:Q",
            y=alt.Y("count:Q", title="當事者人次（人次）", axis=alt.Axis(format=",d"), scale=alt.Scale(zero=True, domainMin=0)),
            y2=alt.datum(0),
            tooltip=[alt.Tooltip("age_range:N", title="年齡區間"), alt.Tooltip("count:Q", title="有效當事者人次", format=",")],
        ).properties(height=360)
        st.altair_chart(chart, width="stretch")
        peak = histogram.loc[histogram["count"].idxmax()]
        st.caption(f"目前組距下最多的是 {peak['age_range']}，共 {int(peak['count']):,} 人次。分組加總：{int(histogram['count'].sum()):,}，與上方可分析年齡人次一致。")
    with st.expander("清理規則與排除筆數"):
        st.write("年齡圖使用可辨識的人之紀錄，採可解析的 0–120 歲整數；120 是本專案檢查門檻，並非官方編碼定義。負值、未填、超出範圍、肇逃尚未查獲及明確非人紀錄不進入年齡分析，原始資料均保留。")
        st.write("0 歲保留；0 歲及 100 歲以上另標為待覆核。可用上方選項觀察排除後的分布。這些值未被自動改寫成其他年齡。")
        if "age_invalid_reason" in participants:
            reasons = participants["age_invalid_reason"].astype(str).value_counts().rename_axis("reason").reset_index(name="紀錄筆數")
            reasons["狀態"] = reasons["reason"].map(AGE_REASONS).fillna(reasons["reason"])
            st.dataframe(reasons[["狀態", "紀錄筆數"]], hide_index=True, width="stretch")
        if exclude_review:
            st.write(f"本次另排除待覆核年齡：{counts['review_excluded']:,} 筆。")
        if not histogram.empty:
            st.dataframe(histogram[["age_range","count"]].rename(columns={"age_range":"年齡區間","count":"當事者人次"}), hide_index=True, width="stretch")
    st.caption("年齡分布描述事故資料中的當事者紀錄；缺少各年齡人口與交通曝險量，不能由圖表判定某年齡層較容易肇事。")
