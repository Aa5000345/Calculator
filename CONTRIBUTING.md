# 贡献指南

感谢你有兴趣为 MultiCalc 做出贡献！

## 目录

- [行为准则](#行为准则)
- [我可以贡献什么？](#我可以贡献什么)
- [开发环境](#开发环境)
- [提交 Pull Request](#提交-pull-request)
- [编码规范](#编码规范)
- [测试](#测试)
- [国际化](#国际化)
- [发布流程](#发布流程)

---

## 行为准则

参与本项目即表示你同意遵守 [行为准则](CODE_OF_CONDUCT.md)。
请在互动中保持尊重和友善。

## 我可以贡献什么？

- 🐛 **报告 Bug**：[新建 Issue](https://github.com/Aa5000345/Calculator/issues/new?template=bug_report.yml)
- 💡 **提出功能建议**：[新建 Issue](https://github.com/Aa5000345/Calculator/issues/new?template=feature_request.yml)
- 📖 **改进文档**
- 🌍 **翻译**：`config/i18n/*.json`
- 🎨 **主题**：`config/themes/*.json`
- 🔧 **提交代码**：见下文

## 开发环境

### 环境要求

- Python **3.10+**
- Windows 11 / 10、macOS 12+、Linux（桌面环境 + Qt 运行库）
- Git

### 克隆与安装

```bash
git clone https://github.com/Aa5000345/Calculator.git
cd Calculator

python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate

pip install -r requirements.txt
pip install pytest pytest-qt  # 测试依赖
运行
bash
# GUI
python main.py

# CLI
python main.py -e "1+1"
python main.py -e "sin(30)" --angle DEG
python main.py -e "1+1" --json
项目结构
.
├── main.py                 # 入口
├── core/                   # 计算内核（不依赖 Qt）
│   ├── engine.py           # 表达式解析 / 求值
│   ├── probability.py      # 概率与统计
│   ├── finance.py          # 财务
│   ├── plot_sample.py      # 绘图采样
│   └── ...
├── ui/                     # Qt 界面层
│   ├── main_window.py      # 主窗口
│   ├── panels/             # 25 个功能面板
│   └── widgets/            # 浮动键盘、手写、OCR
├── config/
│   ├── default_settings.json
│   ├── i18n/               # 语言包
│   └── themes/             # 主题文件
├── tests/
├── plugins/                # 插件目录
└── requirements.txt
提交 Pull Request
流程
Fork 本仓库

从 main 切出一个分支：

bash
git checkout -b feat/your-feature-name
# 或
git checkout -b fix/bug-description
提交改动（遵循 Conventional Commits）

推送到你的 fork

向 main 分支发起 Pull Request

分支命名
前缀	用途
feat/	新功能
fix/	Bug 修复
refactor/	重构
docs/	文档
style/	格式调整
test/	测试
chore/	杂项（依赖升级、CI 等）
提交信息规范
<type>(<scope>): <subject>

<body>

<footer>
示例：

feat(currency): 支持手动币对保存

新增「保存该币对手动汇率」按钮；读取时优先使用手动汇率。

Closes #42
PR 检查清单
提交前请确认：

□ 代码通过 python -m pytest
□ 新增功能已添加对应测试（可选）
□ 遵循 编码规范
□ 更新了相关文档 / README
□ 若涉及 UI 文案，已同步更新 config/i18n/zh_CN.json 和 en_US.json
编码规范
Python
遵循 PEP 8

行宽上限 88 字符

使用 类型注解（from __future__ import annotations）

文档字符串使用 Google 风格

文件头用 from __future__ import annotations，避免运行时类型求值开销

分层原则
core/ 不依赖 Qt：便于测试和 CLI 复用

ui/ 不直接操作 SQLite / 文件系统：走 core/ 的接口

面板之间不直接通信：走 ui/signals.py 的总线

命名约定
模块：snake_case.py

类：PascalCase

函数 / 变量：snake_case

常量：UPPER_SNAKE_CASE

私有成员：_leading_underscore

示例
python
"""模块级 docstring：一句话说明用途。"""
from __future__ import annotations

from core.errors import InputError


def calculate(principal: float, rate: float, years: int) -> dict:
    """计算贷款月供。

    Args:
        principal: 本金。
        rate: 年利率（%）。
        years: 年限。

    Returns:
        包含 ``monthly`` / ``total`` / ``interest`` 的字典。

    Raises:
        InputError: 参数非法时。
    """
    if principal < 0:
        raise InputError("本金不能为负", friendly_key="err_input")
    ...
测试
bash
# 全部测试
python -m pytest

# 仅冒烟测试
python -m pytest tests/test_smoke.py -v

# 覆盖率（可选）
python -m pytest --cov=core --cov=ui
国际化
项目使用 config/i18n/*.json 存放语言包。必须保持所有语言包的键集一致。

bash
# 检查一致性
python scripts/check_i18n.py

# 严格模式（空值也视为错误）
python scripts/check_i18n.py --strict
新增文案时：

在 zh_CN.json 加 key（基准语言）

在 en_US.json 加对应翻译

运行 check_i18n.py 确认

发布流程
仅供维护者参考：

更新 default_settings.json 中的 app_version

更新 core/cli.py 中的 APP_VERSION

打 tag：git tag -a v1.0.1 -m "Release v1.0.1"

推送 tag：git push origin v1.0.1

GitHub Actions 会自动构建并创建 Release

再次感谢你的贡献！🎉


---

## 4. `SECURITY.md`

```markdown
# 安全政策

## 支持的版本

我们为以下版本提供安全更新：

| 版本 | 支持状态 |
|------|----------|
| 最新 release | ✅ 支持 |
| 更早版本 | ❌ 不支持 |

**建议始终使用最新版本。**

## 报告漏洞

**请不要通过公开 Issue 报告安全漏洞。**

如果你发现了安全漏洞，请通过以下方式之一私下报告：

1. **GitHub 私有漏洞报告**（推荐）：
   在仓库页面点击 **Security** → **Report a vulnerability**
   https://github.com/Aa5000345/Calculator/security/advisories/new

2. **邮件**：若无法使用 GitHub，请通过仓库主页公开的联系方式
   联系维护者，标题注明 `[SECURITY]`。

## 报告内容

请尽可能提供以下信息：

- 漏洞类型（例如：命令注入、路径穿越、XSS 等）
- 受影响的文件 / 函数 / 版本
- 复现步骤（最小可复现示例）
- 潜在影响
- 建议的修复方案（如有）

## 响应时间

我们会在 **7 天内** 确认收到报告，并在 **30 天内** 给出初步评估。
修复版本发布后，我们会在此仓库的 Release Notes 中致谢报告者（除非你要求匿名）。

## 范围

以下**属于**安全范围：

- `core/engine.py` 的表达式求值沙箱绕过
- `core/crypto_tools.py` 的加密实现缺陷
- `core/secrets.py` 的密钥泄露
- 插件加载机制的任意代码执行
- 网络请求的 SSRF / 中间人攻击

以下**不属于**安全范围：

- 用户自己输入危险表达式（`core/engine.py` 已有沙箱，见 `_FORBIDDEN_SUBSTR`）
- 用户机器上的本地权限问题
- 依赖库自身的已知漏洞（请直接报告给上游）
- 社会工程学攻击

## 安全设计说明

MultiCalc 在设计上有以下安全考量：

1. **表达式沙箱**：`core/engine.py` 的 `_safety_check()` 拒绝
   `__` / `import` / `eval` / `exec` / `open` 等危险内容
2. **API 密钥隔离**：`core/secrets.py` 将密钥存到 `~/.multicalc/secrets.json`，
   与 `settings.json` 分离，导入/导出设置不会泄露密钥
3. **公式沙箱**：`core/data_table.py` 的 `_eval_formula` 使用 AST 白名单 +
   受限的 `__builtins__`
4. **网络请求**：所有外部请求都有超时；失败时优雅降级到离线数据

## 致谢

感谢所有负责任地披露安全问题的研究者。