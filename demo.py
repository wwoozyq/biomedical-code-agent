#!/usr/bin/env python3
"""
生物医学数据科学推理编码智能体 - 演示脚本
"""

import os
import sys
import subprocess
from pathlib import Path

def setup_environment():
    """设置环境"""
    print("🔧 设置环境...")
    
    # 创建必要的目录
    directories = ["data/sample_data", "sandbox", "output", "logs"]
    for directory in directories:
        Path(directory).mkdir(parents=True, exist_ok=True)
        print(f"  ✓ 创建目录: {directory}")

def generate_sample_data():
    """生成示例数据"""
    print("\n📊 生成示例数据...")
    
    try:
        # 切换到数据目录并生成示例数据
        os.chdir("data/sample_data")
        result = subprocess.run([sys.executable, "generate_sample_data.py"], 
                              capture_output=True, text=True)
        os.chdir("../..")
        
        if result.returncode == 0:
            print("  ✓ 示例数据生成成功")
        else:
            print(f"  ❌ 示例数据生成失败: {result.stderr}")
            return False
    except Exception as e:
        print(f"  ❌ 生成示例数据时出错: {e}")
        return False
    
    return True

def run_demo_task(task_type, task_file):
    """运行演示任务"""
    print(f"\n🚀 运行 {task_type} 任务...")
    
    try:
        cmd = [
            sys.executable, "main.py",
            "--task-type", task_type,
            "--input-file", task_file,
            "--verbose",
            "--max-iterations", "5"
        ]
        
        print(f"  执行命令: {' '.join(cmd)}")
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        print("  📋 执行输出:")
        print("  " + "\n  ".join(result.stdout.split("\n")[-20:]))  # 显示最后20行
        
        if result.returncode == 0:
            print(f"  ✅ {task_type} 任务执行成功")
        else:
            print(f"  ❌ {task_type} 任务执行失败")
            print(f"  错误信息: {result.stderr}")
        
        return result.returncode == 0
        
    except Exception as e:
        print(f"  ❌ 运行任务时出错: {e}")
        return False

def show_results():
    """显示结果"""
    print("\n📈 查看结果...")
    
    output_dir = Path("output")
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
        print(f"  ✓ 生成的文件:")
        for file in generated_files[:10]:  # 只显示前10个
            print(f"    - {file}")
        if len(generated_files) > 10:
            print(f"    ... 还有 {len(generated_files) - 10} 个文件")

def main():
    """主演示函数"""
    print("=" * 60)
    print("🧬 生物医学数据科学推理编码智能体 - 演示")
    print("=" * 60)
    
    # 1. 设置环境
    setup_environment()
    
    # 2. 生成示例数据
    if not generate_sample_data():
        print("❌ 演示终止：无法生成示例数据")
        return 1
    
    # 3. 运行演示任务
    demo_tasks = [
        ("data_analysis", "examples/data_analysis_task.json"),
        ("prediction", "examples/prediction_task.json"),
        ("sql_query", "examples/sql_query_task.json")
    ]
    
    success_count = 0
    for task_type, task_file in demo_tasks:
        if Path(task_file).exists():
            if run_demo_task(task_type, task_file):
                success_count += 1
        else:
            print(f"  ⚠️  任务文件不存在: {task_file}")
    
    # 4. 显示结果
    show_results()
    
    # 5. 总结
    print("\n" + "=" * 60)
    print("📊 演示总结")
    print("=" * 60)
    print(f"✅ 成功执行任务: {success_count}/{len(demo_tasks)}")
    
    if success_count == len(demo_tasks):
        print("🎉 所有演示任务执行成功！")
        print("\n💡 接下来你可以:")
        print("  1. 查看 output/ 目录中的结果文件")
        print("  2. 检查 logs/ 目录中的执行日志")
        print("  3. 修改 examples/ 中的任务配置文件")
        print("  4. 创建自己的任务并运行")
        return 0
    else:
        print("⚠️  部分任务执行失败，请检查日志")
        return 1

if __name__ == "__main__":
    sys.exit(main())