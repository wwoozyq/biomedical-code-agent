#!/bin/bash

# 🚀 GitHub 项目发布脚本
# 使用方法: ./publish_to_github.sh YOUR_GITHUB_USERNAME

set -e  # 遇到错误时退出

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 打印带颜色的消息
print_message() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_step() {
    echo -e "${BLUE}[STEP]${NC} $1"
}

# 检查参数
if [ $# -eq 0 ]; then
    print_error "请提供您的GitHub用户名"
    echo "使用方法: ./publish_to_github.sh YOUR_GITHUB_USERNAME"
    exit 1
fi

GITHUB_USERNAME=$1
REPO_NAME="biomedical-code-agent"

print_message "🧬 生物医学数据科学推理编码智能体 - GitHub发布脚本"
print_message "GitHub用户名: $GITHUB_USERNAME"
print_message "仓库名称: $REPO_NAME"

# 步骤1: 检查项目完整性
print_step "1. 检查项目完整性..."

if [ ! -f "validate_project.py" ]; then
    print_error "未找到 validate_project.py 文件"
    exit 1
fi

print_message "运行项目验证..."
python3 validate_project.py

if [ $? -ne 0 ]; then
    print_error "项目验证失败，请修复问题后重试"
    exit 1
fi

print_message "✅ 项目验证通过"

# 步骤2: 清理项目文件
print_step "2. 清理项目文件..."

print_message "清理Python缓存文件..."
find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
find . -name "*.pyc" -delete 2>/dev/null || true
find . -name "*.pyo" -delete 2>/dev/null || true

print_message "清理日志和输出文件..."
rm -rf logs/*.log 2>/dev/null || true
rm -rf output/* 2>/dev/null || true
rm -rf multi_agent_output/* 2>/dev/null || true

# 保留目录结构
mkdir -p logs output multi_agent_output

print_message "✅ 文件清理完成"

# 步骤3: 检查必要文件
print_step "3. 检查必要文件..."

required_files=("README.md" "requirements.txt" "LICENSE" ".gitignore" "CONTRIBUTING.md")

for file in "${required_files[@]}"; do
    if [ ! -f "$file" ]; then
        print_error "缺少必要文件: $file"
        exit 1
    fi
    print_message "✅ 找到文件: $file"
done

# 步骤4: Git 初始化和提交
print_step "4. Git 初始化和提交..."

# 检查是否已经是Git仓库
if [ ! -d ".git" ]; then
    print_message "初始化Git仓库..."
    git init
else
    print_message "Git仓库已存在"
fi

# 添加所有文件
print_message "添加文件到Git..."
git add .

# 检查是否有更改需要提交
if git diff --staged --quiet; then
    print_warning "没有新的更改需要提交"
else
    print_message "创建提交..."
    git commit -m "feat: 初始化生物医学数据科学推理编码智能体项目

- 实现基于ReAct范式的单智能体系统
- 添加多智能体协作功能（数据分析、建模、SQL、质量保证）
- 支持数据分析、预测建模、SQL查询任务
- 提供Streamlit Web可视化界面
- 支持多种协作模式（自适应、顺序、并行、分层）
- 包含完整的文档、示例和测试"
fi

# 步骤5: 添加远程仓库
print_step "5. 配置远程仓库..."

REMOTE_URL="https://github.com/$GITHUB_USERNAME/$REPO_NAME.git"

# 检查远程仓库是否已存在
if git remote get-url origin >/dev/null 2>&1; then
    current_url=$(git remote get-url origin)
    if [ "$current_url" != "$REMOTE_URL" ]; then
        print_message "更新远程仓库URL..."
        git remote set-url origin "$REMOTE_URL"
    else
        print_message "远程仓库已正确配置"
    fi
else
    print_message "添加远程仓库..."
    git remote add origin "$REMOTE_URL"
fi

# 步骤6: 推送到GitHub
print_step "6. 推送到GitHub..."

print_message "设置主分支..."
git branch -M main

print_warning "即将推送到GitHub仓库: $REMOTE_URL"
print_warning "请确保您已经在GitHub上创建了该仓库"
read -p "按Enter键继续，或Ctrl+C取消..."

print_message "推送到GitHub..."
git push -u origin main

if [ $? -eq 0 ]; then
    print_message "✅ 成功推送到GitHub"
else
    print_error "推送失败，请检查："
    print_error "1. GitHub仓库是否已创建"
    print_error "2. 您是否有推送权限"
    print_error "3. 网络连接是否正常"
    exit 1
fi

# 步骤7: 生成发布信息
print_step "7. 生成发布信息..."

cat > RELEASE_INFO.md << EOF
# 🎉 生物医学数据科学推理编码智能体 v1.0.0

## 🚀 首次发布

### ✨ 主要特性
- 🤖 基于ReAct范式的推理编码智能体
- 👥 多智能体协作系统（数据分析、建模、SQL、质量保证）
- 📊 支持三大任务类型：数据分析、预测建模、SQL查询
- 🌐 Streamlit Web可视化界面
- ⚡ 多种协作模式：自适应、顺序、并行、分层
- 🔒 安全沙箱执行环境

### 📦 包含内容
- 完整的源代码
- 示例数据和任务配置
- 详细的文档和使用指南
- 演示脚本和验证工具

### 🛠️ 快速开始
\`\`\`bash
git clone https://github.com/$GITHUB_USERNAME/$REPO_NAME.git
cd $REPO_NAME
pip install -r requirements.txt
python demo.py
\`\`\`

### 📊 项目统计
- 项目完成度: 100%
- 代码行数: 3000+
- 支持的任务类型: 3种
- 智能体数量: 4个专门化智能体
- 协作模式: 4种

### 🎯 适用场景
- 生物医学数据分析
- 临床研究数据处理
- 医疗数据挖掘
- 生物信息学研究

### 🔗 相关链接
- 项目主页: https://github.com/$GITHUB_USERNAME/$REPO_NAME
- 文档: https://github.com/$GITHUB_USERNAME/$REPO_NAME/blob/main/README.md
- 问题反馈: https://github.com/$GITHUB_USERNAME/$REPO_NAME/issues
EOF

print_message "✅ 发布信息已生成到 RELEASE_INFO.md"

# 完成
print_message ""
print_message "🎉 项目发布完成！"
print_message ""
print_message "📋 接下来的步骤："
print_message "1. 访问 https://github.com/$GITHUB_USERNAME/$REPO_NAME"
print_message "2. 检查仓库内容是否正确"
print_message "3. 在 Settings 中配置仓库描述和标签"
print_message "4. 创建第一个 Release (使用 RELEASE_INFO.md 中的内容)"
print_message "5. 启用 Issues 和 Discussions"
print_message ""
print_message "🔗 仓库地址: https://github.com/$GITHUB_USERNAME/$REPO_NAME"
print_message ""
print_message "📖 详细发布指南请查看: GITHUB_PUBLISH_GUIDE.md"