# Multi Calculator

> 一款**键盘驱动、随手可用**的桌面多功能计算器 + 计算工作台。  
> 基于 PySide6 + SymPy + SciPy + matplotlib + pint 构建，主要面向 Windows 11。

![Python](https://img.shields.io/badge/Python-3.10%2B-3776ab?logo=python&logoColor=white)
![PySide6](https://img.shields.io/badge/PySide6-6.6%2B-41cd52?logo=qt&logoColor=white)
![License](https://img.shields.io/badge/license-MIT-blue)

---

## ✨ 特性一览

- **25 个面板**，按 9 个分组组织：基础 / 转换 / 数据 / 数学 / 财务 / 工具 / 生产力 / AI / 系统
- **浮动计算器键盘**（`Ctrl+Shift+K`）：不抢焦点、跟随活跃输入框、DEG/RAD、2ⁿᵈ、内存槽、可拖动/缩放/置顶、几何持久化
- **命令面板（`Ctrl+K`）**：`= 2+2` 直接算、`>theme` 切主题、任意文本搜历史，支持中文模糊搜索
- **AI 助手面板**：自然语言 → 表达式（Ollama 本地 / OpenAI / Anthropic / 内置规则）
- **脚本 / 批量计算面板**：多行表达式顺序执行，可导出 CSV
- **实时结果预览**：输入 `2+3*4` 时下方灰色提示 `= 14`
- **跨面板"发送到…"**：任意结果一键流向单位/科学/数据表/片段/绘图
- **变量与函数定义**：`x = 5`、`f(x) = x^2 + 1`，跨会话持久化
- **单位感知计算**：`1 km + 500 m` → `1.5 kilometer`
- **统一结果面板**：右键复制为文本 / LaTeX / JSON / CSV，步骤折叠，耗时显示，错误卡片
- **10+ 套主题** + 可视化主题编辑器，支持导入导出
- **后台计算**：长任务不冻结 UI，可中途取消
- **分屏视图**：同一面板对照显示

---

## 📥 安装

### 1. 环境要求

- Python **3.10** 或更高
- Windows 11 / 10、macOS 12+、Linux（桌面环境 + Qt 运行库）

### 2. 安装依赖

```bash
pip install -r requirements.txt
```

### 3. 可选依赖（启用高级功能）

| 功能 | 依赖 | 安装命令 |
|---|---|---|
| 农历转换 | `lunardate` | `pip install lunardate` |
| 日出日落 | `astral` | `pip install astral` |
| 二维码生成 | `qrcode[pil]` | `pip install "qrcode[pil]"` |
| AI 助手（本地） | [Ollama](https://ollama.com/) | 安装后 `ollama pull qwen2.5:7b` |
| AI 助手（云端） | 无（使用 requests） | 在 AI 面板中配置 API key |

缺少这些包时，只有对应按钮会报"需要安装 xxx"，其他功能不受影响。

---

## 🚀 运行

```bash
python main.py
```

Windows 上也可以用：

```bash
py main.py
```

---

## ⌨️ 键盘快捷键

### 全局

| 快捷键 | 功能 |
|---|---|
| `Ctrl+K` | 打开命令面板 |
| `Ctrl+Shift+K` | 显示 / 隐藏浮动计算器键盘 |
| `Ctrl+,` | 打开设置面板 |
| `Ctrl+1` ~ `Ctrl+9` | 切换到第 N 个**可见**模块（受搜索框过滤影响） |
| `Ctrl+\` | 当前面板在分屏中打开 |
| `Ctrl+Shift+L` | 显示 / 隐藏侧边栏 |

### 面板内

| 快捷键 | 功能 |
|---|---|
| `Enter` | 计算（输入框内） |
| `Ctrl+Enter` | 计算（不限焦点） |
| `Esc` | 取消运行中的任务；基础面板中还用于清空输入 |
| `Ctrl+L` | 清空输入 |
| `↑` / `↓` | 召回历史表达式 |

### 浮动键盘

| 按键 | 功能 |
|---|---|
| `2ⁿᵈ` | 切换二级函数（sin⁻¹ / cos⁻¹ / x³ …） |
| `=` | 触发当前面板的 calc() |
| `C` | 清空当前输入框 |
| `⌫` | 退格 |
| `RAD` / `DEG` 按钮 | 切换角度模式 |
| `SCI` / `MINI` 按钮 | 切换布局 |
| `📌` | 置顶开关 |

---

## 🧠 核心能力

### 浮动计算器键盘

- **不抢焦点**：使用 `WA_ShowWithoutActivating` + `Qt.NoFocus` 按钮
- **智能插入**：数字后接字母自动补 `*`（`2pi` → `2*pi`）
- **跨面板**：焦点在哪个输入框，就往哪插
- **状态持久化**：布局 / 角度模式 / 置顶 / 几何位置全部记住

### AI 助手

三种接入方式，按优先级自动选择：

1. **Ollama**（本地）：自动探测 `localhost:11434`，模型默认 `qwen2.5:7b`
2. **OpenAI / Anthropic**（云端）：在 AI 面板点击"设置 API key"，密钥存于 `~/.multicalc/secrets.json`（与 settings.json 分离，避免导出泄露）
3. **本地规则**（离线兜底）：正则覆盖"X 的 Y%"、"X 的平方根"、"X 的 Y 次方"等常见模式

### 脚本 / 批量计算

- 每行一个表达式，`#` 开头或行尾 ` #` 为注释
- 支持变量定义（复用 `core.symbols`）
- 结果表格 + 一键导出 CSV

### 命令面板（`Ctrl+K`）

| 输入 | 行为 |
|---|---|
| `2+2` 或 `= 2+2` | 直接计算，结果复制到剪贴板 |
| `>theme` | 只匹配命令，忽略历史与计算 |
| `sin` | 同时显示模块、命令、历史记录（带 `↺` 前缀） |
| `键盘` | 匹配"显示计算器键盘"命令 |

### 变量与函数定义

在**科学计算**面板的表达式框直接写：

```
x = 5
y = x * 2
f(x) = x^2 + 1
g(x, y) = x^2 + y^2
```

- 定义会写入 `~/.multicalc/symbols.json`，重启后仍在
- "变量"标签页可查看、插入、删除、清空

### 跨面板"发送到…"

在任意 `ResultView` 上右键 → **发送到…** → 选择目标面板：

- **单位面板**：结果作为带单位文本发给 `UnitPanel.receive_text`
- **科学计算**：写入 expr 输入框
- **数据表**：追加为新行
- **片段管理器**：保存为片段
- **绘图面板**：添加为新曲线并立即绘制

### 数据表与公式列

**数据表**面板支持：

- 可编辑表头，右键菜单可重命名 / 设为公式列 / 清除公式
- 公式语法：`=[A] + [B]`，支持 `sqrt` / `log` / `exp` / `sin` / `cos` / `abs` / `min` / `max` / `round` / `pi` / `e`
- 导入 / 导出 CSV，导出 JSON
- 公式通过安全 AST 求值，禁止任意代码执行

### 主题系统

内置主题：

| 主题 | 风格 |
|---|---|
| `dark` / `light` / `high_contrast` | 默认三套 |
| `dracula` / `nord` / `one_dark` | 流行暗色 |
| `solarized_dark` / `solarized_light` | Solarized 双色 |
| `catppuccin` / `github_light` | 现代配色 |
| `system` | 跟随操作系统 |

通过 **设置 → 编辑主题…** 打开主题编辑器，可视化调色板可实时预览、保存为 `config/themes/<name>.json`。

---

## 📋 面板一览

| 分组 | 面板 | 说明 |
|---|---|---|
| **基础** | 基础计算 | 百分比 / 折扣 / 小费 / 税 + 内存槽 M1–M9 + 实时预览 |
| | 科学计算 | 化简 / 展开 / 因式 / 求解 / 求导 / 积分 / 极限 / 级数 / 求和 / 求积 / ODE / 数值积分 / 优化 / 线性规划 |
| **转换** | 单位换算 | 12 类单位，支持批量换算 + 快捷按钮 |
| | 汇率换算 | 多源 fallback + 缓存 + 离线回退 + 手动币对 + 加密货币 |
| | 进制转换 | 2–36 进制（含小数）、ASCII / Unicode、字节序、IEEE 754 |
| **数据** | 统计计算 | 描述统计、t 检验、相关矩阵、回归 + 图表 |
| | 概率分布 | 12 种分布 + PDF/CDF/分位数/抽样 + 假设检验 + 回归 + 绘图 |
| | 随机数 | 分布抽样、洗牌、UUID v1/3/4/5、密码生成 |
| | 数据表 | 可编辑表格 + 公式列 + CSV/JSON 导入导出 |
| **数学** | 矩阵 | 18 种一元 + 7 种二元运算、LU/QR 分解、CSV 导入导出、方程组求解 |
| | 2D 绘图 | 直角 / 极坐标 / 参数方程 / 隐函数 / 积分曲线，含导数叠加 |
| | 3D 绘图 | 曲面 + 等高线 + 切面 + 动画 + GIF 导出 |
| **财务** | 财务计算 | 贷款 / 复利 / NPV-IRR / 等额本金对比 / TVM / 折旧 / 债券 / 期权 / 个税 / XIRR |
| | 日期计算 | 日期差 / 加天数 / 倒计时 / 周信息 / 时区 / 时间戳 / 年龄 / 节假日 / 农历 / 日出日落 |
| **工具** | 位运算 | 补码 / 位宽 / 位运算 / CRC / Hash / 位图可视化 |
| | 加密工具 | Base64 / URL / HTML / 经典密码 / Hash / HMAC / AES-GCM / RSA-OAEP / TOTP / 密码强度 |
| | LaTeX 编辑器 | 模板库 + 实时预览 + PNG/SVG/PDF 导出 |
| | 工具 | 二维码 / JWT 解析 / 正则测试 / 颜色转换与对比度 |
| **生产力** | 片段管理 | 常用表达式收藏，双击复制到剪贴板 |
| | 计时器 | 倒计时 / 秒表 / 番茄钟 |
| | 剪贴板历史 | 监听系统剪贴板，可搜索、固定、清空 |
| | 脚本 | 多行表达式顺序执行 + CSV 导出 |
| **AI** | AI 助手 | 自然语言 → 表达式（Ollama / OpenAI / Anthropic / 本地规则） |
| **系统** | 历史记录 | SQLite 存储、分页、标签、收藏、导出 JSON/CSV |
| | 设置 | 语言 / 主题 / 字体 / 结果格式 / 汇率源 / 按钮布局 / 配色 / 导入导出 |

---

## 📁 配置文件

所有用户数据保存在 `~/.multicalc/`（Windows 为 `C:\Users\<你>\.multicalc\`）：

| 文件 | 内容 |
|---|---|
| `settings.json` | 用户设置（覆盖默认值） |
| `secrets.json` | AI / 云端服务的 API key（**独立存储**） |
| `draft.json` | 各面板未提交的草稿输入 |
| `history.db` | 历史记录（SQLite） |
| `symbols.json` | 用户定义的变量与函数 |
| `snippets.json` | 片段管理器的条目 |
| `logs/app.log` | 运行日志（滚动，最多保留 3 个备份） |

**项目内的配置文件**：

| 路径 | 用途 |
|---|---|
| `config/default_settings.json` | 出厂默认设置 |
| `config/i18n/*.json` | 语言包（`zh_CN` / `en_US`） |
| `config/themes/*.json` | 外挂主题 |
| `config/rates_offline.json` | 离线汇率缓存 |

---

## 🧪 测试

```bash
# 运行全部测试
pytest tests/ -v

# 只跑 engine
pytest tests/test_engine.py -v

# i18n 一致性检查
python scripts/check_i18n.py
```

测试覆盖：`core.engine`、`core.finance`、`core.dates`、键盘布局 DSL。

---

## 🔌 插件

### 汇率源插件

在 `plugins/rates/` 下放一个 `.py` 文件，定义一个继承 `RateSource` 的类，并实现 `register()`：

```python
# plugins/rates/my_source.py
from core.rates import RateSource, register_source

class MySource(RateSource):
    name = "my-source"
    label = "My Rate API"
    priority = 5
    is_online = True

    def fetch(self):
        import requests
        r = requests.get("https://example.com/api/rates", timeout=10)
        return r.json()["rates"]

def register():
    register_source(MySource())
```

### 通用插件

在 `plugins/<name>/` 下放 `__init__.py`，可选地定义元数据与 `register(app_context)`：

```python
# plugins/my_tool/__init__.py
NAME = "My Tool"
VERSION = "1.0"
DESCRIPTION = "示例插件"

def register(app_context):
    settings = app_context["settings"]
    main_window = app_context["main_window"]
```

---

## 🗂️ 项目结构

```
Calculator/
├── main.py                    # 入口
├── requirements.txt
├── config/
│   ├── default_settings.json
│   ├── i18n/{zh_CN,en_US}.json
│   ├── themes/*.json
│   └── rates_offline.json
├── core/                      # 业务逻辑（无 Qt 依赖或轻量依赖）
│   ├── engine.py              # 计算内核（含 DEG/RAD）
│   ├── symbols.py             # 变量/函数存储
│   ├── settings.py            # 设置管理 + 主题扫描
│   ├── history.py             # 历史记录（SQLite）
│   ├── i18n.py                # 国际化
│   ├── errors.py              # 统一异常
│   ├── worker.py              # QThread 任务包装
│   ├── ai.py                  # AI Provider 与 translate()
│   ├── secrets.py             # API key 独立存储
│   ├── finance.py / bonds.py / options.py / tax.py
│   ├── probability.py / units.py / dates.py / lunar.py / astro.py
│   ├── data_table.py / tools_ext.py / snippets.py
│   ├── crypto.py / crypto_tools.py / bits.py / bits_ext.py
│   └── ...
├── ui/                        # Qt 界面
│   ├── main_window.py         # 主窗口
│   ├── command_palette.py     # Ctrl+K 面板
│   ├── theme_editor.py        # 主题编辑器
│   ├── signals.py             # 跨面板信号总线
│   ├── shortcuts.py           # 快捷键安装
│   ├── split_view.py          # 分屏
│   ├── tray.py                # 系统托盘
│   ├── latex_widget.py        # LaTeX 渲染
│   ├── widgets/               # 浮动键盘与自定义 widget
│   │   ├── focus_tracker.py
│   │   ├── keyboard_layouts.py
│   │   ├── key_button.py
│   │   └── calc_keyboard.py
│   └── panels/                # 25 个功能面板
│       ├── registry.py        # 面板注册表
│       ├── _common.py         # ResultView / InlinePreviewBar
│       └── ...
├── scripts/
│   └── check_i18n.py          # i18n 一致性检查
├── tests/
│   ├── test_engine.py
│   ├── test_finance.py
│   ├── test_dates.py
│   └── test_keyboard_layouts.py
└── plugins/
    └── rates/                 # 汇率源插件目录
```

---

## 🛠️ 开发

### 添加一个新面板

1. 在 `ui/panels/` 下新建 `my_panel.py`，继承 `CalcPanel`：

   ```python
   from .base import CalcPanel

   class MyPanel(CalcPanel):
       module_key = "my_panel"
   ```

2. 在 `ui/panels/registry.py` 的 `all_panels()` 里加一行：

   ```python
   PanelSpec("my_panel", "工具", "my_panel", "My Panel",
             lambda c: MyPanel(c.settings, c.i18n, c.history)),
   ```

3. 在 `config/default_settings.json` 的 `visible_modules` 里加 `"my_panel": true`。

4. 如需语言包键值，在 `config/i18n/zh_CN.json` 与 `en_US.json` 里补充（保持两边键集一致，`scripts/check_i18n.py` 会帮你检查）。

不需要改 `main_window.py`。

### 日志

运行时日志位于 `~/.multicalc/logs/app.log`。出现异常时，错误卡片上的"查看日志"会显示路径。

---

## ❓ 常见问题

**Q：启动时报 `json.decoder.JSONDecodeError`？**  
A：多半是 `config/default_settings.json` 有多余的尾随逗号。用 `python -c "import json; json.load(open('config/default_settings.json', encoding='utf-8'))"` 定位到具体行。

**Q：某些功能点击后报"需要安装 xxx"？**  
A：见上文"可选依赖"表，安装对应包即可。

**Q：汇率获取失败？**  
A：默认使用离线汇率 `config/rates_offline.json`。可在**汇率换算 → 汇率源**切换数据源，或在设置里配置其他源。

**Q：浮动键盘不出现？**  
A：尝试 `Ctrl+Shift+K` 或 视图 → 计算器键盘；若被最小化到托盘，先在托盘菜单里"显示"。

**Q：AI 助手没有响应？**  
A：默认使用 Ollama。请先安装并启动 [Ollama](https://ollama.com/)，然后 `ollama pull qwen2.5:7b`。若想用云端模型，点击"设置 API key"。

**Q：如何恢复默认设置？**  
A：设置面板 → "恢复默认"，或直接删除 `~/.multicalc/settings.json`。

**Q：数据保存在哪？想清空所有数据？**  
A：删除 `~/.multicalc/` 目录即可（会同时清空历史、变量、片段、密钥、日志）。

---

## 📄 许可证

本项目使用 MIT 许可证。详见 `LICENSE`（若未随附，请按你的实际许可协议补充）。

---

## 🙏 致谢

[PySide6](https://doc.qt.io/qtforpython/) ·
[SymPy](https://www.sympy.org/) ·
[NumPy](https://numpy.org/) ·
[SciPy](https://scipy.org/) ·
[matplotlib](https://matplotlib.org/) ·
[pint](https://pint.readthedocs.io/) ·
[requests](https://requests.readthedocs.io/) ·
[holidays](https://holidays.readthedocs.io/) ·
[Babel](https://babel.pocoo.org/) ·
[cryptography](https://cryptography.io/) ·
[Ollama](https://ollama.com/)