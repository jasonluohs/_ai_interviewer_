# -*- coding: utf-8 -*-
"""
AI 面试官 - Streamlit 前端
方案：专业会客厅 - 浅灰/米白背景、深灰正文、深蓝强调，卡片式对话与留白。
"""
import asyncio
import json
import sys
from datetime import datetime
from pathlib import Path
from uuid import uuid4

import streamlit as st

# 确保项目根在 path 中（以 ai_interviewer 为运行目录）
if str(Path(__file__).parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).parent))

from config import (
    STEPFUN_API_KEY,
    TEMP_DIR,
    AUDIO_SAMPLE_RATE,
    init_directories,
)
from modules.llm_agent import llm_stream_chat
from modules.rag_engine import get_retrieved_context
from modules.audio_processor import (
    TTS_no_stream,
    chunking_tool,
    transcribe_file,
)
from modules.ai_report import ai_report_stream, _format_history_for_report

# -----------------------------------------------------------------------------
# 1. 页面配置
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="InterReviewer",
    layout="wide",
    initial_sidebar_state="expanded",
)

# 确保临时目录存在
init_directories()

# 默认提示词
default_prompt = """
你是一位技术面试官。请严格按照以下流程完成一轮面试，并在每一步只做当前步骤应做的事。

【总体要求】
1) 面试以问答形式推进，不一次性抛出过多问题。
2) 每次回复保持简洁、清晰、可执行。
3) 重点考察：理解能力、技术深度、问题分析、实现细节、边界情况与工程可行性。
4) 如候选人回答不清晰，先追问澄清，再进入下一步。

【流程步骤】
步骤1：宣布面试开始
- 简短开场，说明将按“自我介绍→经历追问→技术题→追问→结束”进行。

步骤2：引导自我介绍
- 邀请候选人进行自我介绍。
- 若候选人未主动介绍，明确提醒其先做1-2分钟自我介绍。

步骤3：围绕背景与经历提问（1-3问）
- 基于候选人的自我介绍内容提问。
- 若有简历信息（已上传），优先围绕其技能、项目、过往经历提出细节问题。
- 若回答模糊或不准确，进行针对性追问。

步骤4：项目与技术深挖
- 对候选人提到的项目做进一步技术追问，可覆盖：
    项目背景、目标、系统设计、关键模块、技术选型、性能瓶颈、故障处理与复盘。
- 问题应体现技术性，避免泛泛而谈。

步骤5：给出一道与候选人方向相关的题目
- 题型可为代码题或技术问答题，优先选择与其研究/学习方向相关的问题。
- 题目可参考经典 LeetCode 风格或同类面试题。
- 不要求复杂定量计算，重点考察：
    整体思路、核心概念、实现细节、边界案例、核心算法/技术理解。

步骤6：代码作答与验证（如为代码题）
- 可要求候选人在 IDE 中作答。
- 关注正确性、鲁棒性、边界条件与可读性。
- 必要时要求其用测试样例进行说明或验证。

步骤7：针对回答继续追问
- 根据候选人的题目回答继续追问技术细节。
- 目标是验证其是否真正理解，而非机械记忆。

步骤8：结束面试
- 简短总结本轮考察点，礼貌结束。
- 面试应当由面试官主动提出结束，不要一直持续询问下去，进行到适当程度后面试可以停止。

【执行约束】
- 严格按步骤顺序推进；不要跳步。
- 不要在候选人尚未回答当前问题前进入下一阶段。
- 若信息不足，先补充提问再判断。
- 直接给出你要求面试者当下需要做的事情，不要透露接下来的面试内容和步骤，确保回答较为简短。
"""

# -----------------------------------------------------------------------------
# 2. 自定义 CSS（专业会客厅风格）
# -----------------------------------------------------------------------------
st.markdown(
    """
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Noto+Sans+SC:wght@400;500;700&display=swap" rel="stylesheet">
    <style>
        .stApp {
            background-color: #f5f5f0;
        }
        [data-testid="stSidebar"] {
            background-color: #ffffff;
            border-right: 1px solid #e9ecef;
        }
        [data-testid="stSidebar"] .stMarkdown { font-family: 'Noto Sans SC', 'Inter', sans-serif; }
        .stApp .main .block-container {
            padding-top: 1.5rem;
            padding-bottom: 2rem;
            max-width: 1100px;
        }
        h1, h2, h3 {
            color: #2c3e50;
            font-family: 'Noto Sans SC', 'Inter', sans-serif;
        }
        p, .stMarkdown { font-size: 16px; line-height: 1.5; }
        .chat-card-user {
            background: linear-gradient(135deg, #2c5f7a 0%, #3d7a94 100%);
            color: #fff;
            border-radius: 12px;
            padding: 14px 18px;
            margin: 10px 0;
            margin-left: 15%;
            box-shadow: 0 2px 8px rgba(44,95,122,0.2);
        }
        .chat-card-assistant {
            background: #ffffff;
            border: 1px solid #e9ecef;
            border-radius: 12px;
            padding: 14px 18px;
            margin: 10px 0;
            margin-right: 15%;
            box-shadow: 0 2px 6px rgba(0,0,0,0.04);
        }
        .chat-card-assistant p { margin: 0; color: #2c3e50; }
        .chat-card-user p { margin: 0; }
        #MainMenu { visibility: hidden; }
        footer { visibility: hidden; }
        .rag-card {
            background: #ffffff;
            border-left: 4px solid #2c5f7a;
            border-radius: 8px;
            padding: 12px 16px;
            margin: 8px 0;
            box-shadow: 0 1px 4px rgba(0,0,0,0.06);
        }
        .rag-card .rag-query {
            color: #2c5f7a;
            font-weight: 600;
            font-size: 14px;
            margin-bottom: 6px;
        }
        .rag-card .rag-content {
            color: #2c3e50;
            font-size: 13px;
            line-height: 1.6;
            white-space: pre-wrap;
        }
        .rag-meta {
            color: #95a5a6;
            font-size: 12px;
            margin-top: 4px;
        }
    </style>
    """,
    unsafe_allow_html=True,
)


def run_async(coro):
    """在 Streamlit 中运行 async 函数（同步封装）"""
    return asyncio.run(coro)


def discover_rag_types(data_dir: Path) -> list[str]:
    """扫描 data/cs 下的题库类型，供侧边栏做过滤。"""
    types = set()
    for path in data_dir.glob("qa_*.jsonl"):
        try:
            with open(path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    obj = json.loads(line)
                    t = str(obj.get("type", "")).strip().lower()
                    if t:
                        types.add(t)
        except Exception:
            # 某个文件损坏时不阻断主流程，避免页面不可用
            continue
    return sorted(types)


# -----------------------------------------------------------------------------
# 3. Session State 初始化
# -----------------------------------------------------------------------------
if "history" not in st.session_state:
    st.session_state.history = []

gentle_style_prompt = """
【风格补充：温和型】
- 语气温柔、理解候选人，鼓励式交流。
- 问题难度以简单到中等为主，循序渐进。
- 每轮追问较少（0-1次），优先给提示再追问。
- 允许候选人逐步修正答案，重点看基础是否扎实。
"""

normal_style_prompt = """
【风格补充：正常型】
- 语气专业、客观、中性。
- 问题难度中等并逐步提升。
- 每轮适度追问（1-2次），要求解释思路与复杂度。
- 兼顾正确性、鲁棒性与工程可读性。
"""

pressure_style_prompt = """
【风格补充：压力型】
- 面试风格对齐大厂高压技术面：语气克制但强硬、节奏快、标准高，持续要求候选人给出可验证结论。
- 题目难度默认 Medium-Hard 到 Hard，优先考察：边界条件、反例构造、最坏情况、可扩展性与工程权衡。
- 每轮固定“主问题 + 深挖追问”模式：连续追问 3-6 次；候选人若答非所问、跳步、模糊表述，立即要求回到问题并重答。
- 严禁只给结论不讲依据：必须说明推理链、关键不变量/正确性理由，并在必要时给出简短证明思路。
- 必须追问复杂度：时间复杂度、空间复杂度、瓶颈来源、可行优化；若未达到预期复杂度，继续要求替代解法与 trade-off。
- 代码审查必须覆盖鲁棒性：空输入、重复元素、极端规模、越界/溢出、退化场景；至少要求给出 3 个针对性测试用例并解释预期输出。
- 允许在候选人卡住时给极少量方向提示，但不给完整答案；提示后必须立即回收主导权并继续高压追问。
- 输出要求短促直接：每次回复 2-4 句，优先指出漏洞、风险与下一步必须回答的问题。
"""

# 预设系统提示词模板
PRESET_PROMPTS = {
    "温和型面试官": default_prompt + "\n\n" + gentle_style_prompt,
    "正常型面试官（默认）": default_prompt + "\n\n" + normal_style_prompt,
    "压力型面试官": default_prompt + "\n\n" + pressure_style_prompt,
    "自定义": "",
}
if "system_prompt" not in st.session_state:
    st.session_state.system_prompt = PRESET_PROMPTS["正常型面试官（默认）"]
if "prompt_choice" not in st.session_state:
    st.session_state.prompt_choice = "正常型面试官（默认）"
if "enable_tts" not in st.session_state:
    st.session_state.enable_tts = True
if "audio_processed_token" not in st.session_state:
    st.session_state.audio_processed_token = None
if "last_tts_path" not in st.session_state:
    st.session_state.last_tts_path = None
# RAG 相关状态
if "enable_rag" not in st.session_state:
    st.session_state.enable_rag = True
if "rag_domain" not in st.session_state:
    st.session_state.rag_domain = "cs"
if "rag_top_k" not in st.session_state:
    st.session_state.rag_top_k = 6
if "rag_type_filter" not in st.session_state:
    st.session_state.rag_type_filter = "全部"
if "rag_history" not in st.session_state:
    st.session_state.rag_history = []  # 存储每轮 RAG 检索记录
# 面试报告相关状态
if "ai_report_text" not in st.session_state:
    st.session_state.ai_report_text = ""  # 已生成的报告内容
if "report_generating" not in st.session_state:
    st.session_state.report_generating = False


# -----------------------------------------------------------------------------
# 4. 侧边栏
# -----------------------------------------------------------------------------
with st.sidebar:
    st.title("面试官设置")
    st.markdown("---")

    # 预设提示词选择
    prompt_choice = st.selectbox(
        "选择面试官类型",
        options=list(PRESET_PROMPTS.keys()),
        index=list(PRESET_PROMPTS.keys()).index(st.session_state.prompt_choice)
        if st.session_state.prompt_choice in PRESET_PROMPTS
        else 0,
        help='选择预设角色，或选「自定义」手动编辑',
    )

    # 切换预设时自动更新提示词内容
    if prompt_choice != st.session_state.prompt_choice:
        st.session_state.prompt_choice = prompt_choice
        if prompt_choice != "自定义":
            st.session_state.system_prompt = PRESET_PROMPTS[prompt_choice]

    # 提示词编辑区
    if prompt_choice == "自定义":
        system_prompt = st.text_area(
            "自定义系统提示词",
            value=st.session_state.system_prompt,
            height=160,
            help="自由编写面试官的角色与风格",
        )
        st.session_state.system_prompt = system_prompt
    else:
        with st.expander("查看 / 微调当前提示词", expanded=False):
            system_prompt = st.text_area(
                "当前提示词（可微调）",
                value=st.session_state.system_prompt,
                height=120,
                help="基于预设模板微调，不影响模板原文",
            )
            st.session_state.system_prompt = system_prompt

    enable_tts = st.checkbox("开启语音播报（TTS）", value=st.session_state.enable_tts)
    st.session_state.enable_tts = enable_tts
    st.markdown("---")

    # RAG 知识库设置
    st.subheader("知识库（RAG）")
    enable_rag = st.checkbox("开启知识库检索", value=st.session_state.enable_rag)
    st.session_state.enable_rag = enable_rag

    if st.session_state.enable_rag:
        # 自动扫描可用领域（vector_db 下的子目录）
        _vdb_root = Path(__file__).parent / "vector_db"
        _available_domains = (
            sorted([d.name for d in _vdb_root.iterdir() if d.is_dir()])
            if _vdb_root.exists()
            else []
        )
        if not _available_domains:
            st.warning("未检测到向量库，请先运行 build_cs_vector_store.py 构建知识库。")
        else:
            rag_domain = st.selectbox(
                "检索领域",
                options=_available_domains,
                index=_available_domains.index(st.session_state.rag_domain)
                if st.session_state.rag_domain in _available_domains
                else 0,
                help="选择要检索的知识领域",
            )
            st.session_state.rag_domain = rag_domain

            rag_top_k = st.slider(
                "检索条数（Top-K）",
                min_value=1,
                max_value=15,
                value=st.session_state.rag_top_k,
                help="返回最相关的 K 条知识片段",
            )
            st.session_state.rag_top_k = rag_top_k

            rag_type_options = ["全部"] + discover_rag_types(Path(__file__).parent / "data" / "cs")
            rag_type_filter = st.selectbox(
                "检索类型（Type）",
                options=rag_type_options,
                index=rag_type_options.index(st.session_state.rag_type_filter)
                if st.session_state.rag_type_filter in rag_type_options
                else 0,
                help="按题目类型过滤，如 coding / playbook / design-case",
            )
            st.session_state.rag_type_filter = rag_type_filter

    st.markdown("---")
    if st.button("新对话", use_container_width=True):
        # 清理上一段 TTS 文件
        old_tts = st.session_state.get("last_tts_path")
        if old_tts and Path(old_tts).exists():
            try:
                Path(old_tts).unlink(missing_ok=True)
            except Exception:
                pass
        st.session_state.history = []
        st.session_state.audio_processed_token = None
        st.session_state.last_tts_path = None
        st.session_state.rag_history = []
        st.session_state.ai_report_text = ""
        st.session_state.report_generating = False
        st.rerun()
    st.markdown("---")
    st.caption("语音输入需浏览器授权麦克风；TTS 为整段播报。")


# -----------------------------------------------------------------------------
# 5. 主区域：四个 Tab — 语音对话 / 文字对话 / RAG 知识检索 / 面试报告
# -----------------------------------------------------------------------------
st.title("AI 面试官")
st.markdown("支持**语音**或**文字**输入，结合**知识库检索（RAG）**与面试官对话。")

tab_voice, tab_chat, tab_rag, tab_report = st.tabs(
    ["🎙️ 语音对话", "💬 文字对话", "📚 RAG 知识检索", "📊 面试报告"]
)

user_input = None

# ---------- Tab 1: 语音对话 ----------
with tab_voice:
    st.markdown("#### 🎙️ 语音面试模式")
    st.caption("录音结束后自动识别并发送，面试官回复自动语音播放")

    audio_value = st.audio_input(
        "点击麦克风开始录音", sample_rate=AUDIO_SAMPLE_RATE or 16000
    )
    if audio_value is not None:
        try:
            raw = audio_value.getvalue()
            token = hash(raw) if raw else id(audio_value)
        except Exception:
            token = id(audio_value)
        if st.session_state.audio_processed_token != token:
            st.session_state.audio_processed_token = token
            temp_wav = TEMP_DIR / f"{uuid4().hex}.wav"
            temp_wav.parent.mkdir(parents=True, exist_ok=True)
            with open(temp_wav, "wb") as f:
                f.write(audio_value.getvalue())
            with st.spinner("正在识别语音..."):
                try:
                    text = run_async(
                        transcribe_file(str(temp_wav), STEPFUN_API_KEY)
                    )
                    if text and text.strip():
                        user_input = text.strip()
                    else:
                        st.warning("未识别到有效内容，请重试。")
                except Exception as e:
                    st.error(f"语音识别失败: {e}")
                finally:
                    try:
                        temp_wav.unlink(missing_ok=True)
                    except Exception:
                        pass
    else:
        st.session_state.audio_processed_token = None

    st.markdown("---")

    # 展示最近几轮对话，保持语音 Tab 简洁
    recent = st.session_state.history[-4:] if st.session_state.history else []
    if recent:
        st.markdown("**最近对话**")
        for msg in recent:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            css_class = "chat-card-user" if role == "user" else "chat-card-assistant"
            st.markdown(
                f'<div class="{css_class}"><p>{content}</p></div>',
                unsafe_allow_html=True,
            )
    else:
        st.info("点击上方麦克风开始语音面试")

    # TTS 自动播放（autoplay=True 无需手动点击播放按钮）
    last_tts = st.session_state.get("last_tts_path")
    if last_tts and Path(last_tts).exists():
        st.audio(last_tts, format="audio/mp3", autoplay=True)

# ---------- Tab 2: 文字对话 ----------
with tab_chat:
    # 完整聊天历史
    chat_container = st.container()
    with chat_container:
        if not st.session_state.history:
            st.info("暂无聊天记录，在下方输入文字开始对话。")
        for msg in st.session_state.history:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            css_class = "chat-card-user" if role == "user" else "chat-card-assistant"
            st.markdown(
                f'<div class="{css_class}"><p>{content}</p></div>',
                unsafe_allow_html=True,
            )

    # 文字输入表单（嵌入 Tab 内部）
    with st.form("chat_form", clear_on_submit=True):
        chat_text = st.text_input(
            "输入消息", placeholder="输入文字与面试官对话...", label_visibility="collapsed"
        )
        send_btn = st.form_submit_button("发送", use_container_width=True)
    if send_btn and chat_text and chat_text.strip():
        user_input = chat_text.strip()

# ---------- Tab 3: RAG 知识检索记录 ----------
with tab_rag:
    if not st.session_state.rag_history:
        st.info("暂无检索记录。开启 RAG 并发送消息后，检索到的知识片段会在此展示。")
    else:
        st.markdown(f"共 **{len(st.session_state.rag_history)}** 条检索记录")
        for idx, item in enumerate(reversed(st.session_state.rag_history), 1):
            query = item.get("query", "")
            content = item.get("retrieved", "")
            domain = item.get("domain", "")
            top_k = item.get("top_k", "")
            type_filter = item.get("type_filter", "全部")
            snippets = [s.strip() for s in content.split("\n") if s.strip()]
            preview_html = ""
            for i, snippet in enumerate(snippets, 1):
                display = snippet[:300] + ("..." if len(snippet) > 300 else "")
                preview_html += f"<div style='margin-bottom:4px'><b>片段 {i}:</b> {display}</div>"
            st.markdown(
                f"""<div class="rag-card">
                    <div class="rag-query">Q: {query}</div>
                    <div class="rag-content">{preview_html}</div>
                    <div class="rag-meta">领域: {domain} · Type: {type_filter} · Top-{top_k} · 共 {len(snippets)} 条片段</div>
                </div>""",
                unsafe_allow_html=True,
            )
            with st.expander(f"查看完整检索内容 #{idx}", expanded=False):
                st.text(content)

# ---------- Tab 4: 面试报告 ----------
with tab_report:
    st.markdown("#### 📊 面试报告")
    st.caption("结束面试后，可下载对话记录或生成 AI 评价报告")

    _history = st.session_state.history
    _msg_count = len(_history)
    _user_count = sum(1 for m in _history if m.get("role") == "user")
    _asst_count = sum(1 for m in _history if m.get("role") == "assistant")

    # --- 对话统计 ---
    st.markdown(f"当前对话：**{_msg_count}** 条消息（候选人 {_user_count} 轮，面试官 {_asst_count} 轮）")
    st.markdown("---")

    # --- 下载对话记录 ---
    st.subheader("下载对话记录")
    if not _history:
        st.info("暂无对话记录，开始面试后即可下载。")
    else:
        dl_col1, dl_col2 = st.columns(2)

        # JSON 格式下载
        with dl_col1:
            history_json = json.dumps(
                _history, ensure_ascii=False, indent=2
            )
            st.download_button(
                label="📥 下载 JSON",
                data=history_json,
                file_name=f"interview_history_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                mime="application/json",
                use_container_width=True,
            )

        # TXT 格式下载（可读的对话记录）
        with dl_col2:
            history_txt = _format_history_for_report(_history)
            st.download_button(
                label="📥 下载 TXT",
                data=history_txt,
                file_name=f"interview_history_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
                mime="text/plain",
                use_container_width=True,
            )

    st.markdown("---")

    # --- AI 面试评价报告 ---
    st.subheader("AI 面试评价报告")

    if not _history:
        st.info("暂无对话记录，面试结束后可生成 AI 评价报告。")
    else:
        if st.button("🤖 生成 AI 面试评价报告", use_container_width=True, type="primary"):
            st.session_state.report_generating = True
            st.session_state.ai_report_text = ""

        # 流式生成报告
        if st.session_state.report_generating:
            report_placeholder = st.empty()
            with st.spinner("Qwen-max 正在深度分析面试表现，请稍候（约 15~30 秒）..."):
                try:
                    for partial_report in ai_report_stream(_history):
                        st.session_state.ai_report_text = partial_report
                        report_placeholder.markdown(partial_report)
                except Exception as e:
                    st.error(f"报告生成失败: {e}")
            st.session_state.report_generating = False
            st.rerun()

        # 展示已生成的报告
        if st.session_state.ai_report_text and not st.session_state.report_generating:
            st.markdown(st.session_state.ai_report_text)

            st.markdown("---")
            # 下载报告
            rpt_col1, rpt_col2 = st.columns(2)
            with rpt_col1:
                st.download_button(
                    label="📥 下载报告（Markdown）",
                    data=st.session_state.ai_report_text,
                    file_name=f"interview_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md",
                    mime="text/markdown",
                    use_container_width=True,
                )
            with rpt_col2:
                # 合并：对话记录 + 报告，一份完整文件
                full_export = (
                    "=" * 60 + "\n"
                    "面试对话记录\n"
                    + "=" * 60 + "\n\n"
                    + _format_history_for_report(_history)
                    + "\n\n"
                    + "=" * 60 + "\n"
                    "AI 面试评价报告\n"
                    + "=" * 60 + "\n\n"
                    + st.session_state.ai_report_text
                )
                st.download_button(
                    label="📥 下载完整记录 + 报告",
                    data=full_export,
                    file_name=f"interview_full_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
                    mime="text/plain",
                    use_container_width=True,
                )

# -----------------------------------------------------------------------------
# 6. 共享处理逻辑：LLM + RAG + TTS
# -----------------------------------------------------------------------------
if user_input:
    st.session_state.history.append({"role": "user", "content": user_input})
    reply_placeholder = st.empty()
    full_response = ""
    with st.spinner("面试官正在思考..."):
        try:
            augmented_system_prompt = st.session_state.system_prompt
            retrieved = ""

            # --- RAG 检索 ---
            if st.session_state.enable_rag:
                persist_dir = str(Path(__file__).parent / "vector_db")
                try:
                    search_filter = None
                    if st.session_state.rag_type_filter != "全部":
                        search_filter = {"type": st.session_state.rag_type_filter.lower()}

                    retrieved = get_retrieved_context(
                        user_input,
                        domain=st.session_state.rag_domain,
                        k=st.session_state.rag_top_k,
                        persist_dir=persist_dir,
                        search_filter=search_filter,
                    )
                except Exception as e:
                    st.warning(f"RAG 检索失败: {e}")
                    retrieved = ""

                if retrieved and retrieved.strip():
                    augmented_system_prompt += (
                        "\n\n参考知识库内容（仅供回答参考）：\n" + retrieved
                    )
                    st.session_state.rag_history.append({
                        "query": user_input,
                        "retrieved": retrieved,
                        "domain": st.session_state.rag_domain,
                        "top_k": st.session_state.rag_top_k,
                        "type_filter": st.session_state.rag_type_filter,
                    })

            for partial in llm_stream_chat(
                st.session_state.history[:-1],
                user_input,
                system_prompt=augmented_system_prompt,
            ):
                full_response = partial
                reply_placeholder.markdown(
                    f'<div class="chat-card-assistant"><p>{full_response}</p></div>',
                    unsafe_allow_html=True,
                )
        except Exception as e:
            full_response = f"抱歉，系统出现了点小故障: {str(e)}"
            reply_placeholder.markdown(
                f'<div class="chat-card-assistant"><p>{full_response}</p></div>',
                unsafe_allow_html=True,
            )
    st.session_state.history.append({"role": "assistant", "content": full_response})

    # TTS：生成语音，语音 Tab 会自动播放
    if st.session_state.enable_tts and full_response and not full_response.startswith("抱歉"):
        with st.spinner("正在生成语音..."):
            tts = TTS_no_stream(STEPFUN_API_KEY)
            temp_mp3 = TEMP_DIR / f"{uuid4().hex}.mp3"
            if tts.to_speech(full_response, str(temp_mp3)):
                old_tts = st.session_state.get("last_tts_path")
                if old_tts and old_tts != str(temp_mp3) and Path(old_tts).exists():
                    try:
                        Path(old_tts).unlink(missing_ok=True)
                    except Exception:
                        pass
                st.session_state.last_tts_path = str(temp_mp3)
            else:
                st.error("语音生成失败，请检查网络或 API 配置。")

    st.rerun()
