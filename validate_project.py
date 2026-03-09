#!/usr/bin/env python3
"""
项目完成度验证脚本
"""

import os
import json
from pathlib import Path

def check_basic_requirements():
    """检查基础要求完成情况"""
    print("🔍 检查基础要求完成情况...")
    
    # 1. 检查核心文件存在
    core_files = [
        "src/agent/react_agent.py",
        "src/agent/action_space.py", 
        "src/tasks/data_analysis.py",
        "src/tasks/prediction.py",
        "src/tasks/sql_query.py",
        "main.py",
        "README.md"
    ]
    
    missing_files = []
    for file in core_files:
        if not Path(file).exists():
            missing_files.append(file)
    
    if missing_files:
        print(f"❌ 缺少核心文件: {missing_files}")
        return False
    else:
        print("✅ 所有核心文件存在")
    
    # 2. 检查ReAct智能体实现
    with open("src/agent/react_agent.py", 'r') as f:
        react_content = f.read()
        
    react_features = [
        "class ReActAgent",
        "def solve_task",
        "_generate_thought",
        "_plan_action", 
        "_execute_and_observe"
    ]
    
    missing_features = []
    for feature in react_features:
        if feature not in react_content:
            missing_features.append(feature)
    
    if missing_features:
        print(f"❌ ReAct智能体缺少功能: {missing_features}")
        return False
    else:
        print("✅ ReAct智能体核心功能完整")
    
    # 3. 检查四类动作实现
    with open("src/agent/action_space.py", 'r') as f:
        action_content = f.read()
    
    actions = [
        "_request_info",
        "_terminal_action", 
        "_code_execution",
        "_debugging_action"
    ]
    
    missing_actions = []
    for action in actions:
        if action not in action_content:
            missing_actions.append(action)
    
    if missing_actions:
        print(f"❌ 缺少动作实现: {missing_actions}")
        return False
    else:
        print("✅ 四类核心动作完整实现")
    
    return True

def check_experiment_results():
    """检查实验结果"""
    print("\n📊 检查实验结果...")
    
    # 检查输出目录
    output_dir = Path("output")
    if not output_dir.exists():
        print("❌ 输出目录不存在")
        return False
    
    # 检查结果文件
    result_files = list(output_dir.glob("*_result.json"))
    trace_files = list(output_dir.glob("*_trace.json"))
    
    if not result_files:
        print("❌ 没有找到结果文件")
        return False
    
    if not trace_files:
        print("❌ 没有找到轨迹文件")
        return False
    
    print(f"✅ 找到 {len(result_files)} 个结果文件")
    print(f"✅ 找到 {len(trace_files)} 个轨迹文件")
    
    # 检查结果文件内容
    for result_file in result_files:
        try:
            with open(result_file, 'r') as f:
                result_data = json.load(f)
            
            required_keys = ["task_config", "agent_result", "task_result"]
            missing_keys = [key for key in required_keys if key not in result_data]
            
            if missing_keys:
                print(f"❌ {result_file} 缺少字段: {missing_keys}")
                return False
            
            # 检查执行轨迹
            execution_trace = result_data["agent_result"].get("execution_trace", [])
            if not execution_trace:
                print(f"❌ {result_file} 没有执行轨迹")
                return False
            
            print(f"✅ {result_file} 包含 {len(execution_trace)} 个执行步骤")
            
        except Exception as e:
            print(f"❌ 读取 {result_file} 失败: {e}")
            return False
    
    return True

def check_advanced_features():
    """检查进阶功能"""
    print("\n🌐 检查进阶功能...")
    
    # 检查Web界面
    web_files = ["web_interface.py", "run_web_interface.py"]
    missing_web_files = [f for f in web_files if not Path(f).exists()]
    
    if missing_web_files:
        print(f"❌ 缺少Web界面文件: {missing_web_files}")
        return False
    
    # 检查Web界面内容
    with open("web_interface.py", 'r') as f:
        web_content = f.read()
    
    web_features = [
        "streamlit",
        "def main",
        "st.title",
        "ReActAgent"
    ]
    
    missing_web_features = [f for f in web_features if f not in web_content]
    
    if missing_web_features:
        print(f"❌ Web界面缺少功能: {missing_web_features}")
        return False
    
    print("✅ Web可视化界面完整实现")
    return True

def check_code_quality():
    """检查代码质量"""
    print("\n📝 检查代码质量...")
    
    # 检查文档
    docs = ["README.md", "PROJECT_SUMMARY.md", "requirements.txt"]
    missing_docs = [doc for doc in docs if not Path(doc).exists()]
    
    if missing_docs:
        print(f"❌ 缺少文档: {missing_docs}")
        return False
    
    # 检查README内容
    with open("README.md", 'r') as f:
        readme_content = f.read()
    
    readme_sections = [
        "项目概述",
        "系统架构", 
        "安装与运行",
        "使用方法"
    ]
    
    missing_sections = [s for s in readme_sections if s not in readme_content]
    
    if missing_sections:
        print(f"❌ README缺少章节: {missing_sections}")
        return False
    
    print("✅ 文档完整，格式规范")
    
    # 检查项目结构
    required_dirs = ["src", "config", "examples", "data"]
    missing_dirs = [d for d in required_dirs if not Path(d).exists()]
    
    if missing_dirs:
        print(f"❌ 缺少目录: {missing_dirs}")
        return False
    
    print("✅ 项目结构清晰完整")
    return True

def check_generated_outputs():
    """检查生成的输出"""
    print("\n📈 检查生成的输出...")
    
    # 检查是否有实际生成的文件
    generated_files = []
    
    # 检查图片文件
    image_files = list(Path(".").glob("*.png")) + list(Path(".").glob("*.jpg"))
    if image_files:
        generated_files.extend(image_files)
        print(f"✅ 生成了 {len(image_files)} 个图片文件: {[f.name for f in image_files]}")
    
    # 检查CSV文件
    csv_files = list(Path(".").glob("*.csv"))
    if csv_files:
        generated_files.extend(csv_files)
        print(f"✅ 生成了 {len(csv_files)} 个CSV文件: {[f.name for f in csv_files]}")
    
    # 检查沙箱中的文件
    sandbox_dir = Path("sandbox")
    if sandbox_dir.exists():
        sandbox_files = list(sandbox_dir.glob("*"))
        if sandbox_files:
            generated_files.extend(sandbox_files)
            print(f"✅ 沙箱中有 {len(sandbox_files)} 个文件")
    
    if not generated_files:
        print("⚠️  没有找到智能体生成的输出文件")
        return False
    
    print(f"✅ 智能体成功生成了 {len(generated_files)} 个文件")
    return True

def main():
    """主验证函数"""
    print("🧬 生物医学数据科学推理编码智能体 - 项目完成度验证")
    print("=" * 60)
    
    checks = [
        ("基础工程实现 (50%)", check_basic_requirements),
        ("实验结果 (10%)", check_experiment_results), 
        ("进阶功能 (20%)", check_advanced_features),
        ("代码质量 (20%)", check_code_quality),
        ("实际输出验证", check_generated_outputs)
    ]
    
    passed_checks = 0
    total_checks = len(checks)
    
    for check_name, check_func in checks:
        print(f"\n{'='*20} {check_name} {'='*20}")
        try:
            if check_func():
                passed_checks += 1
                print(f"✅ {check_name} - 通过")
            else:
                print(f"❌ {check_name} - 未通过")
        except Exception as e:
            print(f"❌ {check_name} - 检查出错: {e}")
    
    print("\n" + "=" * 60)
    print("📊 验证结果总结")
    print("=" * 60)
    
    completion_rate = (passed_checks / total_checks) * 100
    print(f"完成度: {passed_checks}/{total_checks} ({completion_rate:.1f}%)")
    
    if completion_rate >= 90:
        print("🎉 项目完成度优秀！已达到老师要求的标准")
    elif completion_rate >= 80:
        print("✅ 项目完成度良好，基本达到要求")
    elif completion_rate >= 70:
        print("⚠️  项目完成度一般，需要完善部分功能")
    else:
        print("❌ 项目完成度不足，需要大幅改进")
    
    print("\n💡 建议:")
    print("1. 查看生成的文件: correlation_heatmap.png")
    print("2. 检查执行日志: output/*_result.json")
    print("3. 运行Web界面: python3 run_web_interface.py")
    print("4. 查看完整文档: README.md")
    
    return completion_rate >= 80

if __name__ == "__main__":
    main()