# -*- coding: utf-8 -*-
"""
IDE 面板组件 - 包含代码编辑器、提交按钮、历史记录
"""

import streamlit as st
from components.code_editor import code_editor, save_code_submission, show_history_panel


def ide_panel(key: str = "monaco_editor"):
    """
    渲染完整的 IDE 面板（右侧 40% 区域）
    
    Args:
        key: session_state 的 key
        
    Returns:
        dict or None: 如果用户提交代码，返回 {"code": ..., "explanation": ...}；否则返回 None
    """
    submission_result = None
    
    # IDE 面板标题栏
    col1, col2 = st.columns([4, 1])
    with col1:
        st.markdown("### 📝 代码编辑器")
    with col2:
        if st.button("❌", key="close_ide_btn", help="关闭编辑器"):
            st.session_state.ide_visible = False
            st.session_state.is_algorithm_mode = False
            st.rerun()
    
    # 代码编辑器
    code = code_editor(key=key, height=350)
    
    # 按钮区域
    st.markdown("---")
    col1, col2, col3 = st.columns([2, 2, 1])
    
    with col1:
        # 提交代码按钮
        if st.button("📤 提交代码", key="submit_code_btn", use_container_width=True):
            if not code or not code.strip():
                st.warning("请先编写代码")
            else:
                # 直接提交代码（不需要录音）
                save_code_submission(code, "")
                
                # 返回提交结果
                submission_result = {
                    "code": code,
                    "explanation": "",  # 不需要语音解释
                }
                
                st.success("✅ 代码已提交！请在对话区与 AI 讨论")
                
                # ⭐ 重要：返回结果，让调用者知道有代码提交
                return submission_result
    
    with col2:
        # 历史记录按钮
        show_history = st.button("📋 历史", key="show_history_btn", use_container_width=True)
    
    with col3:
        # 清空编辑器
        if st.button("🗑️ 清空", key="clear_editor_btn", use_container_width=True):
            st.session_state[key] = ""
            st.rerun()
    
    # 显示历史记录
    if show_history:
        with st.expander("📜 代码提交历史", expanded=True):
            resubmit_code = show_history_panel()
            if resubmit_code:
                st.session_state[key] = resubmit_code
                st.rerun()
    
    # 移除录音区域
    
    # 如果没有提交代码，返回 None
    return None


def show_mini_ide_trigger():
    """
    显示迷你 IDE 触发按钮（当 IDE 关闭但处于算法题模式时）
    
    Returns:
        bool: 如果用户点击打开 IDE，返回 True
    """
    if st.session_state.get("is_algorithm_mode", False) and not st.session_state.get("ide_visible", False):
        st.markdown("---")
        col1, col2 = st.columns([4, 1])
        with col1:
            st.caption("💡 当前为算法题模式，可以打开 IDE 编写代码")
        with col2:
            if st.button("💻 打开 IDE", key="open_ide_trigger", use_container_width=True):
                st.session_state.ide_visible = True
                st.rerun()
