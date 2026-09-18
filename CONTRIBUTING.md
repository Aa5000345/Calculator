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