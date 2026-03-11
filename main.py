# -*- coding: utf-8 -*-
"""
AI 面试官 - FastAPI 后端
支持真正的流式 TTS：LLM 生成一句就立即 TTS 并播放
"""
import asyncio
import base64
import json
import os
import re
import sys
import tempfile
import uuid
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional, Any

from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

# 确保项目根目录在 sys.path 中
BASE_DIR = Path(__file__).parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from config import (
    STEPFUN_API_KEY,
    TEMP_DIR,
    init_directories,
)
from modules.llm_agent import llm_stream_chat
from modules.rag_engine import get_retrieved_context
from modules.audio_processor import (
    EdgeTTS_async,
    transcribe_file,
    _strip_markdown,
)
from modules.ai_report import ai_report_stream, _format_history_for_report
from modules.resume_parser import parse_resume, format_resume_for_prompt

# 初始化目录
init_directories()

# ==================== FastAPI 应用 ====================
app = FastAPI(title="AI 面试官", version="2.0.0")

# CORS 配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 静态文件服务
static_dir = BASE_DIR / "static"
static_dir.mkdir(exist_ok=True)
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


# ==================== 数据模型 ====================
class ChatRequest(BaseModel):
    message: str
    history: List[Dict[str, str]] = []
    system_prompt: str = ""
    enable_tts: bool = True
    enable_rag: bool = True
    rag_domain: str = "cs"
    rag_top_k: int = 6


class SettingsModel(BaseModel):
    prompt_choice: str = "正常型面试官（默认）"
    system_prompt: str = ""
    enable_tts: bool = True
    enable_rag: bool = True
    rag_domain: str = "cs"
    rag_top_k: int = 6


# ==================== 全局状态 ====================
# 使用内存存储会话状态（生产环境应使用 Redis 等）
session_store: Dict[str, Any] = {
    "history": [],
    "rag_history": [],
    "settings": SettingsModel().model_dump(),
    "resume_uploaded": False,
    "resume_analysis": None,
    "resume_file_name": "",
}

# 预设系统提示词 - 基础流程
default_prompt = """
你是一位技术面试官。请严格按照以下流程完成一轮面试，并在每一步只做当前步骤应做的事。

【总体要求】
1) 面试以问答形式推进，不一次性抛出过多问题。
2) 每次回复保持简洁、清晰、可执行。
3) 重点考察：理解能力、技术深度、问题分析、实现细节、边界情况与工程可行性。
4) 如候选人回答不清晰，先追问澄清，再进入下一步。

【流程步骤】
面试环节如下，每当你完成一个环节，请宣布"我们进入面试的下一个环节 /next[(下一个环节的编号)]"（对于最后一个环节则不需要宣布）：

步骤0：宣布面试开始
- 简短开场，说明将按"自我介绍→经历追问→技术题→追问→结束"进行。

步骤1：引导自我介绍
- 邀请候选人进行自我介绍。
- 若候选人未主动介绍，明确提醒其先做1-2分钟自我介绍。

步骤2：围绕背景与经历提问（1-3问）
- 基于候选人的自我介绍内容提问。
- 若有简历信息（已上传），优先围绕其技能、项目、过往经历提出细节问题。
- 若回答模糊或不准确，进行针对性追问。

步骤3：项目介绍
- 邀请候选人介绍一个最有代表性的项目。

步骤4：项目与技术深挖
- 对候选人提到的项目做进一步技术追问，可覆盖：
    项目背景、目标、系统设计、关键模块、技术选型、性能瓶颈、故障处理与复盘。
- 问题应体现技术性，避免泛泛而谈。

步骤5：技术基础问题
- 根据候选人方向，提出计算机基础相关问题（操作系统、网络、数据库等）。

步骤6：给出一道与候选人方向相关的代码题目
- 题型可为代码题或技术问答题，优先选择与其研究/学习方向相关的问题。
- 题目可参考经典 LeetCode 风格或同类面试题。
- 不要求复杂定量计算，重点考察：
    整体思路、核心概念、实现细节、边界案例、核心算法/技术理解。
- 可要求候选人在 IDE 中作答。
- 关注正确性、鲁棒性、边界条件与可读性。
- 必要时要求其用测试样例进行说明或验证。

步骤7：候选人反问环节
- 询问候选人是否有问题想问面试官。
- 认真回答候选人的问题。

步骤8：结束面试
- 简短总结本轮考察点，礼貌结束。
- 面试应当由面试官主动提出结束，不要一直持续询问下去，进行到适当程度后面试可以停止。

【执行约束】
- 严格按步骤顺序推进；不要跳步。
- 不要在候选人尚未回答当前问题前进入下一阶段。
- 若信息不足，先补充提问再判断。
- 直接给出你要求面试者当下需要做的事情，不要透露接下来的面试内容和步骤，确保回答较为简短。
"""

# 风格补充：温和型
gentle_style_prompt = """
【风格补充：温和型】
- 语气温柔、理解候选人，鼓励式交流。
- 问题难度以简单到中等为主，循序渐进。
- 每轮追问较少（0-1次），优先给提示再追问。
- 允许候选人逐步修正答案，重点看基础是否扎实。
"""

# 风格补充：正常型
normal_style_prompt = """
【风格补充：正常型】
- 语气专业、客观、中性。
- 问题难度中等并逐步提升。
- 每轮适度追问（1-2次），要求解释思路与复杂度。
- 兼顾正确性、鲁棒性与工程可读性。
"""

# 风格补充：压力型
pressure_style_prompt = """
【风格补充：压力型】
- 面试风格对齐大厂高压技术面：语气克制但强硬、节奏快、标准高，持续要求候选人给出可验证结论。
- 题目难度默认 Medium-Hard 到 Hard，优先考察：边界条件、反例构造、最坏情况、可扩展性与工程权衡。
- 每轮固定"主问题 + 深挖追问"模式：连续追问 3-6 次；候选人若答非所问、跳步、模糊表述，立即要求回到问题并重答。
- 严禁只给结论不讲依据：必须说明推理链、关键不变量/正确性理由，并在必要时给出简短证明思路。
- 必须追问复杂度：时间复杂度、空间复杂度、瓶颈来源、可行优化；若未达到预期复杂度，继续要求替代解法与 trade-off。
- 代码审查必须覆盖鲁棒性：空输入、重复元素、极端规模、越界/溢出、退化场景；至少要求给出 3 个针对性测试用例并解释预期输出。
- 允许在候选人卡住时给极少量方向提示，但不给完整答案；提示后必须立即回收主导权并继续高压追问。
- 输出要求短促直接：每次回复 2-4 句，优先指出漏洞、风险与下一步必须回答的问题。
"""

# 预设系统提示词
PRESET_PROMPTS = {
    "温和型面试官": default_prompt + "\n\n" + gentle_style_prompt,
    "正常型面试官（默认）": default_prompt + "\n\n" + normal_style_prompt,
    "压力型面试官": default_prompt + "\n\n" + pressure_style_prompt,
    "自定义": "",
}


# ==================== 工具函数 ====================
def extract_sentences(text: str) -> tuple[List[str], str]:
    """
    从文本中提取完整句子（以标点符号结尾）
    返回：(完整句子列表, 剩余文本)
    """
    punc_pattern = r'([。！？.!?])'
    parts = re.split(punc_pattern, text)
    
    sentences = []
    i = 0
    while i < len(parts) - 1:
        sentence = parts[i].strip()
        punctuation = parts[i + 1]
        
        if sentence:
            clean_sentence = _strip_markdown(sentence + punctuation)
            if clean_sentence.strip():
                sentences.append(clean_sentence)
        i += 2
    
    remaining = parts[-1].strip() if len(parts) % 2 == 1 else ""
    return sentences, remaining


async def generate_tts_audio(text: str) -> Optional[str]:
    """
    生成 TTS 音频并返回 base64 编码
    """
    if not text or not text.strip():
        return None
    
    try:
        tts = EdgeTTS_async(rate="+20%")
        temp_file = TEMP_DIR / f"tts_{uuid.uuid4().hex}.mp3"
        
        success, audio_path = await tts.to_speech_async(text, str(temp_file), use_cache=True)
        
        if success and audio_path and Path(audio_path).exists():
            with open(audio_path, "rb") as f:
                audio_data = f.read()
            # 清理临时文件
            try:
                Path(audio_path).unlink(missing_ok=True)
            except:
                pass
            return base64.b64encode(audio_data).decode("utf-8")
    except Exception as e:
        print(f"TTS 生成失败: {e}")
    
    return None


# ==================== API 端点 ====================

@app.get("/")
async def root():
    """根路径 - 返回前端页面"""
    index_file = static_dir / "index.html"
    if index_file.exists():
        return FileResponse(str(index_file))
    return {"message": "AI 面试官 API", "version": "2.0.0"}


@app.get("/api/presets")
async def get_presets():
    """获取预设提示词列表"""
    return {
        "presets": list(PRESET_PROMPTS.keys()),
        "prompts": PRESET_PROMPTS
    }


@app.get("/api/settings")
async def get_settings():
    """获取当前设置"""
    return session_store["settings"]


@app.post("/api/settings")
async def update_settings(settings: SettingsModel):
    """更新设置"""
    session_store["settings"] = settings.model_dump()
    return {"status": "ok", "settings": session_store["settings"]}


@app.get("/api/history")
async def get_history():
    """获取对话历史"""
    return {"history": session_store["history"]}


@app.delete("/api/history")
async def clear_history():
    """清空对话历史"""
    session_store["history"] = []
    session_store["rag_history"] = []
    return {"status": "ok", "message": "对话历史已清空"}


@app.get("/api/rag/history")
async def get_rag_history():
    """获取 RAG 检索历史"""
    return {"rag_history": session_store["rag_history"]}


@app.get("/api/rag/domains")
async def get_rag_domains():
    """获取可用的 RAG 领域"""
    vdb_root = BASE_DIR / "vector_db"
    domains = []
    if vdb_root.exists():
        domains = sorted([d.name for d in vdb_root.iterdir() if d.is_dir()])
    return {"domains": domains}


# ==================== 简历相关 API ====================

@app.get("/api/resume/status")
async def get_resume_status():
    """获取简历上传状态"""
    return {
        "uploaded": session_store["resume_uploaded"],
        "file_name": session_store["resume_file_name"],
        "analysis": session_store["resume_analysis"]
    }


@app.post("/api/resume/upload")
async def upload_resume(file: UploadFile = File(...)):
    """上传并解析简历 PDF"""
    try:
        # 验证文件类型
        if not file.filename.lower().endswith('.pdf'):
            return JSONResponse(
                status_code=400,
                content={"status": "error", "message": "只支持 PDF 文件格式"}
            )
        
        # 保存临时文件
        temp_file = TEMP_DIR / f"resume_{uuid.uuid4().hex}.pdf"
        with open(temp_file, "wb") as f:
            content = await file.read()
            f.write(content)
        
        print(f"📄 [简历上传] 文件已保存: {temp_file}")
        
        try:
            # 解析简历
            analysis_result = parse_resume(str(temp_file))
            
            print(f"✅ [简历上传] 解析成功，基本信息: {analysis_result.get('basic_info', {})}")
            
            # 存储到 session
            session_store["resume_uploaded"] = True
            session_store["resume_analysis"] = analysis_result
            session_store["resume_file_name"] = file.filename
            
            print(f"💾 [简历上传] 已存储到 session_store, resume_uploaded={session_store['resume_uploaded']}")
            
            return {
                "status": "ok",
                "message": "简历解析成功",
                "file_name": file.filename,
                "analysis": analysis_result
            }
        finally:
            # 清理临时文件
            try:
                temp_file.unlink(missing_ok=True)
            except:
                pass
    
    except Exception as e:
        print(f"❌ [简历上传] 失败: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={"status": "error", "message": f"简历解析失败：{str(e)}"}
        )


@app.delete("/api/resume")
async def delete_resume():
    """删除已上传的简历"""
    session_store["resume_uploaded"] = False
    session_store["resume_analysis"] = None
    session_store["resume_file_name"] = ""
    return {"status": "ok", "message": "简历已删除"}


@app.post("/api/chat/stream")
async def chat_stream(request: ChatRequest):
    """
    流式聊天 + 实时 TTS
    返回 SSE 流，包含文本更新和音频数据
    """
    async def generate():
        try:
            # 准备系统提示词
            system_prompt = request.system_prompt
            if not system_prompt:
                settings = session_store["settings"]
                prompt_choice = settings.get("prompt_choice", "技术面试官（默认）")
                system_prompt = PRESET_PROMPTS.get(prompt_choice, "")
            
            # RAG 检索
            retrieved = ""
            if request.enable_rag:
                try:
                    persist_dir = str(BASE_DIR / "vector_db")
                    retrieved = get_retrieved_context(
                        request.message,
                        domain=request.rag_domain,
                        k=request.rag_top_k,
                        persist_dir=persist_dir,
                    )
                    if retrieved and retrieved.strip():
                        system_prompt += f"\n\n参考知识库内容（仅供回答参考）：\n{retrieved}"
                        session_store["rag_history"].append({
                            "query": request.message,
                            "retrieved": retrieved,
                            "domain": request.rag_domain,
                            "top_k": request.rag_top_k,
                            "timestamp": datetime.now().isoformat(),
                        })
                except Exception as e:
                    print(f"RAG 检索失败: {e}")
            
            # 注入简历信息
            print(f"🔍 [聊天] 检查简历状态: uploaded={session_store['resume_uploaded']}, analysis={session_store['resume_analysis'] is not None}")
            if session_store["resume_uploaded"] and session_store["resume_analysis"]:
                resume_info = format_resume_for_prompt(session_store["resume_analysis"])
                system_prompt += (
                    "\n\n【候选人简历信息】\n" + resume_info
                    + "\n\n请根据候选人的背景，调整面试难度和问题方向，个性化面试。"
                )
                print(f"✅ [聊天] 已注入简历信息，长度: {len(resume_info)} 字符")
            else:
                print(f"⚠️ [聊天] 未检测到简历，跳过注入")
            
            # 更新历史
            history = list(request.history)
            session_store["history"] = history + [{"role": "user", "content": request.message}]
            
            # 流式 LLM 输出 + 实时 TTS
            full_response = ""
            sentence_buffer = ""
            processed_length = 0
            
            for partial in llm_stream_chat(history, request.message, system_prompt):
                full_response = partial
                
                # 发送文本更新
                yield f"data: {json.dumps({'type': 'text', 'content': partial}, ensure_ascii=False)}\n\n"
                
                # 检测新句子并生成 TTS
                if request.enable_tts:
                    new_text = full_response[processed_length:]
                    sentence_buffer += new_text
                    processed_length = len(full_response)
                    
                    sentences, sentence_buffer = extract_sentences(sentence_buffer)
                    
                    for sentence in sentences:
                        # 立即生成 TTS 并发送
                        audio_base64 = await generate_tts_audio(sentence)
                        if audio_base64:
                            yield f"data: {json.dumps({'type': 'audio', 'sentence': sentence, 'data': audio_base64}, ensure_ascii=False)}\n\n"
            
            # 处理剩余文本
            if request.enable_tts and sentence_buffer.strip():
                audio_base64 = await generate_tts_audio(sentence_buffer)
                if audio_base64:
                    yield f"data: {json.dumps({'type': 'audio', 'sentence': sentence_buffer, 'data': audio_base64}, ensure_ascii=False)}\n\n"
            
            # 更新历史
            session_store["history"].append({"role": "assistant", "content": full_response})
            
            # 发送完成信号
            yield f"data: {json.dumps({'type': 'done', 'full_response': full_response}, ensure_ascii=False)}\n\n"
            
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)}, ensure_ascii=False)}\n\n"
    
    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )


@app.post("/api/asr")
async def speech_to_text(file: UploadFile = File(...)):
    """语音识别"""
    try:
        # 保存上传的音频文件
        temp_file = TEMP_DIR / f"asr_{uuid.uuid4().hex}.wav"
        with open(temp_file, "wb") as f:
            content = await file.read()
            f.write(content)
        
        # 调用 ASR
        text = await transcribe_file(str(temp_file), STEPFUN_API_KEY)
        
        # 清理临时文件
        try:
            temp_file.unlink(missing_ok=True)
        except:
            pass
        
        if text and text.strip():
            return {"status": "ok", "text": text.strip()}
        else:
            return {"status": "error", "message": "未识别到有效内容"}
    
    except Exception as e:
        return {"status": "error", "message": str(e)}


@app.post("/api/report/stream")
async def report_stream():
    """流式生成面试报告"""
    async def generate():
        try:
            history = session_store["history"]
            if not history:
                yield f"data: {json.dumps({'type': 'error', 'message': '没有对话记录'}, ensure_ascii=False)}\n\n"
                return
            
            # 传入简历分析结果
            resume_analysis = session_store.get("resume_analysis", None)
            for partial_report in ai_report_stream(history, resume_analysis=resume_analysis):
                yield f"data: {json.dumps({'type': 'text', 'content': partial_report}, ensure_ascii=False)}\n\n"
            
            yield f"data: {json.dumps({'type': 'done'}, ensure_ascii=False)}\n\n"
            
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)}, ensure_ascii=False)}\n\n"
    
    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        }
    )


@app.get("/api/report/download/{format}")
async def download_report(format: str):
    """下载报告/对话记录"""
    history = session_store["history"]
    
    if format == "json":
        return JSONResponse(
            content=history,
            headers={
                "Content-Disposition": f"attachment; filename=interview_history_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            }
        )
    elif format == "txt":
        text = _format_history_for_report(history)
        return StreamingResponse(
            iter([text]),
            media_type="text/plain",
            headers={
                "Content-Disposition": f"attachment; filename=interview_history_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
            }
        )
    else:
        raise HTTPException(status_code=400, detail="不支持的格式")


# ==================== 启动入口 ====================
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
