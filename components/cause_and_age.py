"""F 的主要肇因排行與車種年齡箱型圖。"""
import altair as alt
import pandas as pd
import streamlit as st

from utils.chart_style import PRIMARY_COLOR
from utils.widget_state import restore_widget_state, save_widget_state


def summarize_causes(accidents):
    cases = accidents.drop_duplicates("accident_id")
    if "main_cause" in cases:
        causes = cases["main_cause"].astype("string").str.strip()
        # 跨年來源使用兩種同義標籤，保留其他範圍不同的類別。
        causes = causes.replace({
            "駕駛人": "駕駛者",
            "無(車輛駕駛人因素)": "無(車輛駕駛者因素)",
        })
        causes = causes.mask(causes.eq("")).fillna("未知／未填")
    else:
        causes = pd.Series("未知／未填", index=cases.index, dtype="string")
    return (
        causes.value_counts()
        .rename_axis("cause")
        .reset_index(name="cases")
        .sort_values(["cases", "cause"], ascending=[False, True])
        .reset_index(drop=True)
    )


def render_causes(accidents, *, key_prefix):
    st.subheader("主要肇因排行")
    ranking = summarize_causes(accidents)
    if ranking.empty:
        st.info("目前條件下沒有符合的事故。")
        return

    key = f"{key_prefix}_top_n"
    restore_widget_state(key, 10)
    top_n = st.radio(
        "顯示前幾類", [5, 10, 15, 20], horizontal=True,
        key=key, on_change=save_widget_state, args=(key,),
    )
    shown = ranking.head(top_n)
    total = int(ranking["cases"].sum())
    unknown = int(ranking.loc[ranking["cause"].eq("未知／未填"), "cases"].sum())
    st.caption(
        f"符合條件共 {total:,} 件｜圖中顯示 {len(shown)} 類、"
        f"合計 {shown['cases'].sum():,} 件｜未知／未填 {unknown:,} 件，列入排行。"
    )
    st.bar_chart(
        shown,
        x="cause",
        y="cases",
        x_label="事故件數（件）",
        y_label="警方研判主要肇因",
        color=PRIMARY_COLOR,
        stack=False,
        horizontal=True,
        sort="-cases",
    )
    first = shown.iloc[0]
    tied = ranking["cases"].eq(first["cases"]).sum()
    leader = f"並列首位的類別之一為「{first['cause']}」" if tied > 1 else f"件數最多的是「{first['cause']}」"
    st.caption(f"目前篩選下，{leader}，共 {int(first['cases']):,} 件。肇因依警方研判分類，圖表只能描述紀錄中的分布。")


def summarize_vehicle_ages(participants, ages):
    selected = participants.loc[ages.index, ["vehicle_type"]].copy()
    selected["age"] = ages
    selected["vehicle_type"] = selected["vehicle_type"].astype("string").fillna("未知／未填")
    groups = selected.groupby("vehicle_type")["age"]
    summary = groups.agg(n="size", median="median")
    summary["q1"] = groups.quantile(0.25)
    summary["q3"] = groups.quantile(0.75)
    summary["iqr"] = summary["q3"] - summary["q1"]

    # 每種車種與年齡只傳一筆頻數，完整資料也不必把原始人次送到瀏覽器。
    frequencies = groups.value_counts().rename("count").reset_index()
    fences = frequencies.join(summary[["q1", "q3", "iqr"]], on="vehicle_type")
    outside = (
        fences["age"].lt(fences["q1"] - 1.5 * fences["iqr"])
        | fences["age"].gt(fences["q3"] + 1.5 * fences["iqr"])
    )
    whiskers = fences.loc[~outside].groupby("vehicle_type")["age"].agg(
        low="min", high="max"
    )
    summary = summary.join(whiskers).reset_index().sort_values(
        ["n", "vehicle_type"], ascending=[False, True]
    )
    return summary, frequencies.loc[outside]


def render_vehicle_ages(participants, ages):
    st.subheader("依車種類別比較當事者年齡")
    if ages.empty:
        st.info("目前條件下沒有可分析的年齡紀錄。")
        return

    summary, outliers = summarize_vehicle_ages(participants, ages)
    total = int(summary["n"].sum())
    st.caption(f"有效年齡共 {total:,} 人次，使用與上方直方圖相同的車種與待覆核年齡設定。")

    category = alt.Y("vehicle_type:N", title="車種類別", sort=summary["vehicle_type"].tolist())
    base = alt.Chart(summary).encode(y=category)
    whiskers = base.mark_rule(color="#475569").encode(
        x=alt.X("low:Q", title="年齡（歲）", scale=alt.Scale(domain=[0, 120])),
        x2="high:Q",
    )
    boxes = base.mark_bar(size=13, color=PRIMARY_COLOR, opacity=0.75).encode(
        x="q1:Q", x2="q3:Q",
    )
    median = base.mark_tick(orient="vertical", color="#1e293b", size=15).encode(
        x="median:Q",
        tooltip=[
            alt.Tooltip("vehicle_type:N", title="車種類別"),
            alt.Tooltip("n:Q", title="有效人次", format=",d"),
            alt.Tooltip("median:Q", title="中位數"),
            alt.Tooltip("q1:Q", title="第一四分位數"),
            alt.Tooltip("q3:Q", title="第三四分位數"),
        ],
    )
    points = alt.Chart(outliers).mark_point(color="#64748b", size=22).encode(
        y=category, x="age:Q",
        tooltip=[
            alt.Tooltip("vehicle_type:N", title="車種類別"),
            alt.Tooltip("age:Q", title="離群點年齡"),
            alt.Tooltip("count:Q", title="該年齡人次", format=",d"),
        ],
    )
    st.altair_chart(
        (whiskers + boxes + median + points).properties(height=max(110, 27 * len(summary))),
        width="stretch",
    )

    if summary["n"].lt(10).any():
        st.warning("部分車種類別的有效樣本少於 10 人次，請審慎解讀其四分位數與離群點。")
    st.caption("箱內線為中位數，箱體涵蓋中間 50% 的年齡，箱體長度是四分位距。鬚延伸至距箱體 1.5 倍四分位距內的最遠觀測值。超出鬚的點仍是通過年齡規則的紀錄，同車種的同歲離群值合併成一點。")
    eligible = summary.loc[summary["n"].ge(10)]
    if len(eligible) > 1:
        low = eligible.loc[eligible["median"].idxmin()]
        high = eligible.loc[eligible["median"].idxmax()]
        if low["median"] != high["median"]:
            st.caption(
                f"目前至少 10 人次的類別中，中位數從「{low['vehicle_type']}」"
                f"的 {low['median']:g} 歲到「{high['vehicle_type']}」的 {high['median']:g} 歲。"
            )
        else:
            st.caption(f"目前至少 10 人次的類別，其年齡中位數均為 {low['median']:g} 歲。")
    with st.expander("各類別的有效樣本數與四分位數"):
        st.dataframe(
            summary[["vehicle_type", "n", "q1", "median", "q3", "iqr"]].rename(columns={
                "vehicle_type": "車種類別", "n": "有效人次", "q1": "第一四分位數",
                "median": "中位數", "q3": "第三四分位數", "iqr": "四分位距",
            }),
            hide_index=True, width="stretch",
        )
    st.caption("這些年齡描述事故當事者。資料缺少各車種、各年齡層的交通曝險量，無法由分布估算事故風險。")
