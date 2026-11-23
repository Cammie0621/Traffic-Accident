import altair as alt
import pandas as pd
import streamlit as st
from utils.filters import SIX_CITIES


def render(
    accidents: pd.DataFrame,
    participants: pd.DataFrame,
    *,
    key_prefix: str = "city",
    selected_cities: list[str] | None = None,
) -> None:
    """B 負責的六都事故件數比較長條圖模組。"""
    cities = selected_cities if selected_cities is not None else SIX_CITIES
    is_all_six = set(cities) == set(SIX_CITIES)

    title = (
        "六都傷亡事故件數比較"
        if is_all_six
        else f"所選城市傷亡事故件數比較（共 {len(cities)} 都）"
    )
    st.subheader(title)

    # 無資料防呆
    if accidents.empty or not cities:
        st.warning("目前篩選條件下無符合資料，請調整左側篩選條件。")
        return

    # 局部互動控制：排序切換
    sort_mode = st.radio(
        "城市排序方式",
        options=["依事故件數排序", "固定城市順序（北到南）"],
        horizontal=True,
        key=f"{key_prefix}_sort",
    )

    # 使用副本彙整：依城市計算不重複事故件數
    df = accidents.copy()
    summary = (
        df.groupby("city", as_index=False)["accident_id"]
        .nunique()
        .rename(columns={"accident_id": "accident_count"})
    )

    # 補上「有被勾選但件數為 0」的城市，避免消失
    base = pd.DataFrame({"city": cities})
    summary = base.merge(summary, on="city", how="left")
    summary["accident_count"] = summary["accident_count"].fillna(0).astype(int)

    total_acc = int(summary["accident_count"].sum())
    st.caption(
        f"統計單位：事故件數（不重複案數）｜"
        f"有效樣本數：{total_acc:,} 件"
    )

    # 決定 Y 軸排序
    if sort_mode == "依事故件數排序":
        y_sort = alt.EncodingSortField(field="accident_count", order="descending")
    else:
        y_sort = [c for c in SIX_CITIES if c in cities]

    chart = (
        alt.Chart(summary)
        .mark_bar(color="#2B6CB0")
        .encode(
            x=alt.X(
                "accident_count:Q",
                title="事故件數（件）",
            ),
            y=alt.Y(
                "city:N",
                title="城市",
                sort=y_sort,
            ),
            tooltip=[
                alt.Tooltip("city:N", title="城市"),
                alt.Tooltip(
                    "accident_count:Q",
                    title="事故件數（件）",
                    format=",",
                ),
            ],
        )
        .properties(height=max(220, len(cities) * 45))
    )

    st.altair_chart(chart, use_container_width=True)
    st.caption(
        "註：圖表呈現原始事故件數，未做人口數或交通量（車流量）校正，"
        "件數較高不代表個人發生事故風險較高。"
    )