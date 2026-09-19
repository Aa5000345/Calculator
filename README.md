# Multi Calculator

> 一款 **键盘驱动、随手可用** 的桌面多功能计算器 + 计算工作台。
> 基于 PySide6 + SymPy + SciPy + matplotlib + pint 构建，主要面向 Windows 11，
> 同时支持 macOS / Linux 桌面环境。

![Python](https://img.shields.io/badge/Python-3.10%2B-3776ab?logo=python&logoColor=white)
![PySide6](https://img.shields.io/badge/PySide6-6.6%2B-41cd52?logo=qt&logoColor=white)
![License](https://img.shields.io/badge/license-MIT-blue)
![Version](https://img.shields.io/badge/version-1.4.0-blue)
![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20macOS%20%7C%20Linux-lightgrey)

---

## 目录

- [✨ 特性总览](#-特性总览)
- [📥 安装](#-安装)
- [🚀 运行](#-运行)
- [⌨️ 快捷键](#️-快捷键)
- [🧠 核心能力](#-核心能力)
- [📋 面板一览](#-面板一览)
- [📖 文档](#-文档)
- [🆕 版本变更](#-版本变更)
- [📁 配置文件](#-配置文件)
- [🧪 测试](#-测试)
- [🔌 插件](#-插件)
- [🗂️ 项目结构](#️-项目结构)
- [🛠️ 开发](#️-开发)
- [❓ 常见问题](#-常见问题)
- [📄 许可证](#-许可证)
- [🙏 致谢](#-致谢)

---

## ✨ 特性总览

### 计算能力

- **31 个面板**，按 9 个分组组织：基础 / 转换 / 数据 / 数学 / 财务 / 工具 / 生产力 / AI / 系统
- **符号计算**：化简 / 展开 / 因式 / 求导 / 积分 / 极限 / 级数 / 求和 / 求积 / ODE / 优化 / 线性规划
- **数值计算**：SciPy 支撑的分布拟合 / 假设检验 / 回归 / 数值积分 / 最小化
- **贝叶斯推断**：Beta-Binomial / Normal-Normal / Gamma-Poisson / MCMC / 蒙特卡洛
- **矩阵运算**：18 种一元 + 7 种二元操作，LU / QR 分解，方程组求解
- **单位感知**：`1 km + 500 m` → `1.5 kilometer`
- **变量与函数**：`x = 5`、`f(x) = x^2 + 1`，跨会话持久化

### 输入方式

- **手写公式**（Ctrl+Shift+H）：画板 → pix2tex OCR（可选） → 表达式
- **截图 / 图片识别**（Ctrl+Shift+O）：打开 / 粘贴 / 拖放图片 → 表达式
- **剪贴板智能识别**：复制到像表达式的内容 → toast 提示 → 一键送基础面板
- **AI 助手**：自然语言 → 表达式（Ollama 本地 / OpenAI / Anthropic / 内置规则）
- **AI 多轮对话**：支持代词解析（"刚才的结果乘 2"）
- **AI 批量翻译**：多行 NL → 表达式表 → 一键送脚本面板
- **智能建议**：输入时气泡提示（绘图 / 换算 / 警告）
- **浮动计算器键盘**（Ctrl+Shift+K）：不抢焦点、跟随活跃输入框、DEG/RAD、2ⁿᵈ、内存槽
- **URL 参数**：`python main.py "?expr=2%2B3"` 启动即填表达式
- **CLI 模式**：`python main.py -e "1+1"` 直接输出（不启动 GUI）
- **CLI 管道**：`echo "1+1" | python main.py --pipe -o json`
- **Notebook 执行**：`python main.py --nb session.ipynb`

### 工作流

- **管道工作流**：`1 km | to m | * 2 | round(3)` 多步串接
- **脚本 / 批量计算面板**：多行表达式顺序执行，结果导出 CSV
- **数学笔记本**：可折叠 cell，Shift+Enter 执行，导出 `.mcnb` / `.ipynb`
- **数据运算**：列聚合 / 排序 / 筛选 / 分析，与数据表联动
- **实时结果预览**：输入 `2+3*4` 时下方灰色提示 `= 14`
- **结果差异对比**：自动显示 `+3` / `+70%` 变化徽章
- **跨面板「发送到…」**：任意结果一键流向单位 / 科学 / 数据表 / 片段 / 绘图 / 脚本 / 数据运算
- **可重放会话**（`.mcsession`）：导出 / 导入一整套计算流程
- **Jupyter Notebook 导出**：历史 → `.ipynb`
- **会话快照 / 时间机器**：Ctrl+Shift+Z 保存，Ctrl+Shift+Y 打开时间线
- **输入框版本历史**：🕘 按钮回滚到任意版本
- **分享卡片**：表达式 + 结果 + LaTeX + 二维码 → PNG

### 体验

- **命令面板**（Ctrl+K）：`= 2+2` 直接算、`> theme` 分类导航、拼音首字母搜索
- **QStatusBar**：显示当前面板 / 角度模式 / 内存值 / 汇率新鲜度 / 后台任务
- **Toast 通知**：所有成功提示非模态，不打断输入流
- **专注模式**（F11）：隐藏菜单栏 / 侧边栏，只留当前面板
- **快捷键速查表**（F1）+ 完整自定义
- **10+ 主题** + 可视化主题编辑器
- **i18n**：简体中文 / 繁体中文 / English / 日本語
- **内联校验**：输入错误时红框 + tooltip
- **后台计算**：长任务不冻结 UI，可取消
- **启动 Splash Screen**
- **首次运行欢迎页 + 快速导览**
- **插件系统**：可扩展面板 / 命令 / 主题 / 汇率源

### 加密能力

- **编码**：Base64 / Base64URL / Hex / URL / HTML / Base58 / Base32 / Base85 / Ascii85
- **哈希**：MD5 / SHA1 / SHA224 / SHA256 / SHA384 / SHA512 / SHA3-256 / SHA3-512 / BLAKE2b / BLAKE2s
- **对称加密**：AES-256-GCM / ChaCha20-Poly1305
- **非对称加密**：RSA (1024~4096) / Ed25519 / X25519
- **PQC（后量子密码）**：
  - ML-KEM-512/768/1024（FIPS 203）
  - ML-DSA-44/65/87（FIPS 204）
  - SLH-DSA-SHA2/SHAKE（FIPS 205）
- **密码哈希**：Argon2id / bcrypt
- **密钥派生**：Argon2id / Scrypt / PBKDF2
- **文件加密**：流式 AES-GCM（支持 GB 级文件，内存占用恒定）
- **TOTP**：Google Authenticator 兼容

---

## 📥 安装

### 1. 环境要求

- Python **3.10** 或更高
- Windows 11 / 10、macOS 12+、Linux（桌面环境 + Qt 运行库）

### 2. 安装依赖

```bash
pip install -r requirements.txt
```

### 3. 可选依赖

```bash
# 手写 / OCR（约 2GB）
pip install pix2tex

# 打包
pip install pyinstaller

# 测试
pip install pytest pytest-qt pytest-cov
```

---

## 🚀 运行

```bash
# GUI 模式
python main.py

# CLI 模式（不启动 GUI）
python main.py -e "1+1"
python main.py -e "sin(30)" --angle DEG
python main.py -e "1+1" --json
python main.py -e "1+1" -o csv

# 从 stdin 读多行
echo "1+1
2*3
sqrt(16)" | python main.py --pipe -o csv

# 执行 Jupyter Notebook
python main.py --nb session.ipynb

# URL 参数（启动 GUI 并预填表达式）
python main.py "?expr=2%2B3"
```

---

## ⌨️ 快捷键

完整列表见 [docs/SHORTCUTS.md](docs/SHORTCUTS.md)。常用：

| 快捷键 | 功能 |
|--------|------|
| `Ctrl+K` | 命令面板 |
| `Ctrl+Shift+K` | 浮动计算器键盘 |
| `Ctrl+,` | 设置 |
| `Ctrl+1~9` | 切换第 N 个可见模块 |
| `Ctrl+\` | 在分屏打开 |
| `Ctrl+Shift+Z` | 保存会话快照 |
| `Ctrl+Shift+Y` | 打开快照时间线 |
| `Ctrl+Shift+H` | 手写输入 |
| `Ctrl+Shift+O` | 截图 / 图片识别 |
| `F11` | 专注模式 |
| `F1` | 快捷键速查表 |

---

## 🧠 核心能力

### 符号计算

```python
sin(x)**2 + cos(x)**2     # → 1（化简）
(x + 1)**3                # → x³ + 3x² + 3x + 1（展开）
x^2 - 1                   # → (x - 1)(x + 1)（因式分解）
```

### 单位感知

```
1 km + 500 m              # → 1.5 kilometer
100 USD | to CNY          # → 727.5 CNY
1 km | to m | * 2         # → 2000 m（管道）
```

### 数学笔记本

```
a = 3
b = 4
sqrt(a^2 + b^2)           # → 5（跨 cell 共享变量）
```

### 变量持久化

```
x = 5                      # 保存到 ~/.multicalc/symbols.json
f(x) = x^2 + 1             # 跨会话可用
```

---

## 📋 面板一览

| 分组 | 面板 |
|------|------|
| **基础** | 基础计算、科学计算 |
| **转换** | 单位换算、汇率换算、进制转换、数字转换 |
| **数据** | 统计、概率、随机数、数据表、数据运算 |
| **数学** | 矩阵、绘图、3D 绘图、管道 |
| **财务** | 财务、日期 |
| **工具** | 位运算、加密工具、LaTeX、工具、字典 |
| **生产力** | 片段、计时器、剪贴板、脚本、笔记本 |
| **AI** | AI 助手 |
| **系统** | 历史记录、设置、快捷键 |

---

## 📖 文档

- 📘 [**完整使用指南**](docs/USER_GUIDE.md) —— 逐面板讲解
- ❓ [**常见问题**](docs/FAQ.md) —— 60+ 条目
- ⌨️ [**快捷键速查表**](docs/SHORTCUTS.md) —— 全局 / 输入框 / 面板专属
- 📝 [**CHANGELOG**](CHANGELOG.md) —— 版本变更历史

---

## 🆕 版本变更

详见 [CHANGELOG.md](CHANGELOG.md)。

- **v1.1.0**（当前）—— 31 个面板、PQC 加密、AI 多轮对话、管道、笔记本、字典、数字转换、快照、插件系统
- **v1.0.0** —— 首次发布，25 个面板

---

## 📁 配置文件

首次启动创建 `~/.multicalc/`：

```
~/.multicalc/
├── settings.json           # 用户设置
├── draft.json              # 输入框草稿
├── symbols.json            # 变量 / 函数
├── snippets.json           # 片段
├── history.db              # 历史（SQLite）
├── secrets.json            # API key（与 settings 分离）
├── usage.json              # 命令使用频率
├── shortcuts.json          # 自定义快捷键
├── glyph_favorites.json    # 符号收藏
├── ai_conversations.json   # AI 对话记录
├── recent_files.json       # 最近打开
├── input_history.json      # 输入框版本
├── snapshots/              # 会话快照
└── logs/app.log            # 日志
```

---

## 🧪 测试

```bash
python -m pytest
python -m pytest tests/test_smoke.py -v
python -m pytest --cov=core --cov=ui
```

**i18n 一致性检查**：

```bash
python scripts/audit_i18n.py
python scripts/audit_i18n.py --strict --check-order
```

---

## 🔌 插件

在 `plugins/` 下新建目录，包含 `plugin.json` + 可选 `__init__.py`：

```
plugins/
└── my_plugin/
    ├── plugin.json
    └── __init__.py
```

**`plugin.json`**：

```json
{
  "name": "My Plugin",
  "version": "1.0.0",
  "description": "一句话说明",
  "author": "你的名字",
  "enabled": true
}
```

**`__init__.py`**（用装饰器注册扩展点）：

```python
from core.plugin_api import (
    PanelPlugin, register_panel, register_command,
    register_theme,
)

@register_panel
class MyPanel(PanelPlugin):
    key = "my_panel"
    group = "工具"
    title_default = "My Panel"

    def create_widget(self, ctx):
        from PySide6.QtWidgets import QLabel
        return QLabel("Hello from plugin!")

@register_command("mycmd", "My Command", group="plugin")
def _cmd(ctx):
    print("Command executed")
```

支持的扩展点：**面板** / **命令** / **菜单** / **主题** / **汇率源** / **状态栏组件**。

详见 [CONTRIBUTING.md → 插件开发](CONTRIBUTING.md#插件开发)。

---

## 🗂️ 项目结构

```
Calculator/
├── main.py                      # 应用入口
├── requirements.txt
├── MultiCalc.spec.txt           # PyInstaller 配置
├── pytest.ini / conftest.py
│
├── core/                        # 计算内核（不依赖 Qt）
│   ├── engine.py                # 表达式解析 / 求值 / 格式化
│   ├── probability.py           # 概率与统计
│   ├── bayesian.py              # 贝叶斯推断
│   ├── mcmc.py / monte_carlo.py
│   ├── finance.py / bonds.py / options.py / tax.py
│   ├── dates.py / lunar.py / astro.py
│   ├── bits.py / bits_ext.py
│   ├── crypto_tools.py / crypto_advanced.py / file_crypto.py
│   ├── data_table.py / data_ops.py
│   ├── plot_sample.py / plot_advanced.py
│   ├── pipeline.py / notebook.py / notebook_export.py
│   ├── glyph_library.py / number_systems.py
│   ├── symbols.py / settings.py / history.py / i18n.py
│   ├── errors.py / logger.py / cli.py
│   ├── ai.py / ai_conversation.py / suggestions.py
│   ├── rates.py / crypto.py
│   ├── snapshot.py / input_history.py / recent_files.py
│   ├── shortcut_meta.py / shortcut_config.py / shortcut_scheme.py
│   ├── plugin_api.py / plugin_registry.py / plugins.py
│   ├── updater.py / version.py
│   └── pinyin_map.py
│
├── ui/                          # Qt 界面层
│   ├── main_window.py
│   ├── status_bar.py
│   ├── command_palette.py
│   ├── shortcuts.py / shortcuts_dialog.py
│   ├── theme_editor.py
│   ├── toast.py / tray.py / split_view.py
│   ├── signals.py / latex_widget.py
│   ├── panels/                  # 31 个面板
│   │   ├── registry.py / base.py / _common.py
│   │   └── ...
│   └── widgets/                 # 自定义组件
│       ├── calc_keyboard.py / keyboard_layouts.py
│       ├── focus_tracker.py / key_button.py
│       ├── handwriting.py / ocr_input.py
│       ├── file_crypto_tab.py / crypto_advanced_tab.py
│       ├── bayesian_tab.py / update_dialog.py
│       ├── plugin_manager.py / diff_badge.py
│       ├── shortcut_editor.py / input_history_widget.py
│       ├── snapshot_dialog.py
│       ├── empty_state.py / welcome_widget.py / quick_tour.py
│       ├── suggestion_widget.py / ai_chat_tab.py
│       └── plot_animation_widget.py
│
├── config/
│   ├── default_settings.json
│   ├── i18n/                    # 语言包
│   │   ├── zh_CN.json / zh_TW.json
│   │   └── en_US.json / ja_JP.json
│   ├── themes/                  # 主题文件
│   └── rates_offline.json
│
├── tests/
├── scripts/
│   ├── audit_i18n.py / check_i18n.py
│   ├── make_icon.py / build.py
│   └── gen_lang_skeleton.py
├── plugins/                     # 插件目录
├── docs/                        # 文档
│   ├── USER_GUIDE.md
│   ├── FAQ.md
│   └── SHORTCUTS.md
└── assets/
```

---

## 🛠️ 开发

参见 [CONTRIBUTING.md](CONTRIBUTING.md)。

**构建**：

```bash
python scripts/build.py --check       # 检查依赖
python scripts/build.py               # onefile
python scripts/build.py --onedir      # onedir（启动更快）
python scripts/build.py --no-upx --debug
python scripts/build.py --clean
```

---

## ❓ 常见问题

详见 [docs/FAQ.md](docs/FAQ.md)。

---

## 📄 许可证

[MIT](LICENSE)

---

## 🙏 致谢

- [PySide6](https://doc.qt.io/qtforpython/) — Qt for Python
- [SymPy](https://www.sympy.org/) — 符号计算
- [SciPy](https://scipy.org/) — 科学计算
- [matplotlib](https://matplotlib.org/) — 绘图
- [pint](https://pint.readthedocs.io/) — 单位
- [cryptography](https://cryptography.io/) — 加密
- 所有 [Contributors](https://github.com/Aa5000345/Calculator/graphs/contributors)
