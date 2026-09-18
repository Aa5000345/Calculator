# 贡献指南

感谢你有兴趣为 **MultiCalc** 做出贡献！本文档会帮助你快速上手。

---

## 目录

- [行为准则](#行为准则)
- [我可以贡献什么](#我可以贡献什么)
- [开发环境](#开发环境)
- [项目结构](#项目结构)
- [提交 Pull Request](#提交-pull-request)
- [编码规范](#编码规范)
- [测试](#测试)
- [国际化](#国际化)
- [主题开发](#主题开发)
- [插件开发](#插件开发)
- [发布流程](#发布流程)
- [常见问题](#常见问题)

---

## 行为准则

参与本项目即表示你同意遵守 [行为准则](CODE_OF_CONDUCT.md)。
请在互动中保持尊重和友善。任何违反行为准则的行为都可能被
维护者采取相应措施。

---

## 我可以贡献什么

| 类型 | 说明 | 入口 |
|------|------|------|
| 🐛 报告 Bug | 描述可复现的问题 | [新建 Issue](https://github.com/Aa5000345/Calculator/issues/new?template=bug_report.yml) |
| 💡 功能建议 | 提出新功能或改进 | [新建 Issue](https://github.com/Aa5000345/Calculator/issues/new?template=feature_request.yml) |
| 📖 改进文档 | 修正错别字、补充说明 | Pull Request |
| 🌍 翻译 | 新增语言包 | `config/i18n/*.json` |
| 🎨 主题 | 新增配色方案 | `config/themes/*.json` |
| 🔧 提交代码 | 修复 Bug / 实现功能 | Pull Request |
| 🧪 测试 | 补充测试用例 | `tests/` |
| 🔌 插件 | 扩展新面板 / 命令 | `plugins/` |

**新手友好**：Issue 中带 `good first issue` 标签的任务适合首次贡献。

---

## 开发环境

### 环境要求

- Python **3.10** 或更高
- Windows 11 / 10、macOS 12+、Linux（桌面环境 + Qt 运行库）
- Git 2.30+

### 克隆与安装

```bash
git clone https://github.com/Aa5000345/Calculator.git
cd Calculator

# 建议使用虚拟环境
python -m venv .venv

# Windows
.venv\Scripts\activate

# macOS / Linux
source .venv/bin/activate

# 安装运行依赖
pip install -r requirements.txt

# 安装开发依赖（测试 / 代码检查）
pip install pytest pytest-qt pytest-cov
```

### 运行

```bash
# GUI 模式
python main.py

# CLI 模式（不启动 GUI）
python main.py -e "1+1"
python main.py -e "sin(30)" --angle DEG
python main.py -e "1+1" --json

# URL 参数（启动 GUI 并预填表达式）
python main.py "?expr=2%2B3"
```

### 检查 i18n 一致性

```bash
python scripts/check_i18n.py
python scripts/check_i18n.py --strict
python scripts/check_i18n.py --check-order
```

### 生成图标

```bash
python scripts/make_icon.py          # 生成 ICO
python scripts/make_icon.py --png    # 生成 PNG
python scripts/make_icon.py --force  # 覆盖已存在的
```

---

## 项目结构

```
Calculator/
├── main.py                      # 应用入口（CLI 优先，延迟导入 Qt）
├── requirements.txt             # 运行依赖
├── pytest.ini                   # pytest 配置
├── conftest.py                  # pytest 全局 fixture
├── MultiCalc.spec.txt           # PyInstaller 打包配置
│
├── core/                        # 计算内核（不依赖 Qt）
│   ├── engine.py                # 表达式解析 / 求值 / 格式化
│   ├── probability.py           # 概率分布 / 假设检验 / 回归
│   ├── finance.py               # NPV / IRR / 摊销 / 折旧 / TVM
│   ├── bonds.py                 # 债券定价
│   ├── options.py               # Black-Scholes
│   ├── tax.py                   # 个税（中 / 美）
│   ├── dates.py                 # 日期 / 工作日 / 时区
│   ├── lunar.py                 # 农历
│   ├── astro.py                 # 日出日落
│   ├── bits.py / bits_ext.py    # 位运算 / CRC / 哈希
│   ├── crypto_tools.py          # AES / RSA / TOTP
│   ├── data_table.py            # 数据表 / 公式列
│   ├── plot_sample.py           # 绘图采样
│   ├── symbols.py               # 用户变量 / 函数
│   ├── settings.py              # 设置管理
│   ├── history.py               # SQLite 历史记录
│   ├── i18n.py                  # 国际化
│   ├── errors.py                # 异常类型
│   ├── logger.py                # 日志
│   ├── cli.py                   # CLI 解析
│   ├── ai.py                    # AI 翻译层
│   ├── rates.py                 # 汇率管理
│   └── ...
│
├── ui/                          # Qt 界面层
│   ├── main_window.py           # 主窗口
│   ├── status_bar.py            # 状态栏
│   ├── command_palette.py       # 命令面板（Ctrl+K）
│   ├── shortcuts.py             # 快捷键安装
│   ├── shortcuts_dialog.py      # 快捷键速查表（F1）
│   ├── settings_dialog.py       # 模块可见性对话框
│   ├── theme_editor.py          # 主题编辑器
│   ├── toast.py                 # 非模态通知
│   ├── tray.py                  # 系统托盘
│   ├── split_view.py            # 分屏视图
│   ├── signals.py               # 全局信号总线
│   ├── latex_widget.py          # LaTeX 渲染组件
│   ├── panels/                  # 25 个功能面板
│   │   ├── registry.py          # 面板注册表
│   │   ├── base.py              # CalcPanel 基类
│   │   ├── _common.py           # 共享工具
│   │   ├── basic.py             # 基础计算
│   │   ├── scientific.py        # 科学计算
│   │   └── ...
│   └── widgets/                 # 自定义组件
│       ├── calc_keyboard.py     # 浮动键盘
│       ├── keyboard_layouts.py  # 键盘布局 DSL
│       ├── focus_tracker.py     # 焦点追踪
│       ├── handwriting.py       # 手写输入
│       └── ocr_input.py         # 截图识别
│
├── config/
│   ├── default_settings.json    # 默认设置
│   ├── i18n/
│   │   ├── zh_CN.json           # 简体中文（基准）
│   │   └── en_US.json           # 英文
│   ├── themes/                  # 用户主题文件
│   │   ├── catppuccin.json
│   │   ├── dracula.json
│   │   └── ...
│   └── rates_offline.json       # 离线汇率缓存
│
├── tests/
│   ├── test_smoke.py            # 冒烟测试
│   └── ...
│
├── scripts/
│   ├── check_i18n.py            # i18n 一致性检查
│   └── make_icon.py             # 图标生成
│
├── plugins/                     # 插件目录
│   └── rates/                   # 汇率源插件
│
└── assets/
    └── icon.ico
```

---

## 提交 Pull Request

### 完整流程

1. **Fork 本仓库**
   点击右上角 **Fork** 按钮。

2. **克隆你的 fork**
   ```bash
   git clone https://github.com/<你的用户名>/Calculator.git
   cd Calculator
   git remote add upstream https://github.com/Aa5000345/Calculator.git
   ```

3. **同步上游**
   ```bash
   git fetch upstream
   git checkout main
   git merge upstream/main
   ```

4. **创建分支**
   ```bash
   git checkout -b feat/your-feature-name
   ```

5. **开发 + 提交**
   ```bash
   git add .
   git commit -m "feat(scope): 简短描述"
   ```

6. **推送到你的 fork**
   ```bash
   git push origin feat/your-feature-name
   ```

7. **发起 Pull Request**
   在 GitHub 上点击 **Compare & pull request**，填写 PR 模板。

### 分支命名

| 前缀 | 用途 | 示例 |
|------|------|------|
| `feat/` | 新功能 | `feat/pipeline-syntax` |
| `fix/` | Bug 修复 | `fix/bond-ytm-price` |
| `refactor/` | 重构 | `refactor/panel-base` |
| `docs/` | 文档 | `docs/update-readme` |
| `style/` | 格式调整 | `style/pep8-cleanup` |
| `test/` | 测试 | `test/stats-panel` |
| `chore/` | 杂项 | `chore/bump-deps` |
| `perf/` | 性能优化 | `perf/lazy-import` |

### 提交信息规范

遵循 [Conventional Commits](https://www.conventionalcommits.org/)：

```
<type>(<scope>): <subject>

<body>

<footer>
```

**type**：`feat` / `fix` / `docs` / `style` / `refactor` / `perf` / `test` / `chore` / `build` / `ci` / `revert`

**scope**（可选）：`engine` / `ui` / `panels` / `i18n` / `settings` / `plot` / `finance` / ...

**示例**：

```
feat(finance): 债券 Tab 新增 Market Price 输入框

之前 bond_ytm 直接使用面值当价格，导致 YTM 永远等于票面利率。
现在新增独立的 Market Price 输入框，用户可输入实际市场价格。

Closes #42
```

```
fix(ui): ResultView 右键菜单重复添加 Copy as JSON

去掉重复的 menu.addAction 调用。

Fixes #17
```

**破坏性变更**：在 footer 加 `BREAKING CHANGE:` 说明。

### PR 检查清单

提交前请确认：

- [ ] 代码通过 `python -m pytest`
- [ ] 遵循 [编码规范](#编码规范)
- [ ] 新增功能已添加对应测试（推荐）
- [ ] 更新了相关文档 / README
- [ ] 涉及 UI 文案的改动已同步更新 `zh_CN.json` 和 `en_US.json`
- [ ] 运行 `python scripts/check_i18n.py` 通过
- [ ] CLI 路径仍可用：`python main.py -e "1+1"`

### 审查流程

1. 提交 PR 后，维护者会在 **7 天内** 初步回复。
2. 可能会请求改动（Change Request），请在原分支上继续提交。
3. 通过后由维护者合并（推荐 **Squash merge**）。

---

## 编码规范

### Python 基础

- 遵循 **PEP 8**
- 行宽上限 **88** 字符（与 Black 默认一致）
- 使用 **类型注解**：`def foo(x: int) -> str:`
- 文件头用 `from __future__ import annotations`，避免运行时类型求值开销
- 文档字符串使用 **Google 风格**

### 分层原则（重要）

| 层 | 职责 | 禁止 |
|----|------|------|
| `core/` | 纯计算逻辑 | ❌ 不 import Qt / matplotlib |
| `ui/` | 界面展示 | ❌ 不直接操作 SQLite / 文件系统 |
| `ui/panels/` | 面板 UI | ❌ 面板之间不直接通信 |
| `ui/widgets/` | 可复用组件 | ❌ 不依赖具体面板 |

**为什么？**

- `core/` 不依赖 Qt → CLI 模式可复用、可单独测试
- `ui/` 不直接操作 SQLite → 未来可换存储后端
- 面板不直接通信 → 通过 `ui/signals.py` 总线，避免强耦合

### 命名约定

| 类型 | 约定 | 示例 |
|------|------|------|
| 模块 | `snake_case.py` | `data_table.py` |
| 包 | `snake_case/` | `panels/` |
| 类 | `PascalCase` | `BasicPanel` |
| 函数 / 方法 | `snake_case` | `calc_result()` |
| 变量 | `snake_case` | `user_input` |
| 常量 | `UPPER_SNAKE_CASE` | `MAX_ITEMS` |
| 私有成员 | `_leading_underscore` | `_worker` |
| 类型变量 | `PascalCase` | `T = TypeVar("T")` |

### 示例

```python
"""模块级 docstring：一句话说明用途。

必要时补充设计说明、依赖关系、注意事项。
"""
from __future__ import annotations

from core.errors import InputError


def calculate(principal: float, rate: float, years: int) -> dict:
    """计算贷款月供。

    Args:
        principal: 本金（>= 0）。
        rate: 年利率（%，>= 0）。
        years: 年限（> 0）。

    Returns:
        包含以下键的字典：
        - ``monthly``: 月供
        - ``total``: 还款总额
        - ``interest``: 利息总额

    Raises:
        InputError: 参数非法时。
    """
    if principal < 0:
        raise InputError(
            "本金不能为负",
            friendly_key="err_finance_neg",
        )
    ...
```

### 异常处理

- 使用项目自定义异常（`core/errors.py`）
- 不要裸 `except:`
- 捕获后要么处理，要么重新抛出并附带上下文

```python
# ✅ 推荐
try:
    result = parse_expr(s)
except SyntaxError as e:
    raise InputError(f"语法错误：{e}",
                     friendly_key="err_syntax") from e

# ❌ 不推荐
try:
    result = parse_expr(s)
except:
    pass
```

### 导入顺序

```python
# 1. 标准库
import os
import sys

# 2. 第三方库
import numpy as np
from PySide6.QtWidgets import QWidget

# 3. 项目内部
from core import engine
from core.errors import InputError
```

---

## 测试

### 运行测试

```bash
# 全部测试
python -m pytest

# 详细输出
python -m pytest -v

# 仅冒烟测试
python -m pytest tests/test_smoke.py -v

# 失败后立即停止
python -m pytest -x

# 覆盖率
python -m pytest --cov=core --cov=ui
python -m pytest --cov=core --cov=ui --cov-report=html
```

### 编写测试

- 测试文件放在 `tests/` 下
- 文件名：`test_*.py`
- 测试类：`Test*`
- 测试函数：`test_*`

```python
"""核心引擎冒烟测试。"""
from __future__ import annotations

import pytest

from core import engine


def test_basic_calc_addition():
    assert engine.basic_calc("1+1") == 2


def test_basic_calc_division_by_zero():
    from core.errors import MathError
    with pytest.raises(MathError):
        engine.basic_calc("1/0")
```

### 无 GUI 测试

CI 环境下无需显示，`conftest.py` 已设置 `QT_QPA_PLATFORM=offscreen`。

---

## 国际化

### 语言包位置

`config/i18n/<lang>.json`，目前支持：

- `zh_CN.json` — 简体中文（**基准语言**，新 key 从这里开始）
- `en_US.json` — 英文

### 新增文案

1. 在 `zh_CN.json` 添加 key：

   ```json
   {
     "my_new_label": "我的新标签"
   }
   ```

2. 在 `en_US.json` 添加对应翻译：

   ```json
   {
     "my_new_label": "My New Label"
   }
   ```

3. 在代码中使用：

   ```python
   label = QLabel(i18n.t("my_new_label", "默认文本"))
   ```

4. 运行检查：

   ```bash
   python scripts/check_i18n.py
   ```

### 占位符规范

使用 `{name}` 而非 `%s`：

```python
# ✅ 推荐
i18n.t("ai_key_set", "已设置：{k}").format(k=shown)

# ❌ 不推荐
i18n.t("ai_key_set", "已设置：%s") % shown
```

### 检查选项

| 命令 | 作用 |
|------|------|
| `python scripts/check_i18n.py` | 检查键集一致 + 占位符匹配 |
| `--base en_US` | 指定基准语言 |
| `--strict` | 空值也视为错误 |
| `--check-order` | 检查键顺序是否一致 |
| `--i18n-dir <path>` | 指定 i18n 目录 |

### 添加新语言

1. 复制 `en_US.json` 为 `ja_JP.json`（或目标语言代码）
2. 逐条翻译
3. 在 `ui/panels/settings.py` 的语言下拉框里加一项
4. 运行 `check_i18n.py` 确认

---

## 主题开发

### 主题文件格式

`config/themes/<name>.json`：

```json
{
  "name": "my_theme",
  "label": "My Theme",
  "palette": {
    "bg": "#1e1e2e",
    "fg": "#cdd6f4",
    "panel": "#313244",
    "accent": "#cba6f7",
    "border": "#45475a",
    "hover": "#45475a"
  }
}
```

### 字段说明

| 字段 | 含义 | 示例 |
|------|------|------|
| `name` | 唯一 ID（文件名一致） | `catppuccin` |
| `label` | 显示名 | `Catppuccin Mocha` |
| `palette.bg` | 背景色 | `#1e1e2e` |
| `palette.fg` | 前景（文字）色 | `#cdd6f4` |
| `palette.panel` | 面板背景 | `#313244` |
| `palette.accent` | 强调色（选中 / 高亮） | `#cba6f7` |
| `palette.border` | 边框色 | `#45475a` |
| `palette.hover` | 悬停色 | `#45475a` |

### 提交主题

1. 在 `config/themes/` 下添加 `<name>.json`
2. 启动应用，在「设置 → 主题」里应该能看到
3. 提交 PR，附上截图

也可以在应用内用「主题编辑器」可视化编辑后导出。

---

## 插件开发

### 目录结构

```
plugins/
└── my_plugin/
    ├── plugin.json          # 元数据（推荐）
    └── __init__.py          # 可选：注册回调
```

### `plugin.json`

```json
{
  "name": "My Plugin",
  "version": "1.0.0",
  "description": "一句话说明插件作用",
  "author": "你的名字",
  "enabled": true
}
```

### `__init__.py`

```python
"""插件入口：可选的 register() 回调。"""


def register(app_context):
    """应用启动时调用。

    Args:
        app_context: 包含以下键的字典：
            - settings: Settings 实例
            - i18n: I18n 实例
            - history: History 实例
            - main_window: MainWindow 实例
    """
    # 例如：注册一个新的汇率源
    from core.rates import RateSource, register_source

    class MyRateSource(RateSource):
        name = "my_source"
        label = "My Rate Source"
        priority = 50
        is_online = True

        def fetch(self):
            import requests
            r = requests.get("https://api.example.com/rates", timeout=10)
            return r.json()["rates"]

    register_source(MyRateSource())
```

### 汇率源插件

放在 `plugins/rates/`，会自动加载。详见 `core/rates.py` 的
`load_plugin_dir()`。

---

## 发布流程

**仅维护者**：

### 1. 更新版本号

- `config/default_settings.json` → `app_version`
- `core/cli.py` → `APP_VERSION`
- `README.md` 徽章（如有）

### 2. 更新 CHANGELOG（如有）

### 3. 打标签

```bash
git tag -a v1.0.1 -m "Release v1.0.1"
git push origin v1.0.1
```

### 4. GitHub Actions

推 tag 后自动触发构建：

- 打包 Windows exe
- 生成 Release Notes
- 上传构建产物

### 5. 手动构建（备用）

```bash
pip install pyinstaller
pyinstaller MultiCalc.spec.txt
# 产物：dist/MultiCalc.exe
```

---

## 常见问题

### Q: 为什么 `core/` 不依赖 Qt？

A: 这样 CLI 模式（`python main.py -e "..."`）可以在没有 GUI 的
环境下运行，也便于单元测试。核心计算逻辑本身与 UI 无关。

### Q: 面板之间怎么通信？

A: 通过 `ui/signals.py` 的全局信号总线：

```python
from ui.signals import bus

# 发送
bus().send_to_basic.emit("1+1")

# 接收（通常在 MainWindow 中）
bus().send_to_basic.connect(self._on_send_to_basic)
```

不要直接 import 另一个面板。

### Q: 为什么 `main.py` 里 CLI 优先？

A: CLI 模式只需要 `core/`，无需加载 Qt / matplotlib（节省
2~4 秒启动时间）。所以 `try_run_cli()` 在导入 Qt 之前调用。

### Q: 打包后 `config/` 目录找不到？

A: PyInstaller 会把 `config/` 解压到 `sys._MEIPASS`。
`MultiCalc.spec.txt` 已配置 datas。运行时用 `base_path` 定位。

### Q: 如何调试 Qt 崩溃？

A: 日志在 `~/.multicalc/logs/app.log`。也可以：

```bash
# Linux / macOS
QT_LOGGING_RULES="*.debug=true" python main.py

# Windows
set QT_LOGGING_RULES=*.debug=true
python main.py
```

### Q: 如何避免打包体积过大？

A: `MultiCalc.spec.txt` 的 `excludes` 已经排除 PyQt5/6、tkinter、
IPython 等。如果加了新依赖，记得检查是否需要排除子模块。

---

## 联系方式

- 🐛 [Issues](https://github.com/Aa5000345/Calculator/issues)
- 💬 [Discussions](https://github.com/Aa5000345/Calculator/discussions)
- 🔒 [安全漏洞](SECURITY.md)

---

再次感谢你的贡献！🎉