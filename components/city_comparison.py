import pandas as pd
import streamlit as st
from utils.chart_style import PRIMARY_COLOR
from utils.filters import SIX_CITIES
from utils.widget_state import restore_widget_state, save_widget_state


def render(
    accidents: pd.DataFrame,
    participants: pd.DataFrame,
    *,
    key_prefix: str = "city",
    selected_cities: list[str] | None = None,
) -> None:
    """B 負責的六都事故件數比較長條圖模組（使用 st.bar_chart）。"""
    cities = selected_cities if selected_cities is not None else SIX_CITIES
    is_all_six = set(cities) == set(SIX_CITIES)

    title = (
        "六都傷亡事故件數比較"
        if is_all_six
        else f"所選城市傷亡事故件數比較（共 {len(cities)} 都）"
    )
    st.subheader(title)

    # 無資料時排序元件會暫時隱藏；另存狀態，恢復資料後仍沿用原本排序。
    sort_key = f"{key_prefix}_sort"
    restore_widget_state(sort_key, "依事故件數排序")

    # 無資料防呆
    if accidents.empty or not cities:
        st.warning("目前篩選條件下無符合資料，請調整左側篩選條件。")
        return

    # 局部互動控制：排序切換
    sort_mode = st.radio(
        "城市排序方式",
        options=["依事故件數排序", "固定城市順序（北到南）"],
        horizontal=True,
        key=sort_key,
        on_change=save_widget_state,
        args=(sort_key,),
    )

    # 使用副本彙整：依城市計算不重複事故件數
    df = accidents.copy()
    summary = (
        df.groupby("city", as_index=False, observed=True)["accident_id"]
        .nunique()
        .rename(columns={"accident_id": "事故件數（件）"})
    )

    # 依北到南順序對齊所選城市，補上件數為 0 的城市
    ordered_cities = [c for c in SIX_CITIES if c in cities]
    base = pd.DataFrame({"city": ordered_cities})
    summary = base.merge(summary, on="city", how="left")
    summary["事故件數（件）"] = summary["事故件數（件）"].fillna(0).astype(int)
    summary = summary.rename(columns={"city": "城市"})

    total_acc = int(summary["事故件數（件）"].sum())
    st.caption(
        f"統計單位：事故件數（不重複案數）｜"
        f"有效樣本數：{total_acc:,} 件"
    )

    # "-事故件數（件）" 為由大到小排序，False 為維持資料原本（北到南）順序
    sort_option = (
        "-事故件數（件）"
        if sort_mode == "依事故件數排序"
        else False
    )

    st.bar_chart(
        summary,
        x="城市",
        y="事故件數（件）",
        x_label="城市",
        y_label="事故件數（件）",
        color=PRIMARY_COLOR,
        horizontal=True,
        sort=sort_option,
    )

    st.caption(
        "註：圖表呈現原始事故件數，未做人口數或交通量（車流量）校正，"
        "件數較高不代表個人發生事故風險較高。"
    )
