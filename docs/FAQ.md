# 常见问题（FAQ）

---

## 安装与运行

### Q: 支持哪些操作系统？

**A**: Windows 11 / 10、macOS 12+、Linux（桌面环境 + Qt 运行库）。
主要开发环境是 Windows 11，其它系统上基本功能可用，但极端情况可能有差异。

### Q: Python 版本要求？

**A**: **3.10** 或更高。推荐 3.11 / 3.12。

### Q: 启动很慢怎么办？

**A**:

- CLI 模式（`python main.py -e "1+1"`）不会加载 Qt / matplotlib，约 0.3 秒
- GUI 模式首次启动需要加载 PySide6 / sympy / scipy / matplotlib，约 2~4 秒（取决于磁盘）
- 启动时会显示 Splash Screen，消除"卡死"感

### Q: 打包后的 exe 很大？

**A**: 包含 sympy / scipy / matplotlib / numpy / PySide6 等大型依赖，约 200~400 MB。
`MultiCalc.spec.txt` 已排除 PyQt5/6、tkinter、IPython 等无关模块。如需进一步压缩，可启用 UPX。

### Q: 可以在无 GUI 环境下使用吗？

**A**: 可以。CLI 模式完全不需要 GUI：

```bash
python main.py -e "sin(30)" --angle DEG
```

---

## 计算相关

### Q: 支持哪些常量？

**A**: 数学常量 `pi`、`e`、`oo`（无穷大）、`I`（虚数）、`EulerGamma`、`Catalan`；
物理常量 `c`、`h`、`hbar`、`G`、`e`、`me`、`mp`、`mn`、`NA`、`kB`、`R`、`F`、`sigma`、`mu0`、`eps0`、`atm`、`g`、`au`、`ly`、`pc`。

点击科学面板的「Constants…」按钮可以查看完整列表。

### Q: 怎么定义变量 / 函数？

**A**: 在科学面板输入框直接赋值：

```
x = 5
y = x * 2
f(x) = x^2 + 1
g(x, y) = x^2 + y^2
```

变量会**持久化**到 `~/.multicalc/symbols.json`，**跨会话可用**。

### Q: 结果为什么是分数而不是小数？

**A**: 检查基础面板右上角的格式化下拉框，切换到 `Auto` 或 `Number`。

或在设置面板调整「结果格式」和「有效数字」。

### Q: 为什么 `1/3` 得到 `1/3` 而不是 `0.333`？

**A**: SymPy 会保留精确分数。如果想得到小数，用：

```
N(1/3)           # 得到 0.333333333333333
1.0/3            # 隐式转浮点
```

或在格式化下拉框选 `Number`。

### Q: 支持哪些单位的换算？

**A**: 13 个类别、约 100 个单位。参见 [使用指南 → 单位与货币](USER_GUIDE.md#单位与货币)。

### Q: 货币汇率多久更新一次？

**A**: 6 小时自动缓存。可在「汇率」面板手动刷新，或勾选「自动刷新（30 分钟）」。

离线时使用 `config/rates_offline.json`。

### Q: 汇率 API 失败怎么办？

**A**: 应用会自动按优先级尝试多个源：

1. `open.er-api.com`
2. `exchangerate.host`
3. 离线文件

也可以手动保存币对（在「手动汇率」表格）。

---

## 输入相关

### Q: 怎么输入 `π`？

**A**: 多种方式：

1. 直接输入 `pi`
2. 用浮动键盘（`Ctrl+Shift+K`），点 `π`
3. 在字典面板（侧边栏 → 字典 → 希腊字母）复制
4. 输入 `3.14159`（近似值）

### Q: 怎么输入上标 / 下标？

**A**: 

- 上标：直接输入 `^`，如 `x^2`
- Unicode 上标：字典面板 → 上下标 → `²`
- 结果会自动识别 Unicode 上标

### Q: 怎么输入大括号 / 数学符号？

**A**: 侧边栏 → **字典**。15 个分类，约 500+ 符号。

- 单击复制
- 双击 / 右键插入到当前输入框

### Q: 输入框太小怎么办？

**A**: 拖动主窗口边缘放大。或按 `F11` 进入专注模式，隐藏菜单栏 / 侧边栏。

### Q: 怎么快速召回历史？

**A**: 在输入框中按 `↑` / `↓`，循环召回历史表达式。

---

## 界面相关

### Q: 界面太亮 / 太暗怎么办？

**A**: 设置 → 主题，选择：

- `dark`（深色）
- `light`（浅色）
- `system`（跟随系统）
- 或自定义主题

### Q: 怎么隐藏某些面板？

**A**: 设置 → 模块显示，或点击侧边栏顶部的「Visibility」按钮。勾选要显示的模块。

### Q: 怎么调整面板顺序？

**A**: 在侧边栏拖拽模块到目标位置。也可以设置 → 模块显示，拖拽调整。

### Q: 侧边栏不见了？

**A**: 按 `Ctrl+Shift+L` 切换显示 / 隐藏。或菜单 → 视图 → 模块。

### Q: F11 专注模式怎么退出？

**A**: 再按一次 `F11`，或点击右上角的浮动「✕ 退出专注」按钮。

### Q: 状态栏显示了什么？

**A**: 从左到右：

- `[基础]` — 当前面板
- `RAD` / `DEG` — 角度模式
- `内存: 12.5` — 基础面板的内存值
- `汇率: 2 小时前` — 汇率缓存新鲜度
- `⏳ 计算中` — 后台任务

---

## 快捷键相关

### Q: 怎么查看所有快捷键？

**A**: 按 `F1`，或菜单 → 帮助 → 快捷键速查表。

### Q: 可以自定义快捷键吗？

**A**: 可以。`F1` → 「自定义」Tab，点击「录制」后按下想要的组合键。

冲突的键位会标红。保存后立即生效。

### Q: 为什么 Ctrl+K 没用？

**A**: 检查是否有其它应用占用了 `Ctrl+K`。可以在 `F1` → 自定义里改成别的键。

---

## 数据与同步

### Q: 数据存储在哪里？

**A**: `~/.multicalc/`（Windows 上是 `%USERPROFILE%\.multicalc\`）。

包含设置、历史、变量、密钥等。参见 [使用指南 → 性能与存储](USER_GUIDE.md#性能与存储)。

### Q: 怎么备份 / 迁移？

**A**: 直接复制整个 `~/.multicalc/` 目录即可。

### Q: 怎么重置所有数据？

**A**: 删除 `~/.multicalc/`：

```bash
# Windows (PowerShell)
Remove-Item -Recurse ~/.multicalc

# macOS / Linux
rm -rf ~/.multicalc
```

### Q: 历史记录太多会卡吗？

**A**: 历史用 SQLite，最多 5000 条（自动裁剪）。分页显示（每页 100 条），通常不会卡。

如遇卡顿，可以在历史面板「清空本模块」或「清空全部」。

---

## 加密相关

### Q: 文件加密安全吗？

**A**: 采用 **AES-256-GCM** 或 **ChaCha20-Poly1305**（认证加密），
密钥派生用 **PBKDF2-HMAC-SHA256**（默认 60 万迭代）/ **Scrypt** / **Argon2id**。

**每个文件独立 salt + nonce**，即使同一密码加密同一文件两次，密文也不同。

**篡改可检测**：任何字节修改都会被 GCM tag 拒绝。

### Q: 加密大文件会占多少内存？

**A**: 流式处理，内存占用**恒定**（约等于块大小，默认 1 MiB）。加密 8 GB 文件也只占 1 MiB 左右。

### Q: 密码丢了怎么办？

**A**: **无法恢复**。这是加密的本质——没有后门。请务必备份密码。

### Q: PQC（后量子密码）支持哪些算法？

**A**:

- **ML-KEM**（FIPS 203）：密钥封装 — 512/768/1024
- **ML-DSA**（FIPS 204）：数字签名 — 44/65/87
- **SLH-DSA**（FIPS 205）：哈希签名 — SHA2/SHAKE × 128/192/256

> 需要 `cryptography>=48` 且 OpenSSL 3.5+ / AWS-LC / BoringSSL 后端。
> 在「高级加密」Tab 的「后端能力」页可以查看当前环境支持情况。

### Q: `.mcenc` 文件可以用其它工具解密吗？

**A**: 目前不行。这是自有格式。如果需要跨工具，可以用 `openssl` 手动解密：

```bash
# 从文件头提取 salt / nonce_prefix / chunk_size
# 用 PBKDF2 派生密钥
# 用 AES-256-GCM 逐块解密
```

（不推荐，容易出错。）

---

## AI 相关

### Q: AI 助手需要联网吗？

**A**: 不一定：

- **本地规则**：永远可用，无需联网
- **Ollama**：本地 LLM，探测 `localhost:11434`，无需联网
- **OpenAI / Anthropic**：需 API key + 联网

### Q: API key 存哪里？安全吗？

**A**: 存到 `~/.multicalc/secrets.json`，与 `settings.json` **分离**。

- 导入 / 导出设置时**不会**泄露密钥
- Unix 上文件权限设为 `0600`（Windows 上尽力而为）

### Q: 多轮对话怎么用？

**A**: 在「对话」Tab，输入自然语言：

```
你: 100 的 15%
AI: 100 * 15 / 100 = 15

你: 刚才的结果乘 2
AI: (100 * 15 / 100) * 2 = 30
```

代词「它」「那个」「刚才」「上一步」会自动解析为上一个表达式。

### Q: 智能建议怎么关掉？

**A**: 设置 → 搜索「suggestions」→ 关闭。

或在 `config/default_settings.json` 里把 `suggestions_enabled` 设为 `false`。

---

## 手写 / OCR

### Q: 手写识别需要什么依赖？

**A**: 需要 `pix2tex`：

```bash
pip install pix2tex
```

首次使用会下载约 97 MB 的模型。加载需要 30~60 秒。

### Q: 可以用 OpenAI 视觉替代吗？

**A**: 可以。在 AI 面板配置 OpenAI API key，OCR 对话框选「OpenAI 视觉」。

### Q: 手写识别准确率不高怎么办？

**A**: 

- 写清楚，避免连笔
- 别太大 / 太小（画板中间 1/3 最佳）
- 用识别后手动编辑
- 尝试 OpenAI 视觉（通常更准）

### Q: 画板能导出吗？

**A**: 可以。点击「导出 PNG」。

---

## 性能相关

### Q: 为什么有些计算很慢？

**A**: SymPy 的符号计算可能较慢（尤其是复杂积分、大矩阵）。

- 后台线程执行，UI 不冻结
- 可以点击「取消」
- 数值计算（SciPy）通常更快

### Q: 实时预览为什么有时不显示？

**A**: 预览有保护机制：

- 表达式 > 40 字符
- 含昂贵关键字（`integrate`、`solve` 等）

这些情况下跳过预览，避免卡顿。

### Q: 浮动键盘会影响输入吗？

**A**: 不会。浮动键盘用 `Qt.Tool` 窗口 + `WA_ShowWithoutActivating`，不会抢焦点。

---

## 打包 / 发布

### Q: 怎么打包成 exe？

**A**: 用 PyInstaller：

```bash
pip install pyinstaller
pyinstaller MultiCalc.spec.txt
# 产物：dist/MultiCalc.exe
```

### Q: 打包后找不到 config 目录？

**A**: PyInstaller 会把 `config/` 解压到 `sys._MEIPASS`。
`MultiCalc.spec.txt` 已配置 datas。运行时用 `base_path` 定位。

### Q: 怎么减小打包体积？

**A**:

1. `MultiCalc.spec.txt` 已排除 PyQt5/6、tkinter、IPython
2. 启用 UPX（`upx=True`）
3. 排除未使用的 matplotlib 后端
4. 排除 pix2tex（可选，用户手动安装）

---

## 开发 / 贡献

### Q: 怎么参与开发？

**A**: 参见 [CONTRIBUTING.md](../CONTRIBUTING.md)。

### Q: 代码分层原则是什么？

**A**:

- `core/` 不依赖 Qt — CLI 可复用、可单独测试
- `ui/` 不直接操作 SQLite — 走 core 接口
- 面板之间通过 `ui/signals.py` 总线通信

### Q: 怎么添加新面板？

**A**:

1. 在 `ui/panels/` 新建 `my_panel.py`，继承 `CalcPanel`
2. 在 `ui/panels/registry.py` 的 `all_panels()` 里加一行 `PanelSpec`
3. 在 `config/default_settings.json` 的 `visible_modules` 加 key
4. 更新 i18n 语言包

参见 [CONTRIBUTING.md → 项目结构](../CONTRIBUTING.md#项目结构)。

### Q: 怎么添加新主题？

**A**: 在 `config/themes/` 添加 `<name>.json`：

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

或使用应用内「主题编辑器」可视化编辑后保存。

### Q: 怎么添加新语言？

**A**:

1. 复制 `config/i18n/en_US.json` 为 `<lang>.json`
2. 逐条翻译
3. 在 `ui/panels/settings.py` 的语言下拉框里加一项
4. 运行 `python scripts/audit_i18n.py` 确认

### Q: 怎么运行测试？

```bash
python -m pytest
python -m pytest tests/test_smoke.py -v
```

### Q: 怎么检查 i18n 一致性？

```bash
python scripts/audit_i18n.py
python scripts/audit_i18n.py --strict --check-order
```

---

## 反馈

### Q: 怎么报告 Bug？

**A**: [新建 Issue](https://github.com/Aa5000345/Calculator/issues/new?template=bug_report.yml)，
请附上：

- MultiCalc 版本
- 操作系统
- 复现步骤
- 日志（`~/.multicalc/logs/app.log`）

### Q: 怎么提出功能建议？

**A**: [新建 Issue](https://github.com/Aa5000345/Calculator/issues/new?template=feature_request.yml)。

### Q: 发现安全漏洞怎么办？

**A**: **不要通过公开 Issue 报告**。请用 [GitHub 私有漏洞报告](https://github.com/Aa5000345/Calculator/security/advisories/new)。
参见 [SECURITY.md](../SECURITY.md)。

---

**没找到你的问题？** 去 [Discussions](https://github.com/Aa5000345/Calculator/discussions) 提问。