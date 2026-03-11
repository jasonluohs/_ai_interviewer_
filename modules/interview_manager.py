# -*- coding: utf-8 -*-
"""
Interview Manager - 面试状态管理器

专门维护面试过程中的核心状态：
- current_stage: 当前面试阶段 (0-8)
- resume_context: 解析后的简历信息
- history: 当前环节的对话历史
"""

import re
from typing import List, Dict, Any, Optional


# 面试阶段定义
STAGE_NAMES = {
    0: "面试开始",
    1: "候选人自我介绍",
    2: "针对自我介绍提问",
    3: "候选人项目介绍",
    4: "针对项目提问",
    5: "技术基础问题",
    6: "代码题目",
    7: "候选人反问",
    8: "面试结束",
}


def detect_stage_transition(ai_response: str) -> Optional[int]:
    """
    检测 AI 回复中的阶段切换指令
    
    支持的格式：
    - /next[(1)] - 切换到阶段 1
    - /next[(2)] - 切换到阶段 2
    
    Args:
        ai_response: AI 的回复文本
        
    Returns:
        如果检测到切换指令，返回目标阶段编号 (0-8)；否则返回 None
    """
    # 匹配 /next[(数字)] 格式
    match = re.search(r"/next\[\s*\(?\s*(\d+)\s*\)?\s*\]", ai_response)
    if match:
        target_stage = int(match.group(1))
        if 0 <= target_stage <= 8:
            return target_stage
    return None


class InterviewManager:
    """
    面试状态管理器
    
    负责维护：
    1. current_stage: 当前面试阶段 (0-8)
    2. resume_context: 简历信息
    3. history: 当前环节的对话历史
    """

    def __init__(self):
        self._current_stage: int = 0
        self._resume_context: Optional[Dict[str, Any]] = None
        self._history: List[Dict[str, str]] = []

    @property
    def current_stage(self) -> int:
        """获取当前阶段 (0-8)"""
        return self._current_stage

    def set_stage(self, stage: int) -> None:
        """设置当前阶段"""
        if 0 <= stage <= 8:
            self._current_stage = stage

    def update_stage_from_response(self, ai_response: str) -> bool:
        """
        从 AI 回复中检测并更新阶段
        
        Args:
            ai_response: AI 的回复文本
            
        Returns:
            如果检测到阶段切换，返回 True；否则返回 False
        """
        new_stage = detect_stage_transition(ai_response)
        if new_stage is not None and new_stage != self._current_stage:
            self._current_stage = new_stage
            return True
        return False

    @property
    def resume_context(self) -> Optional[Dict[str, Any]]:
        """获取简历信息"""
        return self._resume_context

    def set_resume_context(self, context: Dict[str, Any]) -> None:
        """设置简历信息"""
        self._resume_context = context

    @property
    def history(self) -> List[Dict[str, str]]:
        """获取当前环节的对话历史"""
        return self._history.copy()

    def add_to_history(self, role: str, content: str) -> None:
        """添加对话记录"""
        self._history.append({"role": role, "content": content})

    def clear_history(self) -> None:
        """清空对话历史"""
        self._history = []