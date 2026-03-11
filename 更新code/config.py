"""
配置文件 - 集中管理 API 密钥和系统路径
"""

import os
from pathlib import Path

# ==================== API 密钥配置 ====================
# StepFun API (用于 TTS 和 ASR) - 8 个 Key 轮询
STEPFUN_API_KEYS = [
    os.getenv("STEPFUN_API_KEY_1", "6pZ3jWJGHoMXAcZZpjF3ierYzYDqHEpQLU9gK6auHIWhB1uthsLfqUAnzGLcBiW5x"),
    os.getenv("STEPFUN_API_KEY_2", "3ZrwQrJ6sG8i2AhNs89yejHYABzGnlT6pMpXaVxr1UDb4iSOQBeRzMwotRFXo3vP7"),  # 添加第 2 个 Key
    os.getenv("STEPFUN_API_KEY_3", "4eZ2G2tgOlbaI3MfB54mDuCTpbreWWGjaUtMSTP42IsUHkbS8xkcQ1Zf9hqs6DGlt"),  # 添加第 3 个 Key
    os.getenv("STEPFUN_API_KEY_4", "5FD40mZBI8s0NZx3NfOGpbLVDgWMUCGJwXxoxgxtm6GDpk7agpoRmkYtWTOSLWvCt"),  # 添加第 4 个 Key
    os.getenv("STEPFUN_API_KEY_5", "50yWwsj0tsPglPPudVPGCHuivWP3kukyUTPaMNesmNzolxAOeBl6yktwS66GbUsQ"),  # 添加第 5 个 Key
    os.getenv("STEPFUN_API_KEY_6", "7voYNQ6OdRV78nqvmaNEOTUOsvOr5vQDpf1QsDNWhdFHntWD9V2Dc61Qc9gcVD3Vm"),  # 添加第 6 个 Key
    os.getenv("STEPFUN_API_KEY_7", "63AhrV0IbjdbVbFQVUqqCQJOQSuyJ3n9nUn3LXnNSZdBxKo2JLswf7qIXFEFn3ilp"),  # 添加第 7 个 Key
    os.getenv("STEPFUN_API_KEY_8", "6cqW4gyXcWs2nVypU2jw3p6coQK9ZgG9Cj9UQtU0SrlIFtuwUvRSwimLMniD57t5G"),  # 添加第 8 个 Key
]

# 兼容旧代码（使用第一个 Key）
STEPFUN_API_KEY = STEPFUN_API_KEYS[0]

# 阿里云 DashScope API (用于 LLM)
DASHSCOPE_API_KEY ="sk-af8e9af4aae340bd86178117f7f3f33c" #os.getenv("DASHSCOPE_API_KEY", "sk-af8e9af4aae340bd86178117f7f3f33c")

# ==================== 模型配置 ====================
# LLM 模型
# - qwen-plus: 日常对话、面试问答（性价比高，推荐）
# - qwen-max: 复杂任务（报告生成、深度分析）
LLM_MODEL = "qwen-plus"  # ✅ 修正：实际使用的是 qwen-plus
LLM_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"

# 简历分析专用模型（使用更强的 qwen-plus）
RESUME_ANALYSIS_MODEL = "qwen-plus"

# AI 报告生成模型（使用最强的 qwen-max）
AI_REPORT_MODEL = "qwen-max"  # ✅ 新增配置

# TTS 模型
TTS_MODEL = "step-tts-mini"
TTS_VOICE = "cixingnansheng"  # 磁性男声

# ASR 模型
ASR_MODEL = "step-asr"
# ==================== 路径配置 ====================
# 项目根目录
BASE_DIR = Path(__file__).parent

# 数据目录
DATA_DIR = BASE_DIR / "data"
RAW_KNOWLEDGE_DIR = DATA_DIR / "raw_knowledge"
VECTOR_STORE_DIR = DATA_DIR / "vector_db"  # ✅ 修正：实际使用 vector_db

# 输出目录（如果未使用可以删除）
OUTPUT_DIR = BASE_DIR / "output"
REPORTS_DIR = OUTPUT_DIR / "reports"
VIDEOS_DIR = OUTPUT_DIR / "videos"

# 临时文件目录
TEMP_DIR = BASE_DIR / "temp_audio"

# ==================== 应用配置 ====================
# 音频采样率
AUDIO_SAMPLE_RATE = 16000

# 最大对话轮数
MAX_CONVERSATION_TURNS = 50

# 流式输出延迟（秒）
STREAM_DELAY = 0.01

# ==================== 初始化目录 ====================
def init_directories():
    """创建必要的目录结构"""
    directories = [
        DATA_DIR,
        RAW_KNOWLEDGE_DIR,
        VECTOR_STORE_DIR,
        OUTPUT_DIR,
        REPORTS_DIR,
        VIDEOS_DIR,
        TEMP_DIR
    ]
    
    for directory in directories:
        directory.mkdir(parents=True, exist_ok=True)
    
    print("✅ 目录初始化完成")

# 自动初始化
if __name__ == "__main__":
    init_directories()
