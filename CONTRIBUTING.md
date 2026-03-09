# 贡献指南 / Contributing Guide

感谢您对生物医学数据科学推理编码智能体项目的关注！我们欢迎各种形式的贡献。

## 如何贡献

### 报告问题 (Bug Reports)

如果您发现了问题，请：

1. 检查 [Issues](../../issues) 确认问题尚未被报告
2. 创建新的 Issue，包含：
   - 清晰的问题描述
   - 重现步骤
   - 预期行为 vs 实际行为
   - 环境信息（Python版本、操作系统等）
   - 相关的错误日志

### 功能请求 (Feature Requests)

1. 检查现有的 Issues 和 Pull Requests
2. 创建新的 Issue 描述：
   - 功能的详细说明
   - 使用场景
   - 可能的实现方案

### 代码贡献

#### 开发环境设置

```bash
# 1. Fork 项目到您的 GitHub 账户
# 2. 克隆您的 fork
git clone https://github.com/YOUR_USERNAME/biomedical-code-agent.git
cd biomedical-code-agent

# 3. 创建虚拟环境
python -m venv venv
source venv/bin/activate  # Linux/Mac
# 或 venv\Scripts\activate  # Windows

# 4. 安装依赖
pip install -r requirements.txt

# 5. 运行测试确保环境正常
python demo.py
```

#### 开发流程

1. **创建分支**
   ```bash
   git checkout -b feature/your-feature-name
   # 或
   git checkout -b fix/your-bug-fix
   ```

2. **编写代码**
   - 遵循现有的代码风格
   - 添加必要的注释和文档
   - 编写或更新测试

3. **测试**
   ```bash
   # 运行基础测试
   python validate_project.py
   
   # 运行演示脚本
   python demo.py
   python demo_multi_agent.py
   
   # 测试Web界面
   python run_web_interface.py
   ```

4. **提交更改**
   ```bash
   git add .
   git commit -m "feat: 添加新功能的简短描述"
   # 或
   git commit -m "fix: 修复问题的简短描述"
   ```

5. **推送并创建 Pull Request**
   ```bash
   git push origin your-branch-name
   ```

#### 代码规范

- **Python 代码风格**: 遵循 PEP 8
- **注释**: 使用中文注释，重要函数添加文档字符串
- **命名**: 
  - 变量和函数使用 snake_case
  - 类名使用 PascalCase
  - 常量使用 UPPER_CASE
- **导入**: 按标准库、第三方库、本地模块的顺序组织

#### 提交信息规范

使用以下前缀：
- `feat:` 新功能
- `fix:` 错误修复
- `docs:` 文档更新
- `style:` 代码格式调整
- `refactor:` 代码重构
- `test:` 测试相关
- `chore:` 构建过程或辅助工具的变动

### Pull Request 指南

1. **PR 标题**: 清晰描述更改内容
2. **PR 描述**: 包含：
   - 更改的详细说明
   - 相关的 Issue 编号
   - 测试说明
   - 截图（如适用）

3. **检查清单**:
   - [ ] 代码遵循项目规范
   - [ ] 添加了必要的测试
   - [ ] 更新了相关文档
   - [ ] 所有测试通过
   - [ ] 没有引入新的警告

## 开发指南

### 项目架构

```
src/
├── agent/              # 核心智能体实现
├── multi_agent/        # 多智能体协作系统
├── tasks/              # 任务处理器
└── utils/              # 工具函数
```

### 添加新任务类型

1. 在 `src/tasks/` 创建新的任务处理器
2. 继承 `BaseTask` 类
3. 实现必要方法
4. 添加示例和测试

### 添加新的智能体

1. 在 `src/multi_agent/specialized_agents.py` 添加新智能体
2. 继承 `BaseSpecializedAgent`
3. 实现 `can_handle_task` 和 `execute_task` 方法
4. 在协调器中注册

### 扩展协作模式

1. 在 `src/multi_agent/collaboration_patterns.py` 添加新模式
2. 继承 `CollaborationPattern`
3. 实现 `execute` 方法
4. 在协调器中注册

## 社区

- **讨论**: 使用 GitHub Discussions 进行技术讨论
- **问题**: 使用 GitHub Issues 报告问题和功能请求
- **代码**: 通过 Pull Requests 贡献代码

## 行为准则

请遵循友善、包容的交流原则：
- 尊重不同观点和经验水平
- 提供建设性的反馈
- 专注于对社区最有利的事情
- 对新贡献者表现出同理心

感谢您的贡献！🎉