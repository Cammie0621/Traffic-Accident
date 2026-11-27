"""保存圖表元件在同一次使用中的選擇，避免切頁或隱藏元件後遺失。"""

import streamlit as st


def restore_widget_state(key: str, default: object) -> None:
    """建立元件前，從未綁定 widget 的狀態還原選擇。"""
    saved_key = f"saved_{key}"
    if saved_key not in st.session_state:
        st.session_state[saved_key] = st.session_state.get(key, default)
    st.session_state[key] = st.session_state[saved_key]


def save_widget_state(key: str) -> None:
    """作為 on_change callback，在頁面重跑前保存最新選擇。"""
    st.session_state[f"saved_{key}"] = st.session_state[key]
