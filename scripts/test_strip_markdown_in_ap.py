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

import re

string='**这是加粗文本**，这是普通文本，*这是斜体文本*，这是普通文本，`这是行内代码`，这是普通文本，> 这是引用文本，- 这是无序列表项，1. 这是有序列表项，![图片](url)，[链接文本](url)，$$E=mc^2$$，$a^2+b^2=c^2$，\\frac{1}{2}，x_i，y^2'
print(_strip_markdown(string))

ai_output_test='**题目：合并K个升序链表**  给你一个链表数组，每个链表都已经按升序排列。  请你将所有链表合并到一个升序链表中，返回合并后的链表。  **示例：**  输入：`lists = [[1,4,5],[1,3,4],[2,6]]`  输出：`[1,1,2,3,4,4,5,6]`  **链表定义（Python）：**  ```pythonclass ListNode:    def __init__(self, val=0, next=None):        self.val = val        self.next = next```**函数签名：**  ```pythondef mergeKLists(lists: List[Optional[ListNode]]) -> Optional[ListNode]:```---**现在，请你先澄清题目细节。**（如果有任何边界条件、输入范围等问题，请提出来。如果没有，可以直接进入下一步。）' 
print(_strip_markdown(ai_output_test))