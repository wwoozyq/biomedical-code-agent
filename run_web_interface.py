#!/usr/bin/env python3
"""
启动Web界面
"""

import subprocess
import sys
import os
from pathlib import Path

def check_dependencies():
    """检查依赖"""
    required_packages = {
        'streamlit': 'streamlit',
        'plotly': 'plotly', 
        'pandas': 'pandas',
        'numpy': 'numpy'
    }
    missing_packages = []
    
    for package, import_name in required_packages.items():
        try:
            __import__(import_name)
        except ImportError:
            missing_packages.append(package)
    
    if missing_packages:
        print(f"❌ 缺少依赖包: {', '.join(missing_packages)}")
        print("请运行以下命令安装:")
        print(f"pip install {' '.join(missing_packages)}")
        return False
    
    print("✅ 所有依赖包已安装")
    return True

def setup_directories():
    """创建必要目录"""
    directories = ["data/sample_data", "sandbox", "output", "logs"]
    for directory in directories:
        Path(directory).mkdir(parents=True, exist_ok=True)

def main():
    """主函数"""
    print("🧬 启动生物医学数据科学推理编码智能体 - 高级可视化界面")
    print("=" * 70)
    
    # 检查依赖
    print("🔍 检查系统依赖...")
    if not check_dependencies():
        return 1
    
    # 创建目录
    print("📁 创建必要目录...")
    setup_directories()
    
    # 生成示例数据（如果不存在）
    sample_data_dir = Path("data/sample_data")
    if not any(sample_data_dir.glob("*.csv")) and not any(sample_data_dir.glob("*.db")):
        print("📊 生成示例数据...")
        try:
            os.chdir("data/sample_data")
            subprocess.run([sys.executable, "generate_sample_data.py"], check=True)
            os.chdir("../..")
            print("✅ 示例数据生成完成")
        except Exception as e:
            print(f"⚠️ 生成示例数据失败: {e}")
            os.chdir("../..")
    else:
        print("✅ 示例数据已存在")
    
    # 启动Streamlit
    print("\n" + "=" * 70)
    print("🚀 启动高级可视化Web界面...")
    print("🌐 界面将在浏览器中打开: http://localhost:8501")
    print("💡 提示: 使用 Ctrl+C 停止服务")
    print("=" * 70)
    
    try:
        subprocess.run([
            sys.executable, "-m", "streamlit", "run", "web_interface.py",
            "--server.port", "8501",
            "--server.address", "localhost",
            "--theme.base", "light",
            "--theme.primaryColor", "#1f77b4",
            "--theme.backgroundColor", "#ffffff",
            "--theme.secondaryBackgroundColor", "#f8f9fa"
        ])
    except KeyboardInterrupt:
        print("\n👋 Web界面已关闭")
    except Exception as e:
        print(f"❌ 启动失败: {e}")
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())