# MultiCalc 使用指南

> 一款键盘驱动、随手可用的桌面多功能计算器 + 计算工作台。
> 基于 PySide6 + SymPy + SciPy + matplotlib + pint 构建。

---

## 目录

- [安装与启动](#安装与启动)
- [界面总览](#界面总览)
- [基础计算](#基础计算)
- [科学计算](#科学计算)
- [单位与货币](#单位与货币)
- [进制与位运算](#进制与位运算)
- [矩阵](#矩阵)
- [数据与统计](#数据与统计)
- [概率与绘图](#概率与绘图)
- [贝叶斯 / MCMC](#贝叶斯--mcmc)
- [财务](#财务)
- [日期](#日期)
- [加密工具](#加密工具)
- [文件加密](#文件加密)
- [字典（符号库）](#字典符号库)
- [数字系统转换](#数字系统转换)
- [LaTeX 编辑器](#latex-编辑器)
- [管道工作流](#管道工作流)
- [数学笔记本](#数学笔记本)
- [AI 助手](#ai-助手)
- [脚本 / 批量计算](#脚本--批量计算)
- [数据表](#数据表)
- [数据运算](#数据运算)
- [历史记录](#历史记录)
- [会话快照 / 时间机器](#会话快照--时间机器)
- [浮动键盘](#浮动键盘)
- [手写 / OCR 输入](#手写--ocr-输入)
- [命令面板](#命令面板)
- [设置](#设置)
- [主题](#主题)
- [插件系统](#插件系统)
- [快捷键自定义](#快捷键自定义)
- [自动更新](#自动更新)
- [命令行模式](#命令行模式)
- [性能与存储](#性能与存储)
- [故障排除](#故障排除)

---

## 安装与启动

### 环境要求

- Python **3.10** 或更高
- Windows 11 / 10、macOS 12+、Linux（桌面环境 + Qt 运行库）

### 安装

```bash
git clone https://github.com/Aa5000345/Calculator.git
cd Calculator

python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate

pip install -r requirements.txt
```

### 启动

```bash
# GUI
python main.py

# CLI（不启动 GUI）
python main.py -e "1+1"
python main.py -e "sin(30)" --angle DEG
python main.py -e "1+1" --json

# URL 参数（启动 GUI 并预填表达式）
python main.py "?expr=2%2B3"
```

### 首次启动

首次启动会自动创建用户目录 `~/.multicalc/`，包含：

```
~/.multicalc/
├── settings.json           # 用户设置（覆盖默认值）
├── draft.json              # 输入框草稿
├── symbols.json            # 用户变量 / 函数
├── snippets.json           # 片段收藏
├── history.db              # 历史记录（SQLite）
├── secrets.json            # API key（与 settings 分离）
├── usage.json              # 命令面板使用频率
├── shortcuts.json          # 自定义快捷键
├── glyph_favorites.json    # 符号收藏
├── ai_conversations.json   # AI 对话记录
├── recent_files.json       # 最近打开
├── input_history.json      # 输入框版本历史
├── snapshots/              # 会话快照
└── logs/
    └── app.log             # 日志
```

首次启动会弹出**快速导览**（5 步），之后不再自动弹出。

---

## 界面总览

```
┌──────────────────────────────────────────────────────────────┐
│ 文件  视图  工具  帮助                                          │  ← 菜单栏
├────────────┬─────────────────────────────────────────────────┤
│            │                                                 │
│  模块树    │              当前面板                            │
│  ├─ 基础   │                                                 │
│  ├─ 转换   │    [输入框]                                     │
│  ├─ 数据   │    [实时预览: = 14]                             │
│  ├─ 数学   │    [计算]  [取消]                               │
│  ├─ 财务   │                                                 │
│  ├─ 工具   │    [结果]                                       │
│  ├─ 生产力 │    [LaTeX 预览]  [步骤]                         │
│  ├─ AI     │                                                 │
│  └─ 系统   │                                                 │
│            │                                                 │
├────────────┴─────────────────────────────────────────────────┤
│ [基础]  RAD  内存: 0  汇率: 2 小时前                            │  ← 状态栏
└──────────────────────────────────────────────────────────────┘
```

### 侧边栏

- **搜索框**：输入模块名（支持拼音首字母，如 `jcjs` 搜「基础计算」）
- **模块树**：拖拽可调整顺序；双击分组头展开/收起
- **可见性按钮**：打开对话框，勾选显示哪些模块

### 状态栏

底部状态栏从左到右显示：

| 显示 | 含义 |
|------|------|
| `[基础]` | 当前面板名 |
| `RAD` / `DEG` | 角度模式 |
| `内存: 12.5` | 基础面板的内存值 |
| `汇率: 2 小时前` | 汇率缓存新鲜度 |
| `⏳ 计算中` | 后台任务运行中 |

---

## 基础计算

**路径**：侧边栏 → 基础

### 输入

在输入框直接输入表达式，按 Enter 或点击「计算」：

```
1+1
2 * (3 + 4)
100 / 7
sqrt(2)
sin(pi/6)
```

### 实时预览

输入 `2+3*4` 时，下方灰色提示 `= 14`。

### 百分比语法

| 输入 | 结果 |
|------|------|
| `20% off 100` | 80 |
| `8% on 100` | 108 |
| `15% of 200` | 30 |
| `tip 15% on 100` | 115（小费 15） |
| `tax 13% on 100` | 113（税 13） |

### 内存槽

底部 9 个按钮 `M1` ~ `M9`：

- **左键点击**：把槽里的值插入到输入框
- **右键点击**：把当前结果存入槽

### 格式化

右上角下拉框：

| 选项 | 效果 |
|------|------|
| Auto | 自动（默认保留完整精度） |
| Number | 保留 6 位有效数字 |
| Scientific | 科学计数法 |
| Fraction | 分数（如 `1/3`） |
| Percent | 百分比 |

### 内存变量

```
M+    内存 += 当前结果
M-    内存 -= 当前结果
MR    把内存插入到输入框
MC    清空内存
```

### 结果差异徽章

连续两次计算后，结果旁会显示变化：

- 数值差异：`+3` / `-0.02`
- 百分比：`(+70%)` / `(-4.0%)`
- 单位不同时只提示，不算差值

---

## 科学计算

**路径**：侧边栏 → 科学

### 操作列表

| 操作 | 说明 | 示例 |
|------|------|------|
| `数值计算` | 直接求值 | `sin(pi/6)` → `0.5` |
| `复数求值` | 保留复数 | `sqrt(-1)` → `I` |
| `化简` | simplify | `sin(x)^2 + cos(x)^2` → `1` |
| `展开` | expand | `(x+1)^3` → `x³+3x²+3x+1` |
| `因式分解` | factor | `x^2-1` → `(x-1)(x+1)` |
| `部分分式` | apart | `1/(x^2-1)` |
| `三角化简` | trigsimp | |
| `解方程` | solve | `x^2-1=0` → `[-1, 1]` |
| `解不等式` | 支持 `<=` `>=` `<` `>` | `x^2 < 4` |
| `解方程组` | 每行一个 | `x+y=3` / `x-y=1` |
| `求导` | diff | `sin(x)` → `cos(x)` |
| `积分` | integrate（可指定上下限） | `x^2` → `x³/3` |
| `数值积分` | SciPy quad | `exp(-x^2)` |
| `极限` | limit（可指定左右方向） | `sin(x)/x` → `1` |
| `级数展开` | Taylor / Laurent / FPS | `sin(x)` 到 6 阶 |
| `求和` | summation | `1/n^2` 从 1 到 ∞ |
| `求积` | product | |
| `ODE 求解` | dsolve | `y' = y` |
| `数值最小化` | SciPy minimize | |
| `线性规划` | SciPy linprog | JSON 参数 |

### 变量与函数

在输入框直接赋值：

```
x = 5
y = x * 2
f(x) = x^2 + 1
g(x, y) = x^2 + y^2
```

变量持久化到 `~/.multicalc/symbols.json`，**跨会话可用**。

切换到「变量」Tab 可以：

- 查看所有变量 / 函数
- 插入到输入框
- 删除
- 全部清空

### 常数库

点击「Constants…」按钮，从下拉列表选择：

| 分类 | 常见项 |
|------|--------|
| 数学 | π、e、φ（黄金比例）、γ（欧拉常数）、G（卡塔兰） |
| 物理 | c（光速）、h（普朗克）、ℏ、G（引力）、e（元电荷） |
| 天文 | au、ly（光年）、pc（秒差距） |
| 其它 | N_A、k_B、R、F、σ、μ₀、ε₀ |

### 结果格式

右上角下拉框：`text` / `unicode` / `latex`。

**unicode** 会把矩阵、分数渲染成美观形式：

```
⌈1  2⌉
⌊3  4⌋
```

---

## 单位与货币

**路径**：侧边栏 → 单位 / 汇率

### 单位换算

支持 13 个类别：

| 类别 | 单位 |
|------|------|
| 长度 | m, km, cm, mm, μm, nm, mi, yd, ft, in, nmi, ly, au |
| 质量 | kg, g, mg, μg, t, lb, oz, st, ct |
| 面积 | m², km², cm², ha, acre, ft², in² |
| 体积 | m³, L, mL, cm³, gal, qt, pt, cup, floz |
| 温度 | K, °C, °F, °R |
| 速度 | m/s, km/h, mph, knot, ft/s |
| 压力 | Pa, kPa, MPa, bar, atm, mmHg, psi |
| 能量 | J, kJ, cal, kcal, Wh, kWh, eV, BTU |
| 功率 | W, kW, MW, hp |
| 数据 | B, KB, MB, GB, TB, KiB, MiB, GiB, bit |
| 时间 | s, ms, μs, min, h, d, wk, yr |
| 角度 | rad, deg, grad, arcmin, arcsec |
| 其它 | — |

**用法**：

1. 选择「类别」
2. 输入「数值」
3. 选择「从」「到」
4. 点击「转换」

或点击快捷按钮直接转换。

**批量换算**：在「目标单位」输入逗号分隔的单位列表（如 `m,km,cm,mm`），点击「批量」，得到表格。

### 货币换算

- **源**：可切换（默认 `open.er-api.com`）
- **缓存**：6 小时。过期后自动尝试更新
- **离线**：勾选「使用离线汇率」时，只用本地缓存
- **手动汇率**：底部表格可以保存自定义币对（如 `USD->CNY = 7.25`）
- **加密货币**：选择币种，点击「获取加密货币价格」（CoinGecko 免费 API）

---

## 进制与位运算

**路径**：侧边栏 → 进制

### 4 个进制实时联动

| Tab | 说明 |
|-----|------|
| **Live** | 4 个输入框（Dec / Hex / Bin / Oct）实时同步 |
| **Convert** | 单个转换（支持 2~36 进制、小数） |
| **ASCII** | 文本 ↔ 编码 |
| **Bit tools** | 字节序交换、IEEE 754 |

### 位运算

**路径**：侧边栏 → 位运算

| Tab | 功能 |
|-----|------|
| Operations | and / or / xor / not / shl / shr，支持补码、位宽 |
| CRC | CRC32 / CRC16-CCITT / CRC16-Modbus |
| Hash | MD5 / SHA1 / SHA256 / SHA3 / BLAKE2 |
| Bitmap | 把整数渲染为位图 |

---

## 矩阵

**路径**：侧边栏 → 矩阵

### 18 种一元操作

`det`、`inv`、`transpose`、`trace`、`rank`、`rref`、`eigenvals`、`eigenvects`、`charpoly`、`adjugate`、`nullspace`、`columnspace`、`rowspace`、`lu`、`qr`、`exp`、`norm`、`power`

### 7 种二元操作

`mat_add`、`mat_sub`、`mat_mul`、`mat_hadamard`、`mat_kron`、`mat_solve`、`mat_lstsq`

### 输入矩阵

**Editor Tab**：

- 用 Rows / Cols 调整维度
- 单元格输入数字（支持符号如 `a`、`b`）

**Import CSV**：逗号 / 空格 / Tab 分隔均可。

### 求解 Ax=b

**Solver Tab**：

- A：每行一个，逗号/空格分隔
- b：逗号分隔
- 点击「Solve Ax=b」

---

## 数据与统计

**路径**：侧边栏 → 统计

### Describe Tab

输入数字（空格/逗号/分号分隔），得到：

- count、mean、median、std、var、min、max、range、sum、q1、q3

### Test Tab

| 检验 | 说明 |
|------|------|
| 单样本 t | 检验均值是否等于 μ₀ |
| 独立样本 t | 比较两组均值 |
| 配对 t | 配对差异 |
| 正态性（Shapiro） | 检验是否正态 |
| 单因素方差分析（ANOVA） | 两组以上比较 |

### Correlation Tab

每行一个变量：`名称: 值1 值2 ...`

得到相关矩阵。

### Regression Tab

- 简单回归（X, Y）
- 多元回归（X 矩阵，y）

### 发送到数据运算

Describe Tab 下点击「发送到数据运算」，可将当前数据发送到数据运算面板的「解析」区域。

---

## 概率与绘图

**路径**：侧边栏 → 概率

### 分布

12 个分布：`norm`、`t`、`chi2`、`f`、`binom`、`poisson`、`geom`、`expon`、`uniform`、`beta`、`gamma`、`lognorm`

参数用 JSON 传：

```json
{"loc": 0, "scale": 1}
```

操作：

- PDF / PMF
- CDF
- Quantile
- Sample
- 绘图（PDF / CDF / 直方图）

### 拟合

`fit` 按钮：给定数据，自动拟合到选定分布，返回估计参数 + KS 检验。

### 置信区间

`ci` 按钮：给数据 + α，返回均值的置信区间。

### 绘图

**路径**：侧边栏 → 绘图

- 支持 Cartesian / Polar / Parametric / Implicit / Integral / **Fill between**
- 多曲线同时绘制
- 可显示导数
- **多 Y 轴**（勾选「启用右 Y 轴」）
- LaTeX 标签
- **从数据表导入**（读取 A、B 两列）
- **极坐标动画**（弹出 PolarAnimationWidget，可导出 GIF）
- 导出 PNG / PDF / SVG

---

## 贝叶斯 / MCMC

**路径**：侧边栏 → 概率 → 贝叶斯 Tab

### 共轭先验

| 模型 | 说明 | 输入 |
|------|------|------|
| Beta-Binomial | 成功率估计 | α, β, 成功数, 失败数 |
| Normal-Normal | 均值估计（已知方差） | μ₀, σ₀, x̄, σ, n |
| Gamma-Poisson | 计数率估计 | α, β, 计数列表 |

输出：后验参数、均值、众数、方差、95% / 99% 可信区间。

### MCMC

- **Metropolis-Hastings**：1D 正态 / 1D 双峰 / 2D 相关正态
- **Gibbs 采样**（供扩展）
- 参数：采样数、Burn-in、Proposal σ、Seed
- 输出：均值 / 标准差 / **ESS** / **接受率** / **MAP** / 分位数 / **lag-1 自相关**

### 蒙特卡洛

- **π 估算**：`4 × 圆内比例`
- **1D 积分**：`f(x)` + 区间 + 采样数
- **ND 积分** / **对偶变量方差缩减**（供扩展）

---

## 财务

**路径**：侧边栏 → 财务

| Tab | 功能 |
|-----|------|
| Loan | 贷款月供（等额本息 / 等额本金） |
| Compound | 复利终值 |
| NPV / IRR | 现金流分析（支持多解检测） |
| Compare | 两种方案对比 |
| TVM | 时间价值（5 个变量已知 4 个求第 5 个） |
| Depreciation | 折旧（直线 / 年数总和 / 双倍余额） |
| Bond | 债券定价 + YTM（**需市场价**，独立输入框） |
| Option | Black-Scholes + Greeks |
| Tax | 个税（中 / 美） |
| XIRR | 不规则现金流 IRR |

---

## 日期

**路径**：侧边栏 → 日期

- 日期差（工作日、节假日）
- 加天数
- 倒计时
- 周信息（ISO 周、季度、年内第几天）
- 时区转换
- 时间戳 ↔ 日期
- 精确年龄
- **农历**（需 lunardate）
- **日出日落**（需 astral）

---

## 加密工具

**路径**：侧边栏 → 加密工具

### 编码 Tab

| Tab | 支持 |
|-----|------|
| Encode | Base64 / Base64URL / Hex / URL / HTML / Base58 / Base32 / Base85 / Ascii85 |

### 经典密码

ROT13、Caesar

### 哈希 / HMAC

MD5、SHA1、SHA224、SHA256、SHA384、SHA512、SHA3-256/512、BLAKE2b/2s

### AES

AES-GCM 加密 / 解密（密钥 128/192/256 位）

### RSA

生成密钥（1024~4096 位）、加密、解密

### TOTP

两步验证码（Google Authenticator 兼容）

### 密码强度

估算熵值 + 分级

### 文件加密 Tab

见下节。

### 高级加密 Tab（PQC）

包含 9 个子 Tab：

| 子 Tab | 说明 |
|--------|------|
| 后端能力 | 探测当前环境支持哪些算法（OpenSSL 版本 / PQC） |
| ML-KEM | 密钥封装（FIPS 203），512/768/1024 |
| ML-DSA | 数字签名（FIPS 204），44/65/87 |
| SLH-DSA | 哈希签名（FIPS 205），SHA2/SHAKE × 128/192/256 |
| ChaCha20 | ChaCha20-Poly1305（RFC 8439） |
| Ed25519 | 快速签名 + 验证 |
| X25519 | 密钥交换 |
| Argon2/bcrypt | 密码哈希 |
| 编码 | Base58 / Base32 / Base85 / Ascii85 |

---

## 文件加密

**路径**：加密工具 → 文件加密

### 加密 Tab

| 字段 | 说明 |
|------|------|
| 源文件 | 任意文件（GB 级） |
| 输出文件 | `.mcenc` 格式 |
| 加密算法 | AES-256-GCM / ChaCha20-Poly1305 |
| 密码 | 用于密钥派生 |
| KDF | PBKDF2 / Scrypt / Argon2id |
| 迭代次数 | PBKDF2 有效，建议 60 万 |
| 分块大小 | 256 KiB ~ 16 MiB |

**特点**：

- 流式处理：内存占用恒定（约等于块大小）
- 认证加密：篡改会被检测
- 可取消：中途可停止
- 进度条实时显示

### 解密 Tab

选择 `.mcenc` 文件 + 密码 + 输出路径。

**兼容性**：自动识别 v1（旧版）和 v2 格式。

### 文件信息 Tab

不解密，只读取文件头，显示：

- 格式版本
- 加密算法
- KDF 类型
- 原始大小
- 文件大小

---

## 字典（符号库）

**路径**：侧边栏 → 字典

15 个分类，约 500+ 符号：

| 分类 | 内容 |
|------|------|
| 希腊字母 | α β γ … Α Β Γ |
| 数学运算 | + − × ÷ ± ∓ √ ∑ ∏ ∫ |
| 关系符 | = ≠ ≈ ≤ ≥ ≪ ≫ |
| 集合与逻辑 | ∈ ∉ ∪ ∩ ∅ ∀ ∃ ¬ ∧ ∨ |
| 微积分 | ∫ ∬ ∭ ∮ ∂ ∇ ′ ″ |
| 线性代数 | ⊕ ⊗ ⊙ ⟨ ⟩ ‖ † |
| 箭头 | → ⇒ ⇔ ↦ ↪ ⟶ ⟹ |
| 序号/圈码 | ① ② ③ ⑴ ⒈ Ⅰ Ⓐ Ⓑ ❶ |
| 货币 | $ € £ ¥ ₹ ₽ ₿ Ξ |
| 单位 | ° ′ ″ ℃ ℉ Ω µ |
| 上下标 | ⁰ ¹ ² ₀ ₁ ₂ ₐ ₑ ᵢ |
| 分数 | ½ ⅓ ¼ ⅕ ⅛ |
| 括号 | ( ) [ ] { } ⟨ ⟩ ⌈ ⌉ |
| 角度/温度 | ° ′ ″ ℃ ℉ °R |
| 其他 | § ¶ † ‡ • ○ ● □ ■ ☆ ★ ✓ ✗ |

### 使用

- **单击**：复制到剪贴板
- **双击 / 右键**：插入到当前焦点输入框
- **右键菜单**：复制 / 插入 / 复制 LaTeX / 复制 Unicode / 收藏 / 查看详情

### 搜索

输入中文名、英文名或 LaTeX 命令：

- `alpha` → α
- `阿尔法` → α
- `\alpha` → α

---

## 数字系统转换

**路径**：侧边栏 → 数字转换

| 系统 | 示例 |
|------|------|
| 阿拉伯数字 | 2024 |
| 罗马数字 | MMXXIV |
| 中文小写 | 二千零二十四 |
| 中文大写 | 贰仟零贰拾肆 |
| 英文单词 | two thousand twenty-four |
| 摩尔斯数字 | ..--- ----- ..--- ....- |

### 使用

1. 选择「源系统」
2. 输入值
3. 选择「目标系统」
4. 点击「转换」

**交换按钮 ⇄**：快速交换源/目标。

底部「对照表」显示 1~20 的所有系统写法。

---

## LaTeX 编辑器

**路径**：侧边栏 → LaTeX 编辑器

- 输入 LaTeX 源码，实时渲染预览
- 内置模板（二次方程、欧拉公式、泰勒展开…）
- 导出 PNG / SVG / PDF
- 复制 LaTeX
- **→ 表达式**：把当前 LaTeX 转成 SymPy 表达式，可一键发送到科学面板

---

## 管道工作流

**路径**：侧边栏 → 管道

把多步计算串起来：

```
1 km | to m
1 km | to m | * 2 | round(3)
100 USD | to CNY
5 | sqrt | round(2)
0.1 | as fraction
```

### 步骤类型

| 类型 | 语法 | 示例 |
|------|------|------|
| 单位换算 | `to <unit>` | `to m` |
| 货币换算 | `to <CUR>` | `to CNY` |
| 格式化 | `as <fmt>` | `as fraction` |
| 函数调用 | `<name>(<args>)` | `round(3)` |
| 算术 | `<op> <expr>` | `* 2` / `+ 5` / `** 2` |

### 占位符

`_` 代表上一步结果：

```
5 | _ * 2 | _ + 3
```

### 步骤表格

执行后，每一步的中间结果都显示在表格里，方便检查。

---

## 数学笔记本

**路径**：侧边栏 → 笔记本

类似 Jupyter 的轻量笔记本：

- **Code cell**：可执行表达式
- **Markdown cell**：文档说明
- **Shift+Enter**：执行当前 cell 并跳到下一个
- **Ctrl+Enter**：执行当前 cell（不跳转）
- **Ctrl+Shift+Return**：运行全部
- **Ctrl+S**：保存为 `.mcnb`
- **Ctrl+Shift+C**：新增 code cell
- **Ctrl+Shift+M**：新增 markdown cell

### 跨 cell 变量共享

```
Cell 1:  a = 3
Cell 2:  b = 4
Cell 3:  sqrt(a^2 + b^2)    → 5
```

变量通过 `core.symbols` 自动持久化。

### 保存 / 导出

- `.mcnb`：自有格式（JSON）
- `.ipynb`：Jupyter Notebook 格式（可在 Jupyter 中打开）

---

## AI 助手

**路径**：侧边栏 → AI

### 单条翻译

把自然语言转成表达式：

```
100 的 15%              → 100 * 15 / 100
3 的平方根              → sqrt(3)
20 的 3 次方            → 20**3
factorial of 5          → factorial(5)
```

**Provider 链**（按 auto 顺序）：

1. Ollama（本地 LLM，自动探测 `localhost:11434`）
2. OpenAI（需 API key）
3. Anthropic（需 API key）
4. 本地规则（永远可用）

API key 存到 `~/.multicalc/secrets.json`，与设置文件分离。

### 批量翻译

多行输入，一次翻译，结果表可一键发送到脚本面板。

### 多轮对话

在「对话」Tab：

```
你: 100 的 15%
AI: 100 * 15 / 100 = 15

你: 刚才的结果乘 2
AI: (100 * 15 / 100) * 2 = 30
```

代词（「它」「那个」「刚才」「上一步」）会自动解析为上一个表达式。

会话自动持久化到 `~/.multicalc/ai_conversations.json`。

### 智能建议

输入时，输入框旁会弹出「💡」气泡，给出建议：

- 输入 `sin(x)` → 建议「试试绘制它的图像？」
- 输入 `100 USD` → 建议「换算 CNY？」
- 输入 `25!` → 建议「结果巨大，可能耗时较长」

在设置中可关闭。

---

## 脚本 / 批量计算

**路径**：侧边栏 → 脚本

每行一个表达式：

```
a = 3
b = 4
sqrt(a^2 + b^2)

100 * 15 / 100
sin(pi / 6)
factorial(5)
```

`#` 开头或 ` #` 之后的为注释。

点击「运行全部」，结果表显示每行结果。可导出 CSV。

---

## 数据表

**路径**：侧边栏 → 数据表

- 可编辑表头（右键重命名）
- 公式列：`=[A] + [B] * 2`
- 支持 `sqrt` / `log` / `exp` / `sin` / `cos` / `abs` 等
- 单元格变化时自动重算（防抖 350ms）
- 导入 / 导出 CSV、JSON
- **发送到数据运算**：一键把整个表格发到数据运算面板

---

## 数据运算

**路径**：侧边栏 → 数据运算

### 输入

三种方式：

1. 直接粘贴 CSV / TSV
2. 从 CSV 文件导入
3. 从「数据表」面板读取

### 4 个 Tab

| Tab | 功能 |
|-----|------|
| 聚合 | 18 种聚合操作（sum / mean / std / q1 / skew / kurt ...） |
| 排序 | 按列升序 / 降序 |
| 筛选 | 11 种筛选操作（`==` / `>` / `contains` / `is_empty` ...） |
| 分析 | 每列完整描述统计 |

### 与统计面板联动

「聚合」Tab 下点击「发送到统计面板」，把当前列数据发送到统计面板。

---

## 历史记录

**路径**：侧边栏 → 历史记录

- 分页显示（每页 100 条）
- 搜索、按模块过滤、按标签过滤
- 收藏 / 保存值 / 编辑标签
- 双击复用表达式
- 右键菜单：复用 / 复制 / 删除
- 导出 JSON / CSV / `.mcsession` / `.ipynb`
- **空历史时**显示引导卡片

---

## 会话快照 / 时间机器

**快捷键**：`Ctrl+Shift+Z` 保存，`Ctrl+Shift+Y` 打开时间线

### 保存内容

- Settings 差异（只保存与默认不同的键）
- 变量 / 函数
- 片段
- 草稿
- 面板状态

### 操作

- 新建 / 恢复 / 删除 / 重命名 / 导出
- 对比两个快照（settings / symbols / drafts / panel_states 分三栏）

### 使用场景

- **调参对比**：调好参数 → 保存快照 → 再调 → 对比两个快照 → 选最优
- **实验回滚**：尝试激进设置 → 不理想 → 一键恢复
- **多套配置**：为「日常」「演示」「重活」各存一个快照

---

## 浮动键盘

**呼出**：`Ctrl+Shift+K`，或点击面板右上角的 ⌨ 按钮

**特点**：

- **不抢焦点**：可以边看主窗口边点击
- **跟随活跃输入框**：自动插入到当前焦点输入框
- **DEG / RAD**：切换角度模式
- **2ⁿᵈ**：切换二级函数（`sin` → `sin⁻¹`）
- **内存槽**：MC / MR / M+ / M- / MS
- **智能插入**：
  - 数字后接字母自动补 `*`
  - `(` 结尾时自动补 `)`，光标停在中间
- **按模块切换布局**：14 个专属布局 + 通用布局

---

## 手写 / OCR 输入

### 手写输入

**快捷键**：`Ctrl+Shift+H`

- 用鼠标 / 触控笔书写
- 点击「识别」（需 `pip install pix2tex`，首次加载约 30~60 秒）
- 或直接手动输入
- 结果插入到打开前的焦点输入框

### 图片识别

**快捷键**：`Ctrl+Shift+O`

- 打开图片 / `Ctrl+V` 粘贴 / 拖放
- 支持 pix2tex 或 OpenAI 视觉

---

## 命令面板

**快捷键**：`Ctrl+K`

### 输入规则

| 输入 | 行为 |
|------|------|
| `1+1` 或 `= 1+1` | 直接计算，结果内联显示 |
| `>` | 显示分类列表 |
| `> theme` | 只匹配 theme: 前缀的命令 |
| `jcjs` | 拼音首字母搜索（基础计算） |
| 其它 | 模糊搜索命令 + 历史 |

### 特点

- **越用越顺手**：按使用频率排序（`~/.multicalc/usage.json`）
- **Tab 切换焦点**：在搜索框和列表间切换
- **Enter 执行**：计算结果显示后按 Enter 复制到剪贴板

---

## 设置

**路径**：侧边栏 → 设置

### 常用设置

| 项 | 说明 |
|----|------|
| 语言 | 简体中文 / 繁體中文 / English / 日本語 |
| 主题 | 内置 8 种 + 自定义 |
| 字体 | 任意系统字体 |
| 字号 | 8~30 pt |
| 结果格式 | text / unicode / latex |
| 有效数字 | 0（自动）~ 20 |
| 科学计数法 | 开关 |
| 分数显示 | 开关 |
| 百分比 | 开关 |
| 汇率源 | `open.er-api.com` / `exchangerate.host` |
| 按钮布局 | JSON 数组（基础面板按钮） |

### 搜索设置项

顶部搜索框可以按名称过滤设置项。

### 导入 / 导出

- 导出：保存为 JSON
- 导入：从 JSON 恢复（不会覆盖密钥）

---

## 主题

### 内置主题

| 名称 | 风格 |
|------|------|
| dark | 深色（默认） |
| light | 浅色 |
| high_contrast | 高对比 |
| catppuccin | Catppuccin Mocha |
| dracula | Dracula |
| github_light | GitHub Light |
| nord | Nord |
| one_dark | One Dark |
| solarized_dark | Solarized Dark |
| solarized_light | Solarized Light |

### 主题编辑器

**设置 → 编辑主题…**

- 可视化选择 6 个颜色（bg / fg / panel / accent / border / hover）
- 保存到 `config/themes/<name>.json`
- 「应用」按钮临时预览
- 「保存」按钮永久生效

### 自定义主题文件

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

放到 `config/themes/` 即可。

---

## 插件系统

**路径**：设置 → 插件，或菜单 → 工具 → 插件…

### 目录结构

```
plugins/
└── my_plugin/
    ├── plugin.json          # 元数据
    └── __init__.py          # 可选：注册回调
```

### `plugin.json`

```json
{
  "name": "My Plugin",
  "version": "1.0.0",
  "description": "一句话说明",
  "author": "你的名字",
  "enabled": true
}
```

### `__init__.py`

```python
from core.plugin_api import (
    PanelPlugin, register_panel, register_command,
    register_theme, register_menu, register_rate_source,
    register_status_widget,
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


register_theme(
    name="example_theme",
    label="Example Theme",
    palette={
        "bg": "#1a1b26", "fg": "#c0caf5",
        "panel": "#24283b", "accent": "#7aa2f7",
        "border": "#414868", "hover": "#3b4261",
    })
```

### 6 种扩展点

| 扩展点 | 装饰器 / 函数 |
|--------|--------------|
| 面板 | `@register_panel` |
| 命令 | `@register_command` |
| 菜单 | `@register_menu` |
| 主题 | `register_theme(...)` |
| 汇率源 | `register_rate_source(...)` |
| 状态栏组件 | `register_status_widget(...)` |

### 插件管理器

**设置 → 插件** / **菜单 → 工具 → 插件…**

- 查看已安装插件
- 勾选 / 取消启用
- 查看注册内容
- 导出注册表快照

---

## 快捷键自定义

**路径**：侧边栏 → 快捷键，或 `F1` → 自定义 Tab

### 操作

- **双击命令** → 录制新键位
- **右键** → 清除 / 恢复默认 / 复制命令 ID
- **冲突的键位**会标红
- 修改**立即生效**

### 预设方案

| 方案 | 说明 |
|------|------|
| default | 项目默认 |
| vscode | 命令面板用 `Ctrl+Shift+P` |
| jetbrains | 命令面板用 `Ctrl+Shift+A` |
| emacs | 尽量接近 Emacs |

### 导入 / 导出

- **导出**：JSON 格式，带版本号
- **导入**：可选「合并」（保留未在文件中的命令）或「覆盖」

---

## 自动更新

**路径**：菜单 → 工具 → 检查更新

### 特性

- **启动 5 秒后自动检查**（7 天一次）
- 从 GitHub Releases API 获取
- 流式下载 + 进度 + 速度显示
- **SHA256 校验**（如 release 提供 checksum）
- 平台匹配（Windows / macOS / Linux）
- **不自动安装**，下载完成后手动替换

### 手动检查

菜单 → 工具 → 检查更新

---

## 命令行模式

### 基本用法

```bash
python main.py -e "1+1"
python main.py --expr "1+1"
python main.py --cli "1+1"
python main.py "1+1"              # 裸表达式
```

### 选项

| 选项 | 说明 |
|------|------|
| `-e, --expr EXPR` | 计算 EXPR |
| `--cli EXPR` | 同 `--expr` |
| `--pipe` | 从 stdin 逐行读取 |
| `--nb FILE` | 执行 Jupyter Notebook |
| `-o, --output FORMAT` | `text` / `json` / `csv` |
| `--json` | 等价于 `-o json` |
| `--csv` | 等价于 `-o csv` |
| `--angle MODE` | `RAD` 或 `DEG` |
| `--no-format` | 不做数字格式化 |
| `--quiet` | 只输出结果 |
| `-h, --help` | 帮助 |
| `-v, --version` | 版本号 |

### 示例

```bash
python main.py -e "sqrt(2)"
python main.py -e "sin(30)" --angle DEG
python main.py -e "1+1" --json
echo "1+1
2*3" | python main.py --pipe -o csv
python main.py --nb session.ipynb
python main.py "?expr=2%2B3"
```

---

## 性能与存储

### 启动速度

- **CLI 模式**：不加载 Qt / matplotlib，约 0.3 秒
- **GUI 模式**：首次启动约 2~3 秒（取决于磁盘）
- **Splash Screen**：启动时显示图标

### 内存占用

- 空载：约 150~250 MB
- 加密大文件：约 1~2 倍块大小（默认 1 MiB）

### 存储位置

```
~/.multicalc/
├── settings.json           # 用户设置
├── draft.json              # 输入框草稿
├── symbols.json            # 变量 / 函数
├── snippets.json           # 片段
├── history.db              # 历史（SQLite，最多 5000 条）
├── secrets.json            # API key
├── usage.json              # 命令使用频率
├── shortcuts.json          # 快捷键
├── glyph_favorites.json    # 符号收藏
├── ai_conversations.json   # AI 对话
├── recent_files.json       # 最近打开
├── input_history.json      # 输入框版本
├── snapshots/              # 会话快照
└── logs/app.log            # 日志（滚动，最多 3 个备份）
```

**清理**：直接删除 `~/.multicalc/` 即可重置所有用户数据。

---

## 故障排除

### 启动崩溃

1. 查看 `~/.multicalc/logs/app.log`
2. 尝试 `python main.py --help`（CLI 是否可用）
3. 若 CLI 可用，GUI 崩溃可能是 Qt / 显卡驱动问题

### 表达式计算错误

- 检查是否含禁用词（`__`、`import`、`eval` 等）
- 检查括号是否匹配
- 检查是否使用了未知函数

### 汇率不更新

- 确认网络可用
- 尝试在「汇率」面板切换源
- 检查是否有代理 / 防火墙

### 首次加载 pix2tex 慢

pix2tex 模型约 97 MB，首次使用会下载。耐心等待。

### 打包体积过大

- `MultiCalc.spec.txt` 已排除 PyQt5/6、tkinter、IPython
- 如需进一步压缩，可启用 UPX

### 重置所有设置

```bash
# 备份
mv ~/.multicalc ~/.multicalc.bak

# 或直接删除
rm -rf ~/.multicalc
```

### i18n 一致性检查

```bash
python scripts/audit_i18n.py
python scripts/audit_i18n.py --strict --check-order
```

---

## 反馈与贡献

- 🐛 [提交 Bug](https://github.com/Aa5000345/Calculator/issues)
- 💡 [功能建议](https://github.com/Aa5000345/Calculator/issues)
- 📖 [贡献指南](../CONTRIBUTING.md)
- 🔒 [安全政策](../SECURITY.md)

---

**祝你使用愉快！** 🎉