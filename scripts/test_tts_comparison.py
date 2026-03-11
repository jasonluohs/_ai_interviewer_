# -*- coding: utf-8 -*-
"""
TTS 延迟对比测试脚本
对比 StepFun API 和 edge-TTS 的延迟、质量和稳定性
"""

import sys
import os
import time
import asyncio
import statistics
from pathlib import Path
from typing import List, Tuple

# 添加项目根目录到 path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from modules.audio_processor import (
    TTS_async,           # StepFun API
    EdgeTTS_async,       # edge-TTS
    EDGE_TTS_AVAILABLE,
    EDGE_TTS_VOICES,
)

# ==================== 测试配置 ====================

# 测试文本（不同长度）
TEST_TEXTS = {
    "短句": "你好，欢迎参加今天的面试。",
    "中句": "请介绍一下你最近做过的一个项目，以及你在其中担任的角色和主要贡献。",
    "长句": "在分布式系统设计中，我们需要考虑多个方面，包括数据一致性、系统可用性、分区容错性，以及如何在这三者之间做出合理的权衡。请详细说明你对CAP定理的理解。",
}

# 测试轮数
TEST_ROUNDS = 3

# 输出目录
OUTPUT_DIR = PROJECT_ROOT / "output" / "tts_test"


# ==================== 测试函数 ====================

async def test_stepfun_tts(text: str, output_path: str) -> Tuple[bool, float]:
    """
    测试 StepFun TTS
    返回: (成功标志, 延迟时间秒)
    """
    tts = TTS_async()
    
    start_time = time.perf_counter()
    success, path = await tts.to_speech_async(text, output_path, use_cache=False)
    end_time = time.perf_counter()
    
    latency = end_time - start_time
    return success, latency


async def test_edge_tts(text: str, output_path: str, voice: str = None) -> Tuple[bool, float]:
    """
    测试 edge-TTS
    返回: (成功标志, 延迟时间秒)
    """
    if not EDGE_TTS_AVAILABLE:
        print("❌ edge-tts 未安装")
        return False, -1
    
    tts = EdgeTTS_async(voice=voice)
    
    start_time = time.perf_counter()
    success, path = await tts.to_speech_async(text, output_path, use_cache=False)
    end_time = time.perf_counter()
    
    latency = end_time - start_time
    return success, latency


async def run_comparison_test():
    """运行完整的对比测试"""
    
    print("=" * 70)
    print("🎤 TTS 延迟对比测试")
    print("=" * 70)
    print()
    
    # 创建输出目录
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    
    # 存储结果
    results = {
        "stepfun": {},
        "edge_tts": {}
    }
    
    # 对每种文本长度进行测试
    for text_type, text in TEST_TEXTS.items():
        print(f"\n{'='*50}")
        print(f"📝 测试文本类型: {text_type}")
        print(f"   文本长度: {len(text)} 字符")
        print(f"   内容预览: {text[:50]}...")
        print(f"{'='*50}")
        
        stepfun_latencies = []
        edge_latencies = []
        
        for round_num in range(1, TEST_ROUNDS + 1):
            print(f"\n--- 第 {round_num}/{TEST_ROUNDS} 轮 ---")
            
            # 测试 StepFun
            stepfun_output = OUTPUT_DIR / f"stepfun_{text_type}_{round_num}.mp3"
            print(f"  🔵 StepFun API 测试中...", end=" ", flush=True)
            try:
                success, latency = await test_stepfun_tts(text, str(stepfun_output))
                if success:
                    stepfun_latencies.append(latency)
                    file_size = stepfun_output.stat().st_size / 1024  # KB
                    print(f"✅ {latency:.3f}s (文件: {file_size:.1f}KB)")
                else:
                    print(f"❌ 失败")
            except Exception as e:
                print(f"❌ 错误: {e}")
            
            # 间隔一下避免限流
            await asyncio.sleep(0.5)
            
            # 测试 edge-TTS
            edge_output = OUTPUT_DIR / f"edge_{text_type}_{round_num}.mp3"
            print(f"  🟢 edge-TTS 测试中...", end=" ", flush=True)
            try:
                success, latency = await test_edge_tts(text, str(edge_output))
                if success:
                    edge_latencies.append(latency)
                    file_size = edge_output.stat().st_size / 1024  # KB
                    print(f"✅ {latency:.3f}s (文件: {file_size:.1f}KB)")
                else:
                    print(f"❌ 失败")
            except Exception as e:
                print(f"❌ 错误: {e}")
            
            await asyncio.sleep(0.5)
        
        # 汇总该文本类型的结果
        results["stepfun"][text_type] = stepfun_latencies
        results["edge_tts"][text_type] = edge_latencies
    
    # ==================== 输出汇总报告 ====================
    print("\n")
    print("=" * 70)
    print("📊 测试结果汇总")
    print("=" * 70)
    
    print("\n### 延迟对比（单位：秒）\n")
    print(f"{'文本类型':<10} | {'StepFun API':<25} | {'edge-TTS':<25} | 胜出")
    print("-" * 80)
    
    for text_type in TEST_TEXTS.keys():
        stepfun_data = results["stepfun"].get(text_type, [])
        edge_data = results["edge_tts"].get(text_type, [])
        
        # 计算统计值
        if stepfun_data:
            sf_avg = statistics.mean(stepfun_data)
            sf_min = min(stepfun_data)
            sf_max = max(stepfun_data)
            sf_str = f"平均:{sf_avg:.3f} (范围:{sf_min:.3f}-{sf_max:.3f})"
        else:
            sf_avg = float('inf')
            sf_str = "N/A"
        
        if edge_data:
            e_avg = statistics.mean(edge_data)
            e_min = min(edge_data)
            e_max = max(edge_data)
            e_str = f"平均:{e_avg:.3f} (范围:{e_min:.3f}-{e_max:.3f})"
        else:
            e_avg = float('inf')
            e_str = "N/A"
        
        # 判断胜出
        if sf_avg < e_avg:
            winner = "🔵 StepFun"
        elif e_avg < sf_avg:
            winner = "🟢 edge-TTS"
        else:
            winner = "平局"
        
        print(f"{text_type:<10} | {sf_str:<25} | {e_str:<25} | {winner}")
    
    # 总体统计
    print("\n### 总体统计\n")
    
    all_stepfun = [lat for lats in results["stepfun"].values() for lat in lats]
    all_edge = [lat for lats in results["edge_tts"].values() for lat in lats]
    
    if all_stepfun:
        print(f"🔵 StepFun API:")
        print(f"   - 平均延迟: {statistics.mean(all_stepfun):.3f}s")
        print(f"   - 最小延迟: {min(all_stepfun):.3f}s")
        print(f"   - 最大延迟: {max(all_stepfun):.3f}s")
        print(f"   - 成功率: {len(all_stepfun)}/{TEST_ROUNDS * len(TEST_TEXTS)} ({100*len(all_stepfun)/(TEST_ROUNDS*len(TEST_TEXTS)):.1f}%)")
    
    print()
    
    if all_edge:
        print(f"🟢 edge-TTS:")
        print(f"   - 平均延迟: {statistics.mean(all_edge):.3f}s")
        print(f"   - 最小延迟: {min(all_edge):.3f}s")
        print(f"   - 最大延迟: {max(all_edge):.3f}s")
        print(f"   - 成功率: {len(all_edge)}/{TEST_ROUNDS * len(TEST_TEXTS)} ({100*len(all_edge)/(TEST_ROUNDS*len(TEST_TEXTS)):.1f}%)")
    
    # 结论
    print("\n### 结论\n")
    if all_stepfun and all_edge:
        sf_total_avg = statistics.mean(all_stepfun)
        e_total_avg = statistics.mean(all_edge)
        
        if e_total_avg < sf_total_avg:
            improvement = (sf_total_avg - e_total_avg) / sf_total_avg * 100
            print(f"✅ edge-TTS 平均延迟更低，比 StepFun API 快 {improvement:.1f}%")
            print(f"   推荐在服务器部署时使用 edge-TTS")
        elif sf_total_avg < e_total_avg:
            improvement = (e_total_avg - sf_total_avg) / e_total_avg * 100
            print(f"✅ StepFun API 平均延迟更低，比 edge-TTS 快 {improvement:.1f}%")
        else:
            print(f"两者延迟相近")
    
    print(f"\n📁 测试音频文件已保存到: {OUTPUT_DIR}")
    print("\n" + "=" * 70)


async def test_edge_voices():
    """测试 edge-TTS 的不同声音"""
    
    if not EDGE_TTS_AVAILABLE:
        print("❌ edge-tts 未安装")
        return
    
    print("\n")
    print("=" * 70)
    print("🎭 edge-TTS 声音测试")
    print("=" * 70)
    
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    
    test_text = "你好，欢迎参加今天的技术面试。请先做一个简短的自我介绍。"
    
    print(f"\n测试文本: {test_text}\n")
    print(f"{'声音ID':<25} | {'描述':<20} | 延迟(秒) | 状态")
    print("-" * 80)
    
    for voice_id, description in EDGE_TTS_VOICES.items():
        output_path = OUTPUT_DIR / f"voice_{voice_id.replace('-', '_')}.mp3"
        
        try:
            success, latency = await test_edge_tts(test_text, str(output_path), voice=voice_id)
            if success:
                print(f"{voice_id:<25} | {description:<20} | {latency:.3f}    | ✅")
            else:
                print(f"{voice_id:<25} | {description:<20} | N/A      | ❌")
        except Exception as e:
            print(f"{voice_id:<25} | {description:<20} | N/A      | ❌ {e}")
        
        await asyncio.sleep(0.3)
    
    print(f"\n📁 声音测试文件已保存到: {OUTPUT_DIR}")


async def quick_test():
    """快速测试（单次对比）"""
    
    print("\n🚀 快速测试模式\n")
    
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    
    text = "这是一个快速测试，用来对比两种TTS引擎的响应速度。"
    
    print(f"测试文本: {text}\n")
    
    # StepFun
    print("🔵 StepFun API...", end=" ", flush=True)
    try:
        success, latency = await test_stepfun_tts(text, str(OUTPUT_DIR / "quick_stepfun.mp3"))
        if success:
            print(f"✅ {latency:.3f}s")
        else:
            print("❌ 失败")
    except Exception as e:
        print(f"❌ {e}")
    
    # edge-TTS
    print("🟢 edge-TTS...", end=" ", flush=True)
    try:
        success, latency = await test_edge_tts(text, str(OUTPUT_DIR / "quick_edge.mp3"))
        if success:
            print(f"✅ {latency:.3f}s")
        else:
            print("❌ 失败")
    except Exception as e:
        print(f"❌ {e}")


# ==================== 主入口 ====================

def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description="TTS 延迟对比测试")
    parser.add_argument("--quick", action="store_true", help="快速测试模式（单次对比）")
    parser.add_argument("--voices", action="store_true", help="测试 edge-TTS 不同声音")
    parser.add_argument("--full", action="store_true", help="完整对比测试")
    
    args = parser.parse_args()
    
    if args.quick:
        asyncio.run(quick_test())
    elif args.voices:
        asyncio.run(test_edge_voices())
    elif args.full:
        asyncio.run(run_comparison_test())
    else:
        # 默认运行快速测试
        print("使用方法:")
        print("  python test_tts_comparison.py --quick   # 快速测试")
        print("  python test_tts_comparison.py --voices  # 测试不同声音")
        print("  python test_tts_comparison.py --full    # 完整对比测试")
        print("\n正在运行快速测试...\n")
        asyncio.run(quick_test())


if __name__ == "__main__":
    main()
