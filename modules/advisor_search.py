"""
导师信息搜索模块
使用 DashScope OpenAI 兼容模式的联网搜索功能
支持两阶段搜索 + 优先级分组 + 渐进显示 + 多API Key并行
"""

import asyncio
from openai import OpenAI

try:
    from config import DASHSCOPE_API_KEYS, DASHSCOPE_API_KEY
except ImportError:
    DASHSCOPE_API_KEYS = ["sk-af8e9af4aae340bd86178117f7f3f33c"]
    DASHSCOPE_API_KEY = DASHSCOPE_API_KEYS[0]

class APIKeyManager:
    """API Key 轮询管理器"""
    def __init__(self, keys):
        self.keys = keys if keys else [DASHSCOPE_API_KEY]
        self.index = 0
    
    def get_next_key(self):
        """获取下一个 API Key"""
        key = self.keys[self.index % len(self.keys)]
        self.index += 1
        return key
    
    def get_client(self, key_index=None):
        """获取 OpenAI 客户端"""
        if key_index is not None:
            key = self.keys[key_index % len(self.keys)]
        else:
            key = self.get_next_key()
        return OpenAI(
            api_key=key,
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1"
        )

key_manager = APIKeyManager(DASHSCOPE_API_KEYS)

SEARCH_SOURCE_HINT = """
【推荐搜索来源】
1. {school}官网/学院教师主页
2. Google Scholar（搜索"{advisor}"）
3. DBLP数据库（计算机领域）
4. 中国知网CNKI（中文论文）
5. 实验室官网/团队主页
6. ResearchGate
7. 学术搜索引擎（百度学术、必应学术）
8. 学校研究生院网站
9. 学生经验分享平台（小红书、知乎、B站、豆瓣、CSDN）
10. 其他公开平台（如：LinkedIn、个人博客）

【注意】信任小红书、知乎、B站等平台的学生经验贴（如"XX组面试回忆"）。
"""

VERIFY_PROMPT = """请确认{school}是否存在名为"{advisor}"的导师/教师：

{source_hint}

【任务】
1. 在学校官网教师名录中查找
2. 在学术数据库中搜索该导师的论文
3. 在知乎、小红书等平台搜索学生经验贴
4. 确认该导师的基本身份（职称、院系）

【返回格式】
如果找到，返回：
- 职称（教授/副教授/讲师等）
- 所在院系
- 主要研究方向（1-2个关键词）

如果确实不存在，返回：未找到该导师信息

注意：不要编造，不确定就写"无法确认"。"""


SEARCH_ASPECTS = {
    "p1": [
        {
            "key": "research_direction",
            "name": "研究方向",
            "prompt": """联网搜索{school} {advisor}导师的研究方向，要求返回具体事实：

{source_hint}

【搜索关键词建议】
- "{advisor} {school} 研究方向"
- "{advisor} 论文"
- "{advisor} Google Scholar"

【必须包含】
1. 具体研究方向名称（如：数据挖掘、推荐系统、NLP等）
2. 代表性论文标题（至少1-2篇，带发表年份）
3. 具体研究关键词（3-5个）

【禁止】
- 使用"主要从事""研究方向包括"等套话开头
- 编造不存在的论文
- 使用模糊表述

【格式】直接列出事实，不要总分结构，80字以内。如果找不到具体论文，可以只写研究方向和关键词。"""
        },
        {
            "key": "recruitment_preference",
            "name": "招生偏好",
            "prompt": """联网搜索{school} {advisor}导师的招生偏好，要求返回具体事实：

{source_hint}

【搜索关键词建议】
- "{advisor} {school} 招生"
- "{advisor} 招生要求"
- "{school} {advisor} 研究生"
- "{advisor} 面试经验 知乎"
- "{advisor} 面试 小红书"

【必须包含】
1. 对学生背景的具体要求（如：本科学校层次、专业背景）
2. 面试考察的具体内容（如：会问什么类型问题）
3. 加分项（如：有论文/竞赛/项目经历优先）
4. 学生经验贴参考（如有，注明来源如"知乎用户分享"）

【禁止】
- 编造不存在的要求
- 使用模糊表述

【格式】直接列出事实，80字以内。如果找不到具体信息，根据导师研究方向给出建议，如"建议提前阅读导师论文，准备研究方向相关问题，展示科研潜力"。"""
        }
    ],
    "p2": [
        {
            "key": "academic_style",
            "name": "学术风格",
            "prompt": """联网搜索{school} {advisor}导师的学术风格，要求返回具体事实：

{source_hint}

【搜索关键词建议】
- "{advisor} {school} 实验室"
- "{advisor} 论文发表"
- "{advisor} 研究组"
- "{advisor} 导师评价 知乎"
- "{advisor} 实验室 小红书"

【必须包含】
1. 偏理论还是偏工程（必须有明确判断依据）
2. 对学生的具体要求（如：每周组会、代码量要求）
3. 实验室具体产出（如：年均论文数、主要发表期刊/会议）
4. 学生评价参考（如有，注明来源如"知乎用户分享"）

【禁止】
- 编造不存在的信息
- 使用模糊表述

【格式】直接列出事实，80字以内。如果找不到具体信息，根据导师论文类型推断并给出建议，如"从论文看偏理论/工程，建议面试时展示相关能力"。"""
        },
        {
            "key": "training_method",
            "name": "培养方式",
            "prompt": """联网搜索{school} {advisor}导师的培养方式，要求返回具体事实：

{source_hint}

【搜索关键词建议】
- "{advisor} {school} 实验室"
- "{advisor} 指导学生"
- "{advisor} 团队"
- "{advisor} 培养方式 知乎"
- "{advisor} 研究生生活 小红书"
- "{advisor} 实验室 B站"

【必须包含】
1. 实验室管理方式（如：放养/严格管理/导师直接指导）
2. 组会频率和形式
3. 学生毕业去向（如：读博比例、就业去向）
4. 学生经验参考（如有，注明来源如"知乎用户分享"）

【禁止】
- 编造不存在的信息
- 使用模糊表述

【格式】直接列出事实，80字以内。如果找不到具体信息，给出建议，如"建议面试时主动询问实验室日常管理、组会频率、学生培养模式等"。"""
        },
        {
            "key": "students_background",
            "name": "在读学生履历",
            "prompt": """联网搜索{school} {advisor}导师实验室在读学生的情况，要求返回具体事实：

{source_hint}

【搜索关键词建议】
- "{advisor} {school} 学生"
- "{advisor} 研究生"
- "{advisor} 实验室成员"
- "{advisor} 学生背景 知乎"

【必须包含】
1. 在读学生人数（如有）
2. 学生本科来源（如：主要来自哪些学校）
3. 学生发表论文情况（如有具体例子）
4. 学生经验参考（如有，注明来源）

【禁止】
- 编造学生信息
- 使用模糊表述

【格式】直接列出事实，80字以内。如果找不到具体信息，给出建议，如"建议通过实验室官网、知乎、小红书等平台了解在读学生情况，或联系学长学姐咨询"。"""
        }
    ],
    "p3": [
        {
            "key": "recent_papers",
            "name": "近期论文",
            "prompt": """联网搜索{school} {advisor}导师2023-2025年发表的论文，要求返回具体事实：

{source_hint}

【搜索关键词建议】
- "{advisor} 2024 论文"
- "{advisor} 2025 论文"
- "{advisor} Google Scholar"
- "{advisor} DBLP"

【必须包含】
1. 具体论文标题（至少2-3篇，按时间倒序）
2. 发表期刊/会议名称
3. 发表年份

【禁止】
- 只写"发表多篇论文"不写具体标题
- 编造不存在的论文
- 使用模糊表述

【格式】直接列出论文标题和发表信息，如："1. 《论文标题》, KDD 2024"，100字以内。如果找不到近期论文，给出建议，如"建议通过Google Scholar、DBLP搜索导师最新论文，了解研究动态"。"""
        },
        {
            "key": "representative_projects",
            "name": "代表项目",
            "prompt": """联网搜索{school} {advisor}导师的代表性科研项目，要求返回具体事实：

{source_hint}

【搜索关键词建议】
- "{advisor} {school} 项目"
- "{advisor} 国家自然科学基金"
- "{advisor} 科研项目"

【必须包含】
1. 具体项目名称（至少1-2个）
2. 项目来源（如：国家自然科学基金、企业合作）
3. 项目金额或级别（如有）

【禁止】
- 只写"主持多项科研项目"不写具体名称
- 编造不存在的项目
- 使用模糊表述

【格式】直接列出项目名称和来源，如："1. 国家自然科学基金项目《项目名称》"，80字以内。如果找不到具体项目，给出建议，如"建议通过学校官网、国家自然科学基金委网站查询导师科研项目"。"""
        }
    ]
}


def create_client():
    """创建 OpenAI 客户端"""
    return OpenAI(
        api_key=DASHSCOPE_API_KEY,
        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1"
    )


def create_client(key_index=None):
    """创建 OpenAI 客户端（支持多key）"""
    return key_manager.get_client(key_index)


def verify_advisor(client, school, advisor_name):
    """
    第一阶段：验证导师是否存在并获取基本信息
    
    Returns:
        dict: {"exists": bool, "info": str, "error": str}
    """
    source_hint = SEARCH_SOURCE_HINT.format(school=school, advisor=advisor_name)
    prompt = VERIFY_PROMPT.format(
        school=school, 
        advisor=advisor_name,
        source_hint=source_hint
    )
    
    try:
        response = client.chat.completions.create(
            model="qwen-plus",
            messages=[{"role": "user", "content": prompt}],
            extra_body={
                "enable_search": True,
                "search_options": {
                    "forced_search": True,
                    "search_strategy": "pro"
                }
            }
        )
        
        result = response.choices[0].message.content.strip()
        
        if "未找到该导师信息" in result or "不存在" in result:
            return {"exists": False, "info": result, "error": None}
        
        return {"exists": True, "info": result, "error": None}
        
    except Exception as e:
        return {"exists": None, "info": None, "error": str(e)}


def search_single_aspect(client, school, advisor_name, aspect_info):
    """搜索单个方面"""
    source_hint = SEARCH_SOURCE_HINT.format(school=school, advisor=advisor_name)
    prompt = aspect_info["prompt"].format(
        school=school, 
        advisor=advisor_name,
        source_hint=source_hint
    )
    
    try:
        response = client.chat.completions.create(
            model="qwen-plus",
            messages=[{"role": "user", "content": prompt}],
            extra_body={
                "enable_search": True,
                "search_options": {
                    "forced_search": True,
                    "search_strategy": "pro"
                }
            }
        )
        
        result = response.choices[0].message.content.strip()
        
        if result.startswith("```"):
            lines = result.split('\n')
            if lines[0].startswith("```"):
                result = '\n'.join(lines[1:])
            if lines[-1].strip() == "```":
                result = '\n'.join(lines[:-1])
            result = result.strip()
        
        success = True
        if "未找到公开信息" in result or "暂无公开" in result or "暂未找到" in result:
            success = True
        
        return {
            "key": aspect_info["key"],
            "name": aspect_info["name"],
            "success": success,
            "data": result
        }
    except Exception as e:
        return {
            "key": aspect_info["key"],
            "name": aspect_info["name"],
            "success": False,
            "error": str(e)
        }


def search_priority_group(client, school, advisor_name, priority):
    """搜索一个优先级组的所有方面（串行）"""
    aspects = SEARCH_ASPECTS.get(priority, [])
    results = []
    
    for aspect in aspects:
        result = search_single_aspect(client, school, advisor_name, aspect)
        results.append(result)
        print(f"  {'✅' if result['success'] else '❌'} [{priority}] {result['name']}")
    
    return results


async def search_single_aspect_async(school, advisor_name, aspect, key_index):
    """异步搜索单个方面（使用指定key）"""
    loop = asyncio.get_event_loop()
    client = create_client(key_index)
    return await loop.run_in_executor(
        None,
        search_single_aspect,
        client, school, advisor_name, aspect
    )


async def search_priority_group_async(school, advisor_name, priority, base_key_index=0):
    """异步并行搜索一个优先级组的所有方面（每个任务使用不同key）"""
    aspects = SEARCH_ASPECTS.get(priority, [])
    num_keys = len(DASHSCOPE_API_KEYS)
    
    tasks = [
        search_single_aspect_async(school, advisor_name, aspect, base_key_index + i)
        for i, aspect in enumerate(aspects)
    ]
    
    results = await asyncio.gather(*tasks)
    
    for result in results:
        print(f"  {'✅' if result['success'] else '❌'} [{priority}] {result['name']}")
    
    return list(results)


async def verify_advisor_async(school, advisor_name, key_index=0):
    """异步验证导师（使用指定key）"""
    loop = asyncio.get_event_loop()
    client = create_client(key_index)
    return await loop.run_in_executor(
        None, 
        verify_advisor, 
        client, school, advisor_name
    )


async def search_advisor_stream(school, advisor_name):
    """
    流式搜索导师信息，两阶段 + 按优先级渐进返回 + 多Key并行
    
    Yields:
        dict: 包含 priority 和 results 的字典
    """
    school = school.strip()
    advisor_name = advisor_name.strip()
    
    if not school or not advisor_name:
        yield {
            "priority": "error",
            "results": [{"error": "学校和导师姓名不能为空"}]
        }
        return
    
    print(f"🔍 开始联网搜索：{school} - {advisor_name}")
    print(f"🔑 使用 {len(DASHSCOPE_API_KEYS)} 个 API Key 并行搜索")
    
    # 第一阶段：验证导师（使用 Key 0）
    print("📡 第一阶段：验证导师信息...")
    yield {
        "priority": "verify",
        "message": "正在验证导师信息..."
    }
    
    verify_result = await verify_advisor_async(school, advisor_name, key_index=0)
    
    if verify_result["exists"] == False:
        yield {
            "priority": "error",
            "results": [{"error": f"未找到 {school} {advisor_name} 导师的信息，请确认学校名称和导师姓名是否正确"}]
        }
        return
    
    if verify_result["exists"] == True:
        yield {
            "priority": "verified",
            "info": verify_result["info"]
        }
    
    # 第二阶段：搜索详细信息（多Key并行）
    all_results = {}
    
    # P1 使用 Key 0,1
    # P2 使用 Key 1,2,0
    # P3 使用 Key 2,0
    key_offsets = {"p1": 0, "p2": 1, "p3": 2}
    
    for priority in ["p1", "p2", "p3"]:
        print(f"📡 搜索优先级 {priority}...")
        
        results = await search_priority_group_async(
            school, advisor_name, priority, 
            base_key_index=key_offsets[priority]
        )
        
        for r in results:
            if r["success"] and r.get("data"):
                all_results[r["key"]] = r["data"]
        
        yield {
            "priority": priority,
            "results": results
        }
    
    full_info = format_full_info(all_results)
    
    yield {
        "priority": "done",
        "full_info": full_info
    }
    
    print(f"✅ 搜索完成：{school} - {advisor_name}")


def format_full_info(results):
    """将所有搜索结果汇总为完整信息"""
    sections = []
    
    section_names = {
        "research_direction": "【研究方向】",
        "recruitment_preference": "【招生偏好】",
        "academic_style": "【学术风格】",
        "training_method": "【培养方式】",
        "students_background": "【在读学生】",
        "recent_papers": "【近期论文】",
        "representative_projects": "【代表项目】"
    }
    
    for key, name in section_names.items():
        if key in results and results[key]:
            sections.append(f"{name}\n{results[key]}")
    
    if not sections:
        return "未能获取到导师信息"
    
    return "\n\n".join(sections)


def format_advisor_info_for_prompt(advisor_text, school="", lab="", advisor_name=""):
    """将导师信息文本包装为 prompt 注入格式（兼容新旧调用方式）。"""
    advisor_text = (advisor_text or "").strip()
    school = (school or "").strip()
    lab = (lab or "").strip()
    advisor_name = (advisor_name or "").strip()

    if not advisor_text:
        return ""

    meta_lines = []
    if school:
        meta_lines.append(f"学校: {school}")
    if lab:
        meta_lines.append(f"实验室: {lab}")
    if advisor_name:
        meta_lines.append(f"导师: {advisor_name}")

    meta_block = "\n".join(meta_lines)
    if meta_block:
        meta_block += "\n\n"

    return f"""【面试导师信息】
{meta_block}{advisor_text}

请根据上述导师的研究方向和学术背景，在面试中提出针对性的专业问题，考察候选人与该导师研究方向的匹配度。
"""


def search_advisor_info(school, lab=None, advisor_name=None):
    """
    同步搜索导师信息（兼容旧接口）
    
    Args:
        school: 学校名称
        lab: 实验室名称（可选；兼容主程序调用）
        advisor_name: 导师姓名
    
    Returns:
        dict: 导师信息字典
    """
    school = (school or "").strip()

    # 兼容旧签名 search_advisor_info(school, advisor_name)
    if advisor_name is None:
        advisor_name = (lab or "").strip()
        lab = ""
    else:
        lab = (lab or "").strip()
        advisor_name = (advisor_name or "").strip()

    if not school or not advisor_name:
        return {
            "success": False,
            "data": None,
            "error": "学校和导师姓名不能为空"
        }
    
    print(f"🔍 开始联网搜索：{school} - {advisor_name}")
    print(f"🔑 使用 {len(DASHSCOPE_API_KEYS)} 个 API Key")
    
    # 第一阶段：验证导师（使用 Key 0）
    print("📡 第一阶段：验证导师信息...")
    client = create_client(key_index=0)
    verify_result = verify_advisor(client, school, advisor_name)
    
    if verify_result["exists"] == False:
        return {
            "success": False,
            "data": None,
            "error": f"未找到 {school} {advisor_name} 导师的信息，请确认学校名称和导师姓名是否正确"
        }
    
    # 第二阶段：搜索详细信息（多Key轮询）
    all_results = {}
    key_index = 1
    
    for priority in ["p1", "p2", "p3"]:
        print(f"📡 搜索优先级 {priority}...")
        
        aspects = SEARCH_ASPECTS.get(priority, [])
        for aspect in aspects:
            client = create_client(key_index=key_index)
            result = search_single_aspect(client, school, advisor_name, aspect)
            if result["success"] and result.get("data"):
                all_results[result["key"]] = result["data"]
            print(f"  {'✅' if result['success'] else '❌'} [{priority}] {result['name']}")
            key_index = (key_index + 1) % len(DASHSCOPE_API_KEYS)
    
    full_info = format_full_info(all_results)
    
    print(f"✅ 搜索完成：{school} - {advisor_name}")
    
    return {
        "success": True,
        "data": full_info,
        "error": None
    }


if __name__ == "__main__":
    print("测试导师搜索功能...")
    result = search_advisor_info("中国科学技术大学", "陈恩红")
    if result["success"]:
        print("\n✅ 搜索成功！")
        print(result["data"])
    else:
        print(f"\n❌ 搜索失败：{result['error']}")
