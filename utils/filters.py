import pandas as pd
import streamlit as st

SIX_CITIES = [
    "臺北市",
    "新北市",
    "桃園市",
    "臺中市",
    "臺南市",
    "高雄市",
]
ACCIDENT_TYPES = ["A1", "A2"]


def _init_state(all_years: list[int]) -> None:
    """初始化跨頁共用的篩選條件。"""
    if "global_years" not in st.session_state:
        st.session_state["global_years"] = all_years
    if "global_cities" not in st.session_state:
        st.session_state["global_cities"] = SIX_CITIES.copy()
    if "global_types" not in st.session_state:
        st.session_state["global_types"] = ACCIDENT_TYPES.copy()


def _reset_filters(all_years: list[int]) -> None:
    """將所有共用篩選重設為全選。"""
    st.session_state["global_years"] = all_years
    st.session_state["global_cities"] = SIX_CITIES.copy()
    st.session_state["global_types"] = ACCIDENT_TYPES.copy()
    st.session_state["sb_years"] = all_years
    st.session_state["sb_cities"] = SIX_CITIES.copy()
    st.session_state["sb_types"] = ACCIDENT_TYPES.copy()


def render_sidebar_filters(
    accidents: pd.DataFrame,
    participants: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    """顯示共用側邊欄，回傳篩選後的事故表、當事者表與條件摘要。"""
    all_years = sorted(accidents["year"].dropna().unique().tolist())
    _init_state(all_years)

    # 切頁時將共用狀態同步回側邊欄元件
    if "sb_years" not in st.session_state:
        st.session_state["sb_years"] = st.session_state["global_years"]
    if "sb_cities" not in st.session_state:
        st.session_state["sb_cities"] = st.session_state["global_cities"]
    if "sb_types" not in st.session_state:
        st.session_state["sb_types"] = st.session_state["global_types"]

    with st.sidebar:
        st.header("共用篩選條件")

        years = st.multiselect(
            "年度",
            options=all_years,
            key="sb_years",
            on_change=lambda: st.session_state.update(
                {"global_years": st.session_state["sb_years"]}
            ),
        )
        cities = st.multiselect(
            "縣市（六都）",
            options=SIX_CITIES,
            key="sb_cities",
            on_change=lambda: st.session_state.update(
                {"global_cities": st.session_state["sb_cities"]}
            ),
        )
        types = st.multiselect(
            "事故類別",
            options=ACCIDENT_TYPES,
            key="sb_types",
            on_change=lambda: st.session_state.update(
                {"global_types": st.session_state["sb_types"]}
            ),
        )

        st.button(
            "重設篩選",
            on_click=_reset_filters,
            args=(all_years,),
            use_container_width=True,
        )

    # 1. 先篩選事故表
    mask = (
        accidents["year"].isin(years)
        & accidents["city"].isin(cities)
        & accidents["accident_type"].isin(types)
    )
    filtered_acc = accidents.loc[mask].copy()

    # 2. 再依事故 ID 取出對應的當事者（確保兩表口徑一致）
    valid_ids = filtered_acc["accident_id"].unique()
    filtered_part = participants[
        participants["accident_id"].isin(valid_ids)
    ].copy()

    filter_info = {
        "years": years,
        "cities": cities,
        "types": types,
    }
    return filtered_acc, filtered_part, filter_info