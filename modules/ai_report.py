# -*- coding: utf-8 -*-
"""
AI 面试报告生成模块
使用阿里云 DashScope API 调用 Qwen-max (思考模式) 对面试对话进行评价。
"""

from typing import List, Dict, Optional
from openai import OpenAI

from config import DASHSCOPE_API_KEY, LLM_BASE_URL

# ==================== 客户端初始化 ====================
client = OpenAI(
    api_key=DASHSCOPE_API_KEY,
    base_url=LLM_BASE_URL,  # https://dashscope.aliyuncs.com/compatible-mode/v1
)

# ==================== 评价用系统提示词 ====================
REPORT_SYSTEM_PROMPT = """你是一位资深技术面试评审专家。你的任务是对完整面试对话给出可执行、可追踪、可复训的评估报告。

请遵循以下规则：
1) 必须证据驱动：每个关键结论都要引用对话中的具体表现（可简述原话，不要编造）。
2) 必须量化：按权重给分，所有分项加总必须等于总分 100。
3) 必须可行动：改进建议要具体到“下一步怎么做、做到什么标准、如何验证”。
4) 保持客观克制，避免空泛赞美或打击式措辞。

## 评分维度（总分100）
1. 技术能力（30）
2. 问题解决能力（25）
3. 沟通表达能力（20）
4. 学习潜力与思维深度（15）
5. 综合素养（10）

## 输出格式（严格按此顺序）

# AI 面试评价报告

## 一、总体评分
- 总分: X/100
- 评级: `A(90-100) | B(80-89) | C(70-79) | D(60-69) | E(<60)`
- 一句话结论: 不超过30字

## 二、分维度评分与证据
### 1) 技术能力（X/30）
- 证据:
- 风险:

### 2) 问题解决能力（X/25）
- 证据:
- 风险:

### 3) 沟通表达能力（X/20）
- 证据:
- 风险:

### 4) 学习潜力与思维深度（X/15）
- 证据:
- 风险:

### 5) 综合素养（X/10）
- 证据:
- 风险:

## 三、关键亮点（最多3条）
- [亮点1]
- [亮点2]
- [亮点3]

## 四、关键短板（最多3条）
- [短板1]
- [短板2]
- [短板3]

## 五、30天改进计划
- Week 1:
- Week 2:
- Week 3:
- Week 4:

## 六、下一轮面试建议题单（3题）
1. [题目 + 目的]
2. [题目 + 目的]
3. [题目 + 目的]

## 七、结构化评分(JSON)
请在最后单独输出一个 ```json 代码块，字段固定为：
{
  "overall": 0,
  "grade": "",
  "dimensions": {
     "technical": 0,
     "problem_solving": 0,
     "communication": 0,
     "learning_depth": 0,
     "professionalism": 0
  },
  "risk_flags": [""],
  "next_focus": ["", "", ""]
}

注意：
- dimensions 五项必须和 overall 一致。
- JSON 必须可解析，不能带注释。
"""


def _format_history_for_report(history: List[Dict[str, str]]) -> str:
    """
    将对话历史格式化为面试对话记录文本，供评价模型阅读。

    参数:
        history: 对话历史列表，每个元素为 {"role": "user"|"assistant", "content": "..."}

    返回:
        格式化后的对话记录字符串
    """
    if not history:
        return "（无对话记录）"

    lines = []
    turn = 0
    for msg in history:
        role = msg.get("role", "")
        content = msg.get("content", "").strip()
        if not content:
            continue
        if role == "user":
            turn += 1
            lines.append(f"【第 {turn} 轮】")
            lines.append(f"候选人：{content}")
        elif role == "assistant":
            lines.append(f"面试官：{content}")
        lines.append("")  # 空行分隔

    return "\n".join(lines)


def ai_report(
    history: List[Dict[str, str]],
    model: str = "qwen-max",
    enable_thinking: bool = True,
) -> str:
    """
    根据完整对话历史，调用阿里云 Qwen-max (思考模式) 生成面试评价报告。

    参数:
        history:  完整的面试对话历史列表
                  格式: [{"role": "user"|"assistant", "content": "..."}, ...]
                  其中 role="user" 是被面试者的回答，role="assistant" 是面试官的提问/追问。
        model:    使用的模型名称，默认 "qwen-max"（思考模式下实际会走 qwen-max 的深度推理）
        enable_thinking: 是否开启思考模式（深度推理），默认开启

    返回:
        str: AI 生成的面试评价报告文本

    异常:
        如果 API 调用失败，会抛出异常。

    使用示例:
        >>> from modules.ai_report import ai_report
        >>> history = [
        ...     {"role": "assistant", "content": "请做一下自我介绍"},
        ...     {"role": "user", "content": "我是XXX，本科计算机科学..."},
        ...     {"role": "assistant", "content": "请介绍一下TCP三次握手"},
        ...     {"role": "user", "content": "TCP三次握手是..."},
        ... ]
        >>> report = ai_report(history)
        >>> print(report)
    """
    if not history:
        return "⚠️ 没有对话记录，无法生成面试评价报告。"

    # 格式化对话记录
    formatted_history = _format_history_for_report(history)

    # 统计基本信息
    user_turns = sum(1 for msg in history if msg.get("role") == "user")
    assistant_turns = sum(1 for msg in history if msg.get("role") == "assistant")

    # 构造用户消息：把整段面试对话交给评价模型
    user_message = (
        f"以下是一段完整的技术面试对话记录，共 {user_turns} 轮候选人回答、"
        f"{assistant_turns} 轮面试官提问。\n"
        f"请根据对话内容对被面试者的表现进行全面评价。\n\n"
        f"--- 面试对话记录 ---\n\n"
        f"{formatted_history}\n"
        f"--- 对话记录结束 ---\n\n"
        f"请按要求的格式输出评价报告。"
    )

    messages = [
        {"role": "system", "content": REPORT_SYSTEM_PROMPT},
        {"role": "user", "content": user_message},
    ]

    try:
        # 构造请求参数
        request_params = {
            "model": model,
            "messages": messages,
        }

        # 开启思考模式（Qwen-max 深度推理）
        # DashScope 兼容模式下，通过 extra_body 传递 enable_thinking 参数
        if enable_thinking:
            request_params["extra_body"] = {"enable_thinking": True}

        completion = client.chat.completions.create(**request_params)

        # 提取回复内容
        if completion.choices and completion.choices[0].message:
            return completion.choices[0].message.content or "⚠️ 模型未返回有效内容。"
        else:
            return "⚠️ 模型返回为空，请稍后重试。"

    except Exception as e:
        raise RuntimeError(f"面试评价报告生成失败: {str(e)}") from e


def ai_report_stream(
    history: List[Dict[str, str]],
    resume_analysis: Optional[Dict] = None,
    model: str = "qwen-max",
    enable_thinking: bool = True,
):
    """
    流式版本：根据完整对话历史，流式生成面试评价报告。
    适用于 Streamlit 等需要逐步显示内容的前端。

    参数:
        history:  完整的面试对话历史列表
        resume_analysis: 可选，简历分析结果（用于匹配度评估）
        model:    使用的模型名称
        enable_thinking: 是否开启思考模式

    返回:
        Generator[str]: 逐步累积的报告文本（每次 yield 包含从开头到当前的完整文本）

    使用示例（Streamlit 集成）:
        >>> placeholder = st.empty()
        >>> for partial_report in ai_report_stream(st.session_state.history):
        ...     placeholder.markdown(partial_report)
    """
    if not history:
        yield "⚠️ 没有对话记录，无法生成面试评价报告。"
        return

    # 格式化对话记录
    formatted_history = _format_history_for_report(history)

    user_turns = sum(1 for msg in history if msg.get("role") == "user")
    assistant_turns = sum(1 for msg in history if msg.get("role") == "assistant")

    user_message = (
        f"以下是一段完整的技术面试对话记录，共 {user_turns} 轮候选人回答、"
        f"{assistant_turns} 轮面试官提问。\n"
        f"请根据对话内容对被面试者的表现进行全面评价。\n\n"
        f"--- 面试对话记录 ---\n\n"
        f"{formatted_history}\n"
        f"--- 对话记录结束 ---"
    )
    
    # 如果有简历分析结果，添加简历匹配度评估要求
    if resume_analysis:
        basic = resume_analysis.get("basic_info", {})
        skills = resume_analysis.get("technical_skills", {})
        work = resume_analysis.get("work_experience", [])
        projects = resume_analysis.get("projects", [])
        assess = resume_analysis.get("assessment", {})
        
        resume_summary = f"""
--- 候选人简历摘要 ---
姓名：{basic.get('name', '未知')}
工作年限：{basic.get('years_of_experience', 0)}年
技术栈：{', '.join(skills.get('programming_languages', []) + skills.get('frameworks', [])[:5])}
技术深度评分：{assess.get('technical_depth_score', 0)}/10
技术广度评分：{assess.get('technical_breadth_score', 0)}/10
工作经历：{len(work)}段
项目经验：{len(projects)}个
--- 简历摘要结束 ---

请在评价报告中增加以下维度：

## 六、简历匹配度评估

### 1. 技术匹配度（XX / 10）
- 评估面试中展现的技术能力与简历描述的技能栈匹配程度
- 检查是否简历中提到的关键技术都在面试中得到了验证

### 2. 经验匹配度（XX / 10）
- 评估面试表现与简历中工作年限的匹配程度
- 检查项目经验的真实性和深度
- 识别是否存在简历夸大或面试表现不符的情况

### 3. 一致性评估
- 指出面试回答与简历描述一致的地方
- 标注可能存在的疑点或不一致之处
"""
        user_message += f"\n\n{resume_summary}"
    
    user_message += "\n\n请按要求的格式输出评价报告。"

    messages = [
        {"role": "system", "content": REPORT_SYSTEM_PROMPT},
        {"role": "user", "content": user_message},
    ]

    try:
        request_params = {
            "model": model,
            "messages": messages,
            "stream": True,
        }

        if enable_thinking:
            request_params["extra_body"] = {"enable_thinking": True}
            # 流式 + 思考模式下，需要设置 stream_options 以获取增量输出
            request_params["stream_options"] = {"include_usage": True}

        completion = client.chat.completions.create(**request_params)

        full_response = ""
        for chunk in completion:
            if chunk.choices and chunk.choices[0].delta.content:
                content = chunk.choices[0].delta.content
                full_response += content
                yield full_response

    except Exception as e:
        yield f"⚠️ 面试评价报告生成失败: {str(e)}"
