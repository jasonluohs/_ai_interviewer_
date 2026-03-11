# -*- coding: utf-8 -*-
"""
简历解析模块 - PDF 解析 + LLM 深度分析
功能：
1. 使用 pdfplumber 提取 PDF 文本
2. 调用 DashScope LLM (qwen-turbo) 快速分析简历
3. 返回结构化 JSON 数据
4. 支持缓存机制（避免重复解析）
"""

import json
import pdfplumber
from typing import Dict, Any

try:
    from config import DASHSCOPE_API_KEY
except ImportError:
    import os
    DASHSCOPE_API_KEY = os.getenv("DASHSCOPE_API_KEY", "")

from openai import OpenAI

# 简化的分析 Prompt（减少 token 数，加快速度）
RESUME_ANALYSIS_PROMPT = """你是一位技术面试官，请快速分析这份简历并提取关键信息。

请严格以 JSON 格式返回（不要任何额外文字）：
{
  "basic_info": {
    "name": "姓名",
    "contact": "联系方式",
    "years_of_experience": 工作年限（数字）
  },
  "technical_skills": {
    "programming_languages": ["语言列表"],
    "frameworks": ["框架列表"],
    "databases": ["数据库列表"],
    "tools": ["工具列表"]
  },
  "work_experience": [
    {"company": "公司", "position": "职位", "duration": "时间", "responsibilities": ["职责"]}
  ],
  "projects": [
    {"name": "项目名", "technologies": ["技术"], "highlights": ["亮点"], "contribution": "贡献"}
  ],
  "assessment": {
    "technical_depth_score": 1-10 的整数，
    "technical_breadth_score": 1-10 的整数，
    "risk_points": ["风险点"]
  }
}

评估标准：
- 技术深度：项目复杂度、技术难点
- 技术广度：技能多样性
- 风险点：频繁跳槽、技能不匹配等"""


def extract_text_from_pdf(pdf_path: str) -> str:
    """
    从 PDF 文件提取文本内容
    
    Args:
        pdf_path: PDF 文件路径
        
    Returns:
        提取的文本内容
    """
    text = ""
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"
    except Exception as e:
        raise Exception(f"PDF 解析失败：{str(e)}")
    
    return text.strip()


def analyze_resume_with_llm(resume_text: str) -> Dict[str, Any]:
    """
    使用 LLM 深度分析简历内容
    
    Args:
        resume_text: 简历文本内容
        
    Returns:
        结构化分析结果（字典）
    """
    client = OpenAI(
        api_key=DASHSCOPE_API_KEY,
        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
    )
    
    messages = [
        {
            "role": "system",
            "content": "你是一位资深技术面试官，擅长简历分析和人才评估。请严格以 JSON 格式返回分析结果。"
        },
        {
            "role": "user",
            "content": f"{RESUME_ANALYSIS_PROMPT}\n\n以下是简历内容：\n{'='*50}\n{resume_text}\n{'='*50}"
        }
    ]
    
    try:
        completion = client.chat.completions.create(
            model="qwen-plus",
            messages=messages,
            stream=False,
            temperature=0.3,
        )
        
        response_text = completion.choices[0].message.content.strip()
        
        # 尝试解析 JSON（处理可能的 markdown 代码块包裹）
        if response_text.startswith("```"):
            # 移除 markdown 代码块标记
            if response_text.startswith("```json"):
                response_text = response_text[7:]
            elif response_text.startswith("```"):
                response_text = response_text[3:]
            if response_text.endswith("```"):
                response_text = response_text[:-3]
            response_text = response_text.strip()
        
        analysis_result = json.loads(response_text)
        
        # 验证必要字段
        required_fields = ["basic_info", "technical_skills", "assessment"]
        for field in required_fields:
            if field not in analysis_result:
                analysis_result[field] = {}
        
        return analysis_result
        
    except json.JSONDecodeError as e:
        raise Exception(f"LLM 返回格式错误，无法解析为 JSON: {str(e)}\n原始响应：{response_text[:500]}")
    except Exception as e:
        raise Exception(f"简历分析失败：{str(e)}")


def parse_resume(pdf_file_path: str) -> Dict[str, Any]:
    """
    解析简历 PDF 文件并返回结构化分析结果
    
    Args:
        pdf_file_path: PDF 文件路径
        
    Returns:
        包含简历分析结果的字典
    """
    # 1. 提取 PDF 文本
    resume_text = extract_text_from_pdf(pdf_file_path)
    
    if not resume_text or len(resume_text) < 50:
        raise Exception("简历内容过少，可能 PDF 解析失败或文件损坏")
    
    # 2. 使用 LLM 深度分析
    analysis_result = analyze_resume_with_llm(resume_text)
    
    # 3. 添加原始文本（用于后续参考）
    analysis_result["raw_text"] = resume_text
    
    return analysis_result


def format_resume_for_prompt(analysis: Dict[str, Any]) -> str:
    """
    将简历分析结果格式化为 system prompt 中的简历摘要
    
    Args:
        analysis: 简历分析结果字典
        
    Returns:
        格式化的简历摘要文本
    """
    basic = analysis.get("basic_info", {})
    skills = analysis.get("technical_skills", {})
    work = analysis.get("work_experience", [])
    projects = analysis.get("projects", [])
    assess = analysis.get("assessment", {})
    
    # 基本信息
    lines = []
    lines.append(f"【候选人基本信息】")
    if basic.get("name"):
        lines.append(f"姓名：{basic['name']}")
    if basic.get("contact"):
        lines.append(f"联系方式：{basic['contact']}")
    if basic.get("years_of_experience", 0) > 0:
        lines.append(f"工作年限：{basic['years_of_experience']}年")
    lines.append("")
    
    # 技术栈
    lines.append("【技术栈】")
    if skills.get("programming_languages"):
        lines.append(f"编程语言：{', '.join(skills['programming_languages'])}")
    if skills.get("frameworks"):
        lines.append(f"框架：{', '.join(skills['frameworks'])}")
    if skills.get("databases"):
        lines.append(f"数据库：{', '.join(skills['databases'])}")
    if skills.get("tools"):
        lines.append(f"工具：{', '.join(skills['tools'])}")
    lines.append("")
    
    # 工作经历
    if work:
        lines.append("【工作经历】")
        for idx, job in enumerate(work[:3], 1):  # 最多显示 3 段
            company = job.get("company", "未知公司")
            position = job.get("position", "未知职位")
            duration = job.get("duration", "")
            lines.append(f"{idx}. {company} - {position} {duration}")
        lines.append("")
    
    # 项目经验
    if projects:
        lines.append("【重点项目】")
        for idx, proj in enumerate(projects[:3], 1):  # 最多显示 3 个
            name = proj.get("name", "未知项目")
            tech = ", ".join(proj.get("technologies", []))
            lines.append(f"{idx}. {name}（技术栈：{tech}）")
        lines.append("")
    
    # 能力评估
    lines.append("【能力评估】")
    depth = assess.get("technical_depth_score", 0)
    breadth = assess.get("technical_breadth_score", 0)
    lines.append(f"技术深度评分：{depth}/10")
    lines.append(f"技术广度评分：{breadth}/10")
    if assess.get("risk_points"):
        lines.append(f"风险提示：{', '.join(assess['risk_points'])}")
    
    return "\n".join(lines)


async def parse_resume_async(pdf_file_path: str) -> Dict[str, Any]:
    """
    异步版本的简历解析（用于 Streamlit 的 async 环境）
    
    Args:
        pdf_file_path: PDF 文件路径
        
    Returns:
        包含简历分析结果的字典
    """
    import asyncio
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, parse_resume, pdf_file_path)
