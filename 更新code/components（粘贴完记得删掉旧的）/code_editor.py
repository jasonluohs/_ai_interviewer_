# -*- coding: utf-8 -*-
"""
代码编辑器组件 - 轻量级文本编辑器
提供 Python 代码编辑功能
"""

import streamlit as st
from datetime import datetime


def code_editor(key: str = "code_editor", height: int = 300):
    """
    渲染轻量级代码编辑器
    
    Args:
        key: session_state 的 key
        height: 编辑器高度（像素）
        
    Returns:
        str: 编辑器中的代码内容
    """
    # 初始化编辑器内容
    if key not in st.session_state:
        st.session_state[key] = ""
    
    # 使用 st.text_area 作为简易编辑器
    st.markdown("#### 📝 编写代码")
    code = st.text_area(
        label="代码内容",
        value=st.session_state[key],
        height=height,
        key=f"{key}_textarea",
        placeholder="# 在这里编写 Python 代码...",
        label_visibility="collapsed",
    )
    
    # 保存代码到 session_state
    if code and code != st.session_state[key]:
        st.session_state[key] = code
    
    return code


def save_code_submission(code: str, explanation: str = ""):
    """
    保存代码提交到历史记录
    
    Args:
        code: 提交的代码
        explanation: 代码解释（语音转文字）
    """
    if "submitted_codes" not in st.session_state:
        st.session_state.submitted_codes = []
    
    submission = {
        "code": code,
        "explanation": explanation,
        "timestamp": datetime.now().strftime("%H:%M:%S"),
        "index": len(st.session_state.submitted_codes) + 1,
    }
    
    st.session_state.submitted_codes.append(submission)


def show_history_panel():
    """
    显示代码提交历史面板
    
    Returns:
        str or None: 如果用户选择重新提交，返回代码；否则返回 None
    """
    if "submitted_codes" not in st.session_state or not st.session_state.submitted_codes:
        st.info("暂无代码提交记录")
        return None
    
    st.markdown("### 📜 代码提交历史")
    
    # 按时间倒序显示
    for submission in reversed(st.session_state.submitted_codes):
        with st.expander(
            f"第 {submission['index']} 次提交 - {submission['timestamp']}",
            expanded=False,
        ):
            st.markdown("**代码：**")
            st.code(submission["code"], language="python")
            
            if submission.get("explanation"):
                st.markdown("**思路解释：**")
                st.write(submission["explanation"])
            
            # 重新提交按钮
            if st.button(
                "🔄 重新提交此代码",
                key=f"resubmit_{submission['index']}",
                use_container_width=True,
            ):
                return submission["code"]
    
    return None
