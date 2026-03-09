#!/usr/bin/env python3
"""
多智能体协作演示脚本
"""

import os
import sys
import subprocess
from pathlib import Path

def setup_environment():
    """设置环境"""
    print("🔧 设置多智能体环境...")
    
    # 创建必要的目录
    directories = ["multi_agent_output", "logs"]
    for directory in directories:
        Path(directory).mkdir(parents=True, exist_ok=True)
        print(f"  ✓ 创建目录: {directory}")

def run_multi_agent_task(task_file, collaboration_mode):
    """运行多智能体任务"""
    print(f"\n🤖 运行多智能体任务: {collaboration_mode} 模式")
    
    try:
        cmd = [
            sys.executable, "multi_agent_main.py",
            "--task-file", task_file,
            "--collaboration-mode", collaboration_mode,
            "--verbose"
        ]
        
        print(f"  执行命令: {' '.join(cmd)}")
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        
        print("  📋 执行输出:")
        # 显示最后15行输出
        output_lines = result.stdout.split("\n")
        for line in output_lines[-15:]:
            if line.strip():
                print(f"  {line}")
        
        if result.returncode == 0:
            print(f"  ✅ {collaboration_mode} 模式执行成功")
        else:
            print(f"  ❌ {collaboration_mode} 模式执行失败")
            if result.stderr:
                print(f"  错误信息: {result.stderr}")
        
        return result.returncode == 0
        
    except subprocess.TimeoutExpired:
        print(f"  ⏰ {collaboration_mode} 模式执行超时")
        return False
    except Exception as e:
        print(f"  ❌ 运行任务时出错: {e}")
        return False

def show_results():
    """显示结果"""
    print("\n📈 查看多智能体协作结果...")
    
    output_dir = Path("multi_agent_output")
    if output_dir.exists():
        result_files = list(output_dir.glob("*.json"))
        if result_files:
            print(f"  ✓ 找到 {len(result_files)} 个结果文件:")
            for file in result_files:
                print(f"    - {file}")
        else:
            print("  ⚠️  未找到结果文件")
    else:
        print("  ⚠️  输出目录不存在")
    
    # 检查生成的文件
    generated_files = []
    for pattern in ["*.png", "*.csv", "*.json"]:
        generated_files.extend(Path(".").glob(pattern))
    
    if generated_files:
        print(f"  ✓ 智能体生成的文件:")
        for file in generated_files[:10]:  # 只显示前10个
            print(f"    - {file}")
        if len(generated_files) > 10:
            print(f"    ... 还有 {len(generated_files) - 10} 个文件")

def main():
    """主演示函数"""
    print("=" * 70)
    print("🤖 生物医学数据科学多智能体协作系统 - 演示")
    print("=" * 70)
    
    # 1. 设置环境
    setup_environment()
    
    # 2. 运行不同协作模式的演示任务
    demo_tasks = [
        ("examples/multi_agent_comprehensive_task.json", "adaptive"),
        ("examples/multi_agent_sequential_task.json", "sequential"),
        ("examples/multi_agent_parallel_task.json", "parallel")
    ]
    
    success_count = 0
    for task_file, collaboration_mode in demo_tasks:
        if Path(task_file).exists():
            if run_multi_agent_task(task_file, collaboration_mode):
                success_count += 1
        else:
            print(f"  ⚠️  任务文件不存在: {task_file}")
    
    # 3. 显示结果
    show_results()
    
    # 4. 总结
    print("\n" + "=" * 70)
    print("📊 多智能体协作演示总结")
    print("=" * 70)
    print(f"✅ 成功执行协作模式: {success_count}/{len(demo_tasks)}")
    
    if success_count >= 2:
        print("🎉 多智能体协作系统运行良好！")
        print("\n💡 接下来你可以:")
        print("  1. 查看 multi_agent_output/ 目录中的协作结果")
        print("  2. 检查 logs/ 目录中的详细执行日志")
        print("  3. 尝试不同的协作模式和任务配置")
        print("  4. 在Web界面中体验多智能体协作")
        print("  5. 自定义专门化智能体和协作模式")
        return 0
    else:
        print("⚠️  部分协作模式执行失败，请检查日志")
        return 1

if __name__ == "__main__":
    sys.exit(main())