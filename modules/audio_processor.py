# 这里处理 TTS 和 ASR 的 API 调用
# modules/audio_processor.py
from openai import OpenAI
import os
import re
from pathlib import Path
import asyncio
import aiohttp
from typing import Optional, List, Callable
import tempfile
import hashlib
import json
import threading
import queue
import time

# edge-TTS 导入（免费的 Microsoft TTS）
try:
    import edge_tts
    EDGE_TTS_AVAILABLE = True
except ImportError:
    EDGE_TTS_AVAILABLE = False
    print("⚠️ edge-tts 未安装，请运行: pip install edge-tts")

try:
    from config import TTS_MODEL, TTS_VOICE, STEPFUN_API_KEYS
except ImportError:
    TTS_MODEL = "step-tts-mini"
    TTS_VOICE = "cixingnansheng"
    STEPFUN_API_KEYS = []

# 永远不要在代码里写死绝对路径，尤其是带中文的(血的教训)
# 这里保留为空或默认值即可，实际由 app 控制
speech_file_path = "temp_audio_test.mp3"


def _strip_markdown(text: str) -> str:
    """去除文本中的 Markdown 语法符号，保留纯文本供 TTS 朗读。
    
    高鲁棒性设计，按照正确顺序处理以下 Markdown 语法：
    - 代码块（围栏式和缩进式）
    - HTML 标签和注释
    - 图片和链接
    - 标题、加粗、斜体、删除线、高亮
    - 列表、引用、任务列表
    - 表格、分割线、脚注
    - 转义字符等
    """
    if not text:
        return ""
    
    result = text
    
    # ==================== 1. 代码块处理（优先级最高）====================
    # 1.1 围栏式代码块 ```language\ncode\n``` 或 ~~~code~~~
    result = re.sub(r'```[\w-]*\n?[\s\S]*?```', '', result, flags=re.MULTILINE)
    result = re.sub(r'~~~[\w-]*\n?[\s\S]*?~~~', '', result, flags=re.MULTILINE)
    
    # 1.2 行内代码 `code` （保留代码内容，去除反引号）
    result = re.sub(r'`([^`\n]+)`', r'\1', result)
    # 处理双反引号 ``code``
    result = re.sub(r'``([^`]+)``', r'\1', result)
    
    # ==================== 2. HTML 处理 ====================
    # 2.1 HTML 注释 <!-- comment -->
    result = re.sub(r'<!--[\s\S]*?-->', '', result)
    
    # 2.2 HTML 标签（包括自闭合标签）
    result = re.sub(r'<[^>]+/?>', '', result)
    
    # 2.3 HTML 实体转换
    html_entities = {
        '&nbsp;': ' ', '&lt;': '<', '&gt;': '>', '&amp;': '&',
        '&quot;': '"', '&apos;': "'", '&#39;': "'", '&ldquo;': '"',
        '&rdquo;': '"', '&lsquo;': "'", '&rsquo;': "'", '&mdash;': '—',
        '&ndash;': '–', '&hellip;': '…', '&copy;': '©', '&reg;': '®',
        '&trade;': '™', '&times;': '×', '&divide;': '÷',
    }
    for entity, char in html_entities.items():
        result = result.replace(entity, char)
    # 处理数字实体 &#123; 或 &#x1F600;
    result = re.sub(r'&#x?[0-9a-fA-F]+;', '', result)
    
    # ==================== 3. 图片和链接处理 ====================
    # 3.1 图片 ![alt](url) 或 ![alt](url "title") - 保留 alt 文本
    result = re.sub(r'!\[([^\]]*)\]\([^\)]+\)', r'\1', result)
    
    # 3.2 引用式图片 ![alt][ref]
    result = re.sub(r'!\[([^\]]*)\]\[[^\]]*\]', r'\1', result)
    
    # 3.3 链接 [text](url) 或 [text](url "title") - 保留链接文本
    result = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', result)
    
    # 3.4 引用式链接 [text][ref] - 保留链接文本
    result = re.sub(r'\[([^\]]+)\]\[[^\]]*\]', r'\1', result)
    
    # 3.5 自动链接 <url> 或 <email>
    result = re.sub(r'<(https?://[^>]+)>', r'\1', result)
    result = re.sub(r'<([^@>]+@[^>]+)>', r'\1', result)
    
    # 3.6 链接引用定义 [ref]: url "title"（整行删除）
    result = re.sub(r'^\s*\[[^\]]+\]:\s*\S+.*$', '', result, flags=re.MULTILINE)
    
    # ==================== 4. 标题处理 ====================
    # 4.1 ATX 风格标题 # ~ ###### 
    result = re.sub(r'^#{1,6}\s+', '', result, flags=re.MULTILINE)
    # 处理标题末尾的 #
    result = re.sub(r'\s*#+\s*$', '', result, flags=re.MULTILINE)
    
    # 4.2 Setext 风格标题（标题下的 === 或 ---）
    result = re.sub(r'^[=-]{2,}\s*$', '', result, flags=re.MULTILINE)
    
    # ==================== 5. 文本格式化处理 ====================
    # 5.1 加粗+斜体 ***text*** 或 ___text___
    result = re.sub(r'\*{3}([^\*]+)\*{3}', r'\1', result)
    result = re.sub(r'_{3}([^_]+)_{3}', r'\1', result)
    
    # 5.2 加粗 **text** 或 __text__
    result = re.sub(r'\*{2}([^\*]+)\*{2}', r'\1', result)
    result = re.sub(r'_{2}([^_]+)_{2}', r'\1', result)
    
    # 5.3 斜体 *text* 或 _text_（注意不要匹配下划线变量名）
    result = re.sub(r'(?<!\w)\*([^\*\n]+)\*(?!\w)', r'\1', result)
    result = re.sub(r'(?<!\w)_([^_\n]+)_(?!\w)', r'\1', result)
    
    # 5.4 删除线 ~~text~~
    result = re.sub(r'~~([^~]+)~~', r'\1', result)
    
    # 5.5 高亮 ==text==
    result = re.sub(r'==([^=]+)==', r'\1', result)
    
    # 5.6 上标 ^text^ 和下标 ~text~
    result = re.sub(r'\^([^\^]+)\^', r'\1', result)
    result = re.sub(r'~([^~]+)~', r'\1', result)
    
    # 5.7 键盘标签 <kbd>text</kbd>（前面 HTML 已处理，这里兜底）
    result = re.sub(r'<kbd>([^<]+)</kbd>', r'\1', result, flags=re.IGNORECASE)
    
    # ==================== 6. 列表处理 ====================
    # 6.1 无序列表 - * +
    result = re.sub(r'^[\s]*[-*+]\s+', '', result, flags=re.MULTILINE)
    
    # 6.2 有序列表 1. 2. 等
    result = re.sub(r'^[\s]*\d+\.\s+', '', result, flags=re.MULTILINE)
    
    # 6.3 任务列表 - [ ] 或 - [x] 或 - [X]
    result = re.sub(r'\[[ xX]\]\s*', '', result)
    
    # ==================== 7. 引用和缩进 ====================
    # 7.1 块引用 > 
    result = re.sub(r'^[\s]*>+\s*', '', result, flags=re.MULTILINE)
    
    # ==================== 8. 分割线 ====================
    # 8.1 独占一行的分割线 --- *** ___ （标准 Markdown 分割线）
    result = re.sub(r'^[\s]*[-*_]{3,}[\s]*$', '', result, flags=re.MULTILINE)
    # 8.2 行内的分割线（非标准，但 AI 输出中常见）
    result = re.sub(r'\s*-{3,}\s*', ' ', result)
    result = re.sub(r'\s*\*{3,}\s*', ' ', result)
    result = re.sub(r'\s*_{3,}\s*', ' ', result)
    
    # ==================== 9. 表格处理 ====================
    # 9.1 表格分隔行 |---|---|
    result = re.sub(r'^\|?[\s]*[-:]+[\s]*(\|[\s]*[-:]+[\s]*)+\|?$', '', result, flags=re.MULTILINE)
    
    # 9.2 表格内容行：移除首尾的 | 但保留单元格内容
    result = re.sub(r'^\|(.+)\|$', r'\1', result, flags=re.MULTILINE)
    
    # 9.3 单元格分隔符 | 替换为空格
    result = re.sub(r'\|', ' ', result)
    
    # ==================== 10. 脚注处理 ====================
    # 10.1 脚注引用 [^1] [^note]
    result = re.sub(r'\[\^[^\]]+\]', '', result)
    
    # 10.2 脚注定义 [^1]: content
    result = re.sub(r'^\[\^[^\]]+\]:\s*', '', result, flags=re.MULTILINE)
    
    # ==================== 11. 特殊语法 ====================
    # 11.1 数学公式 $...$ 或 $$...$$
    result = re.sub(r'\$\$[\s\S]+?\$\$', '', result)
    result = re.sub(r'\$[^\$\n]+\$', '', result)
    
    # 11.2 缩写定义 *[abbr]: full text
    result = re.sub(r'^\*\[[^\]]+\]:\s*.*$', '', result, flags=re.MULTILINE)
    
    # 11.3 定义列表
    result = re.sub(r'^:\s+', '', result, flags=re.MULTILINE)
    
    # ==================== 12. 转义字符处理（最后处理）====================
    # 移除 Markdown 转义的反斜杠
    escape_chars = r'\`*_{}[]()#+-.!|~^'
    for char in escape_chars:
        result = result.replace(f'\\{char}', char)
    
    # ==================== 13. 清理空白 ====================
    # 13.1 移除多余的空行（超过2个连续空行变为1个）
    result = re.sub(r'\n{3,}', '\n\n', result)
    
    # 13.2 移除行首行尾多余空格
    result = '\n'.join(line.strip() for line in result.split('\n'))
    
    # 13.3 移除多余空格（多个空格变为1个）
    result = re.sub(r'[ \t]+', ' ', result)
    
    # 13.4 最终清理
    result = result.strip()
    
    return result


class APIKeyRotator:
    """
    API Key 轮询管理器
    管理多个 API Key，自动轮换以避免限流
    """
    
    def __init__(self, api_keys: List[str], min_interval: float = 1.5, max_concurrent: int = 4):
        """
        api_keys: API Key 列表
        min_interval: 每个 Key 的最小调用间隔（秒），默认 1.5 秒（激进优化）
        max_concurrent: 最大并发请求数，默认 4 个同时请求
        """
        self.api_keys = [key for key in api_keys if key]  # 过滤空 Key
        if not self.api_keys:
            raise ValueError("至少需要一个有效的 API Key")
        
        self.min_interval = min_interval  # 优化：每个 Key 只需间隔 1.5 秒
        self.max_concurrent = max_concurrent  # 优化：允许 4 个并发
        self.last_call_time = {key: 0.0 for key in self.api_keys}
        self.current_index = 0
        self.concurrent_count = 0  # 当前并发数
        self.lock = threading.Lock()
    
    def get_next_key(self) -> str:
        """
        获取下一个可用的 API Key
        优化：支持并发请求，减少等待时间
        """
        with self.lock:
            current_time = time.time()
            
            # 优化：如果当前并发数未达到上限，允许并发
            if self.concurrent_count < self.max_concurrent:
                # 找最早调用的 Key（即使还在冷却中也可以复用）
                earliest_key = min(
                    self.api_keys,
                    key=lambda k: self.last_call_time[k]
                )
                self.last_call_time[earliest_key] = current_time
                self.concurrent_count += 1
                return earliest_key
            
            # 达到并发上限，轮询查找可用的 Key
            for i in range(len(self.api_keys)):
                idx = (self.current_index + i) % len(self.api_keys)
                key = self.api_keys[idx]
                
                # 检查是否可用（距离上次调用 >= min_interval）
                if current_time - self.last_call_time[key] >= self.min_interval:
                    self.last_call_time[key] = current_time
                    self.current_index = (idx + 1) % len(self.api_keys)
                    self.concurrent_count += 1
                    return key
            
            # 所有 Key 都在冷却中，返回最早可用的 Key
            earliest_key = min(
                self.api_keys,
                key=lambda k: self.last_call_time[k]
            )
            self.last_call_time[earliest_key] = current_time
            self.current_index = (self.api_keys.index(earliest_key) + 1) % len(self.api_keys)
            self.concurrent_count += 1
            return earliest_key
    
    def release_key(self):
        """释放一个 Key（并发计数减 1）"""
        with self.lock:
            if self.concurrent_count > 0:
                self.concurrent_count -= 1
    
    def get_stats(self) -> dict:
        """获取统计信息"""
        current_time = time.time()
        return {
            "total_keys": len(self.api_keys),
            "current_index": self.current_index,
            "cooldown_status": {
                key: max(0, self.min_interval - (current_time - t))
                for key, t in self.last_call_time.items()
            }
        }


class TTSCache:
    """TTS 缓存管理类"""
    def __init__(self, cache_dir: str = None):
        self.cache_dir = Path(cache_dir) if cache_dir else Path(tempfile.gettempdir()) / "tts_cache"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.cache_index_file = self.cache_dir / "cache_index.json"
        self.cache_index = self._load_cache_index()
    
    def _load_cache_index(self) -> dict:
        """加载缓存索引"""
        if self.cache_index_file.exists():
            with open(self.cache_index_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {}
    
    def _save_cache_index(self):
        """保存缓存索引"""
        with open(self.cache_index_file, 'w', encoding='utf-8') as f:
            json.dump(self.cache_index, f, ensure_ascii=False, indent=2)
    
    def _get_text_hash(self, text: str) -> str:
        """获取文本的哈希值"""
        return hashlib.md5(text.encode('utf-8')).hexdigest()
    
    def get(self, text: str) -> Optional[str]:
        """从缓存获取音频文件路径"""
        text_hash = self._get_text_hash(text)
        if text_hash in self.cache_index:
            audio_path = self.cache_dir / f"{text_hash}.mp3"
            if audio_path.exists():
                return str(audio_path)
            else:
                del self.cache_index[text_hash]
                self._save_cache_index()
        return None
    
    def set(self, text: str, audio_path: str):
        """将音频文件添加到缓存"""
        text_hash = self._get_text_hash(text)
        cache_audio_path = self.cache_dir / f"{text_hash}.mp3"
        
        import shutil
        shutil.copy2(audio_path, cache_audio_path)
        
        self.cache_index[text_hash] = {
            "text": text[:100],  # 只保存前100个字符
            "created_at": str(asyncio.get_event_loop().time() if asyncio.get_event_loop().is_running() else 0)
        }
        self._save_cache_index()
        
        return str(cache_audio_path)
    
    def clear_old_cache(self, max_age_hours: int = 24):
        """清理过期缓存"""
        import time
        current_time = time.time()
        max_age_seconds = max_age_hours * 3600
        
        for text_hash, info in list(self.cache_index.items()):
            created_at = float(info.get('created_at', 0))
            if current_time - created_at > max_age_seconds:
                audio_path = self.cache_dir / f"{text_hash}.mp3"
                if audio_path.exists():
                    audio_path.unlink()
                del self.cache_index[text_hash]
        
        self._save_cache_index()


class TTS_async:
    """异步 TTS 类，支持非阻塞调用和缓存"""
    
    _cache = None  # 类级别的缓存实例
    _rotator = None  # 类级别的 API Key 轮询器
    
    @classmethod
    def get_cache(cls) -> TTSCache:
        """获取缓存实例（单例模式）"""
        if cls._cache is None:
            cls._cache = TTSCache()
        return cls._cache
    
    @classmethod
    def get_rotator(cls) -> APIKeyRotator:
        """获取 API Key 轮询器（单例模式）"""
        if cls._rotator is None:
            # 优化：将最小间隔从 6.0 秒降低到 3.0 秒，提升响应速度
            cls._rotator = APIKeyRotator(STEPFUN_API_KEYS, min_interval=3.0)
        return cls._rotator
    
    def __init__(self, model=None, voice=None):
        # api_key 由轮询器自动管理，不需要手动指定
        self.model = model or TTS_MODEL
        self.default_voice = voice or TTS_VOICE
        self.base_url = "https://api.stepfun.com/v1"
        self.rotator = self.get_rotator()
    
    async def to_speech_async(self, text: str, output_path: str, use_cache: bool = True) -> tuple[bool, str]:
        """
        异步生成语音
        返回: (成功标志, 音频文件路径)
        """
        try:
            clean_text = _strip_markdown(text)
            
            # 检查缓存
            if use_cache:
                cache = self.get_cache()
                cached_audio = cache.get(clean_text)
                if cached_audio:
                    import shutil
                    shutil.copy2(cached_audio, output_path)
                    return True, output_path
            
            # 异步 API 调用（使用轮询的 API Key）
            async with aiohttp.ClientSession() as session:
                # 如果没有指定 api_key，从轮询器获取
                current_api_key = self.rotator.get_next_key()
                
                try:
                    headers = {
                        "Authorization": f"Bearer {current_api_key}",
                        "Content-Type": "application/json"
                    }
                    
                    data = {
                        "model": self.model,
                        "voice": self.default_voice,
                        "input": clean_text,
                        "volume": 1.0,
                        "speed": 1.2,  # 优化：语速提升 20%，减少等待时间
                        "voice_label": {"style": "快速"}
                    }
                    
                    async with session.post(
                        f"{self.base_url}/audio/speech",
                        headers=headers,
                        json=data,
                        timeout=aiohttp.ClientTimeout(total=30, connect=10)  # 优化：总超时 30 秒，连接 10 秒
                    ) as response:
                        
                        if response.status == 200:
                            audio_content = await response.read()
                            
                            # 异步写入文件
                            await asyncio.to_thread(self._write_file, output_path, audio_content)
                            
                            # 添加到缓存
                            if use_cache:
                                cache = self.get_cache()
                                cache.set(clean_text, output_path)
                            
                            return True, output_path
                        else:
                            error_text = await response.text()
                            print(f"❌ TTS API 错误 ({response.status}): {error_text}")
                            return False, ""
                finally:
                    # 🚀 关键：释放 API Key（并发计数减 1）
                    self.rotator.release_key()
                        
        except asyncio.TimeoutError:
            print("❌ TTS 请求超时")
            # 🚀 关键：异常时也要释放 API Key
            if hasattr(self, 'rotator'):
                self.rotator.release_key()
            return False, ""
        except Exception as e:
            print(f"❌ TTS 生成错误：{type(e).__name__} - {e}")
            # 🚀 关键：异常时也要释放 API Key
            if hasattr(self, 'rotator'):
                self.rotator.release_key()
            return False, ""
    
    def _write_file(self, path: str, content: bytes):
        """同步写入文件"""
        with open(path, "wb") as f:
            f.write(content)


# ==================== Edge-TTS 实现（免费方案）====================

# Edge-TTS 可用的中文声音列表
EDGE_TTS_VOICES = {
    "zh-CN-YunjianNeural": "云健（男声，沉稳磁性，推荐）",
    "zh-CN-YunxiNeural": "云希（男声，年轻活泼）",
    "zh-CN-YunyangNeural": "云扬（男声，新闻播报风格）",
    "zh-CN-XiaoxiaoNeural": "晓晓（女声，甜美活泼）",
    "zh-CN-XiaoyiNeural": "晓伊（女声，温柔亲切）",
    "zh-CN-XiaochenNeural": "晓辰（女声，温暖）",
}

# 默认使用的 edge-TTS 声音
EDGE_TTS_DEFAULT_VOICE = "zh-CN-YunjianNeural"


class EdgeTTS_async:
    """
    基于 edge-TTS 的异步 TTS 类
    免费、无需 API Key、延迟更低
    """
    
    _cache = None  # 类级别的缓存实例（与 StepFun 共享缓存类，但独立实例）
    
    @classmethod
    def get_cache(cls) -> TTSCache:
        """获取缓存实例（单例模式）"""
        if cls._cache is None:
            cls._cache = TTSCache(cache_dir=str(Path(tempfile.gettempdir()) / "edge_tts_cache"))
        return cls._cache
    
    def __init__(self, voice: str = None, rate: str = "+20%", volume: str = "+0%"):
        """
        初始化 Edge-TTS
        
        参数:
            voice: 声音名称，默认 zh-CN-YunjianNeural（磁性男声）
            rate: 语速，如 "+20%"（加快20%）、"-10%"（减慢10%）
            volume: 音量，如 "+0%"、"+10%"
        """
        if not EDGE_TTS_AVAILABLE:
            raise ImportError("edge-tts 未安装，请运行: pip install edge-tts")
        
        self.voice = voice or EDGE_TTS_DEFAULT_VOICE
        self.rate = rate
        self.volume = volume
    
    async def to_speech_async(self, text: str, output_path: str, use_cache: bool = True) -> tuple[bool, str]:
        """
        异步生成语音
        返回: (成功标志, 音频文件路径)
        """
        try:
            clean_text = _strip_markdown(text)
            
            if not clean_text.strip():
                print("⚠️ 文本为空，跳过 TTS")
                return False, ""
            
            # 检查缓存
            if use_cache:
                cache = self.get_cache()
                cached_audio = cache.get(clean_text)
                if cached_audio:
                    import shutil
                    shutil.copy2(cached_audio, output_path)
                    return True, output_path
            
            # 使用 edge-TTS 生成语音
            communicate = edge_tts.Communicate(
                text=clean_text,
                voice=self.voice,
                rate=self.rate,
                volume=self.volume
            )
            
            await communicate.save(output_path)
            
            # 验证文件是否生成成功
            if Path(output_path).exists() and Path(output_path).stat().st_size > 0:
                # 添加到缓存
                if use_cache:
                    cache = self.get_cache()
                    cache.set(clean_text, output_path)
                return True, output_path
            else:
                print(f"❌ Edge-TTS 生成失败：文件为空或不存在")
                return False, ""
                
        except Exception as e:
            print(f"❌ Edge-TTS 生成错误：{type(e).__name__} - {e}")
            return False, ""
    
    @staticmethod
    def list_voices() -> dict:
        """返回可用的中文声音列表"""
        return EDGE_TTS_VOICES
    
    @staticmethod
    async def list_all_voices() -> List[dict]:
        """异步获取所有可用声音（包括其他语言）"""
        if not EDGE_TTS_AVAILABLE:
            return []
        voices = await edge_tts.list_voices()
        return voices


class EdgeStreamingTTSManager:
    """
    基于 edge-TTS 的流式 TTS 管理器
    与 StreamingTTSManager 接口兼容，但使用免费的 edge-TTS
    """
    
    def __init__(self, voice: str = None, rate: str = "+20%", cache: bool = True, num_workers: int = 4):
        """
        初始化 Edge-TTS 流式管理器
        
        参数:
            voice: 声音名称
            rate: 语速
            cache: 是否启用缓存
            num_workers: 并发工作线程数
        """
        self.voice = voice or EDGE_TTS_DEFAULT_VOICE
        self.rate = rate
        self.use_cache = cache
        self.num_workers = num_workers
        
        # TTS 实例
        self.tts_async = EdgeTTS_async(voice=voice, rate=rate)
        
        # 句子队列（使用 PriorityQueue 支持插队）
        self.sentence_queue = queue.PriorityQueue()
        
        # 完成的音频队列
        self.completed_queue = queue.Queue()
        
        # 已处理的句子集合
        self.processed_sentences = set()
        
        # 计数器
        self.sentence_counter = 0
        self.completed_counter = 0
        self.counter_lock = threading.Lock()
        
        # 音频文件列表
        self.audio_files = []
        
        # 后台线程控制
        self.worker_threads = []
        self.stop_worker = False
        
        # 缓冲文本
        self.buffer = ""
    
    def extract_complete_sentences(self, text: str) -> tuple[List[str], str]:
        """从文本中提取完整的句子"""
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
    
    def add_text(self, text: str, is_first_sentence_priority: bool = True):
        """添加新的文本片段"""
        self.buffer += text
        sentences, self.buffer = self.extract_complete_sentences(self.buffer)
        
        for sentence in sentences:
            if sentence not in self.processed_sentences:
                self.processed_sentences.add(sentence)
                self.sentence_counter += 1
                
                if is_first_sentence_priority and len(self.processed_sentences) == 1:
                    self.sentence_queue.put((0, self.sentence_counter, sentence))
                    print(f"⚡ [Edge-TTS] 第一句插队：{sentence[:30]}...")
                else:
                    self.sentence_queue.put((1, self.sentence_counter, sentence))
    
    def flush(self):
        """强制处理缓冲区剩余文本"""
        if self.buffer.strip():
            clean_sentence = _strip_markdown(self.buffer.strip())
            if clean_sentence and clean_sentence not in self.processed_sentences:
                self.processed_sentences.add(clean_sentence)
                self.sentence_counter += 1
                self.sentence_queue.put((1, self.sentence_counter, clean_sentence))
            self.buffer = ""
    
    def _worker(self):
        """后台工作线程"""
        temp_dir = Path(tempfile.gettempdir()) / "edge_streaming_tts"
        temp_dir.mkdir(parents=True, exist_ok=True)
        
        print(f"🎙️ [Edge-TTS] 工作线程启动")
        
        while not self.stop_worker:
            try:
                try:
                    priority, counter, sentence = self.sentence_queue.get(timeout=1.0)
                except queue.Empty:
                    continue
                
                priority_mark = "⚡" if priority == 0 else "🔤"
                print(f"{priority_mark} [Edge-TTS] 处理句子：{sentence[:30]}...")
                
                audio_path = temp_dir / f"{hashlib.md5(sentence.encode()).hexdigest()}.mp3"
                
                # 检查缓存
                if self.use_cache:
                    cached = self.tts_async.get_cache().get(sentence)
                    if cached and Path(cached).exists():
                        import shutil
                        shutil.copy2(cached, str(audio_path))
                        self.completed_queue.put((counter, sentence, str(audio_path)))
                        self.audio_files.append(str(audio_path))
                        with self.counter_lock:
                            self.completed_counter += 1
                        print(f"✅ [Edge-TTS] 使用缓存 #{counter}: {sentence[:30]}...")
                        continue
                
                # 生成语音
                success, audio_path_str = asyncio.run(
                    self.tts_async.to_speech_async(sentence, str(audio_path), use_cache=False)
                )
                
                if success and audio_path_str:
                    self.audio_files.append(audio_path_str)
                    self.completed_queue.put((counter, sentence, audio_path_str))
                    with self.counter_lock:
                        self.completed_counter += 1
                    print(f"✅ [Edge-TTS] 生成完成 #{counter}: {sentence[:30]}...")
                else:
                    with self.counter_lock:
                        self.completed_counter += 1
                    print(f"❌ [Edge-TTS] 生成失败：{sentence[:30]}...")
                
            except Exception as e:
                print(f"❌ [Edge-TTS] 工作线程错误：{e}")
                import traceback
                traceback.print_exc()
        
        print(f"🛑 [Edge-TTS] 工作线程停止")
    
    def start(self):
        """启动后台工作线程"""
        self.stop_worker = False
        self.worker_threads = []
        
        for i in range(self.num_workers):
            thread = threading.Thread(target=self._worker, daemon=True)
            thread.start()
            self.worker_threads.append(thread)
        
        print(f"🚀 [Edge-TTS] 启动 {self.num_workers} 个工作线程")
    
    def stop(self):
        """停止后台工作线程"""
        self.stop_worker = True
        for thread in self.worker_threads:
            thread.join(timeout=2.0)
        self.worker_threads = []
    
    def reset(self):
        """重置管理器状态"""
        self.buffer = ""
        self.processed_sentences.clear()
        self.audio_files.clear()
        self.sentence_counter = 0
        self.completed_counter = 0
        while not self.sentence_queue.empty():
            try:
                self.sentence_queue.get_nowait()
            except queue.Empty:
                break
    
    def get_total_sentences(self) -> int:
        """获取已提交的句子总数"""
        return self.sentence_counter
    
    def get_completed_count(self) -> int:
        """获取已完成处理的句子数"""
        with self.counter_lock:
            return self.completed_counter
    
    def is_all_completed(self) -> bool:
        """检查是否所有句子都已处理完成"""
        with self.counter_lock:
            return self.completed_counter >= self.sentence_counter and self.sentence_queue.empty()


class StreamingTTSManager:
    """
    流式 TTS 管理器 - 真正的边生成边播放
    实时检测 LLM 流式输出中的标点符号，每遇到一句就立即生成并播放语音
    """
    
    def __init__(self, model=None, voice=None, cache=True, num_workers=4):
        self.model = model or TTS_MODEL
        self.voice = voice or TTS_VOICE
        self.use_cache = cache
        self.num_workers = num_workers  # 优化：4 个 worker 线程并发
        
        # TTS 实例（不传入 api_key，使用轮询器）
        self.tts_async = TTS_async(model=model, voice=voice)
        
        # 句子队列（优化：使用 PriorityQueue 支持插队）
        self.sentence_queue = queue.PriorityQueue()
        
        # 完成的音频队列（线程安全，用于传递到主线程）
        self.completed_queue = queue.Queue()
        
        # 已处理的句子集合（避免重复）
        self.processed_sentences = set()
        
        # 计数器（用于优先级队列排序）
        self.sentence_counter = 0
        
        # 🚀 新增：已完成计数器（线程安全）
        self.completed_counter = 0
        self.counter_lock = threading.Lock()
        
        # 音频文件列表
        self.audio_files = []
        
        # 后台线程控制
        self.worker_threads = []  # 优化：支持多个 worker 线程
        self.stop_worker = False
        
        # 当前缓冲文本
        self.buffer = ""
    
    def extract_complete_sentences(self, text: str) -> tuple[List[str], str]:
        """
        从文本中提取完整的句子（以标点符号结尾）
        返回：(完整句子列表，剩余文本)
        """
        # 标点符号：。！？.!?
        punc_pattern = r'([。！？.!?])'
        
        # 分割文本
        parts = re.split(punc_pattern, text)
        
        sentences = []
        i = 0
        while i < len(parts) - 1:
            sentence = parts[i].strip()
            punctuation = parts[i + 1]
            
            if sentence:
                # 过滤 Markdown
                clean_sentence = _strip_markdown(sentence + punctuation)
                if clean_sentence.strip():
                    sentences.append(clean_sentence)
            
            i += 2
        
        # 返回剩余部分（没有标点的部分，继续缓冲）
        remaining = parts[-1].strip() if len(parts) % 2 == 1 else ""
        
        return sentences, remaining
    
    def add_text(self, text: str, is_first_sentence_priority=True):
        """
        添加新的文本片段（来自 LLM 流式输出）
        自动检测并提取完整句子
        
        参数:
            text: 要添加的文本
            is_first_sentence_priority: 第一句是否使用高优先级（插队）
        """
        # 添加到缓冲区
        self.buffer += text
        
        # 提取完整句子
        sentences, self.buffer = self.extract_complete_sentences(self.buffer)
        
        # 将完整句子加入队列
        for sentence in sentences:
            if sentence not in self.processed_sentences:
                self.processed_sentences.add(sentence)
                self.sentence_counter += 1
                
                # 🚀 优化：第一句使用高优先级（priority=0），其他句子正常顺序（priority=1）
                if is_first_sentence_priority and len(self.processed_sentences) == 1:
                    # 第一句插队：priority=0
                    self.sentence_queue.put((0, self.sentence_counter, sentence))
                    print(f"⚡ 第一句插队：{sentence[:30]}...")
                else:
                    # 其他句子正常排队：priority=1
                    self.sentence_queue.put((1, self.sentence_counter, sentence))
    
    def flush(self):
        """
        强制处理缓冲区中剩余的文本（没有标点结尾的部分）
        通常在 LLM 完全返回后调用
        """
        if self.buffer.strip():
            clean_sentence = _strip_markdown(self.buffer.strip())
            if clean_sentence and clean_sentence not in self.processed_sentences:
                self.processed_sentences.add(clean_sentence)
                self.sentence_counter += 1
                # 剩余句子正常排队
                self.sentence_queue.put((1, self.sentence_counter, clean_sentence))
            self.buffer = ""
    
    def _worker(self):
        """
        后台工作线程：从队列中取出句子并生成语音
        """
        temp_dir = Path(tempfile.gettempdir()) / "streaming_tts"
        temp_dir.mkdir(parents=True, exist_ok=True)
        
        print(f"🎙️ TTS 工作线程启动")
        
        while not self.stop_worker:
            try:
                # 从队列获取句子（阻塞，最多等待 1 秒）
                try:
                    priority, counter, sentence = self.sentence_queue.get(timeout=1.0)
                except queue.Empty:
                    continue
                
                # 根据优先级显示不同标记
                priority_mark = "⚡" if priority == 0 else "🔤"
                print(f"{priority_mark} 处理句子：{sentence[:30]}...")
                
                # 生成音频文件名
                audio_path = temp_dir / f"{hashlib.md5(sentence.encode()).hexdigest()}.mp3"
                
                # 检查缓存
                if self.use_cache:
                    cached = self.tts_async.get_cache().get(sentence)
                    if cached and Path(cached).exists():
                        # 使用缓存（不消耗 API 配额）
                        import shutil
                        shutil.copy2(cached, str(audio_path))
                        # 将音频路径放入完成队列（线程安全，带上 counter 保证顺序）
                        self.completed_queue.put((counter, sentence, str(audio_path)))
                        self.audio_files.append(str(audio_path))
                        # 🚀 增加完成计数器
                        with self.counter_lock:
                            self.completed_counter += 1
                        print(f"✅ 使用缓存 #{counter}: {sentence[:30]}...")
                        continue
                
                # 生成语音（同步调用，因为已经在后台线程中）
                success, audio_path = asyncio.run(
                    self.tts_async.to_speech_async(sentence, str(audio_path), use_cache=False)
                )
                
                if success and audio_path:
                    self.audio_files.append(audio_path)
                    # 将音频路径放入完成队列（线程安全，带上 counter 保证顺序）
                    self.completed_queue.put((counter, sentence, audio_path))
                    # 🚀 增加完成计数器
                    with self.counter_lock:
                        self.completed_counter += 1
                    print(f"✅ 生成完成 #{counter}: {sentence[:30]}... -> {audio_path}")
                else:
                    # 🚀 失败时也要增加完成计数器（表示已处理）
                    with self.counter_lock:
                        self.completed_counter += 1
                    print(f"❌ 生成失败：{sentence[:30]}...")
                
            except Exception as e:
                print(f"❌ TTS 工作线程错误：{e}")
                import traceback
                traceback.print_exc()
        
        print(f"🛑 TTS 工作线程停止")
    
    def start(self):
        """启动后台工作线程（多个 worker 并发）"""
        self.stop_worker = False
        self.worker_threads = []
        
        # 优化：启动多个 worker 线程
        for i in range(self.num_workers):
            thread = threading.Thread(target=self._worker, daemon=True)
            thread.start()
            self.worker_threads.append(thread)
        
        print(f"🚀 启动 {self.num_workers} 个 TTS 工作线程")
    
    def stop(self):
        """停止后台工作线程"""
        self.stop_worker = True
        # 等待所有线程结束
        for thread in self.worker_threads:
            thread.join(timeout=2.0)
        self.worker_threads = []
    
    def reset(self):
        """重置管理器状态"""
        self.buffer = ""
        self.processed_sentences.clear()
        self.audio_files.clear()
        self.sentence_counter = 0
        self.completed_counter = 0  # 🚀 重置完成计数器
        while not self.sentence_queue.empty():
            try:
                self.sentence_queue.get_nowait()
            except queue.Empty:
                break
    
    def get_total_sentences(self) -> int:
        """🚀 获取已提交的句子总数"""
        return self.sentence_counter
    
    def get_completed_count(self) -> int:
        """🚀 获取已完成处理的句子数"""
        with self.counter_lock:
            return self.completed_counter
    
    def is_all_completed(self) -> bool:
        """🚀 检查是否所有句子都已处理完成"""
        with self.counter_lock:
            return self.completed_counter >= self.sentence_counter and self.sentence_queue.empty()

#asr
async def audio_to_text(audio_file_path: str, api_key: str) -> Optional[str]:
    """异步语音转文本"""
    try:
        # 异步读取文件
        audio_data = await asyncio.to_thread(_read_file, audio_file_path)
        if not audio_data:
            return None
        
        # 准备请求
        data = aiohttp.FormData()
        data.add_field('model', 'step-asr')
        data.add_field('file', audio_data, 
                      filename=os.path.basename(audio_file_path),
                      content_type='audio/wav')
        data.add_field('language', 'zh')
        
        # 异步API请求
        async with aiohttp.ClientSession() as session:
            headers = {"Authorization": f"Bearer {api_key}"}
            
            async with session.post(
                "https://api.stepfun.com/v1/audio/transcriptions",
                headers=headers,
                data=data,
                timeout=aiohttp.ClientTimeout(total=30)
            ) as response:
                
                if response.status == 200:
                    result = await response.json()
                    return result.get('text', '').strip()
                else:
                    print(f"API错误: {response.status}")
                    return None
                    
    except Exception as e:
        print(f"转换错误: {e}")
        return None

def _read_file(path: str) -> Optional[bytes]:
    """同步读取文件"""
    try:
        with open(path, 'rb') as f:
            return f.read()
    except Exception as e:
        print(f"读取文件失败 {path}: {e}")
        return None


async def transcribe_file(file_path: str, api_key: str) -> Optional[str]:
    """转录已有音频文件"""
    if not os.path.exists(file_path):
        print(f"文件不存在：{file_path}")
        return None
    
    print(f"处理文件：{file_path}")
    return await audio_to_text(file_path, api_key)
