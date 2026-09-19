# Changelog

本项目遵循 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/) 格式，
版本号遵循 [语义化版本](https://semver.org/lang/zh-CN/)。

> **注意**：v1.4.0 进行了大规模模块合并重构。v1.3.0 及更早版本提到的旧模块
> 路径（如 `core/pipeline.py`、`ui/panels/notebook_panel.py`）**已不存在**，
> 均合并到 v1.4.0 的新模块中。详见 [1.4.0] 章节。

---

## [1.4.0] - 2026-09-19

### 重构（核心变更）

将 `core/` 和 `ui/` 从 **175 个文件**精简为 **89 个文件**（-49%），
所有功能模块合并为高内聚的核心模块和面板模块。

#### 新增（合并后的模块）

**core/（10 个新模块）**
- `core/base.py` —— 异常 / 日志 / 密钥 / 版本（合并 errors / logger / secrets / version）
- `core/state.py` —— i18n / settings / history / symbols（合并 4 个模块）
- `core/runtime.py` —— Worker / 全局异常钩子（合并 worker / error_handler）
- `core/data.py` —— 数据表 / 数据运算（合并 data_table / data_ops）
- `core/latex.py` —— LaTeX 渲染 / 解析（合并 latex_ext / latex_parser）
- `core/plot.py` —— 绘图采样 / 高级绘图（合并 plot_sample / plot_advanced）
- `core/share.py` —— 分享卡片 / 工具扩展（合并 share_card / tools_ext）
- `core/shortcuts.py` —— 快捷键元数据 / 配置 / 方案（合并 3 个模块）
- `core/symbols_lib.py` —— 数字系统 / 符号库（合并 number_systems / glyph_library）
- `core/user_data.py` —— 使用统计 / 输入历史 / 最近文件 / 快照 / 片段（合并 5 个模块）

**ui/（11 个新模块）**
- `ui/shell.py` —— 信号总线 / 状态栏 / 分屏 / Toast / 托盘（合并 5 个模块）
- `ui/dialogs.py` —— 命令面板 / 快捷键速查 / 模块可见性 / 主题编辑器 / LaTeX 渲染
- `ui/panels/convert.py` —— 单位 / 汇率 / 数字系统（合并 3 个）
- `ui/panels/data.py` —— 统计 / 概率 / 随机 / 数据表 / 数据运算 / 贝叶斯（合并 5 个）
- `ui/panels/math.py` —— 绘图 / 3D 绘图 / 管道 / LaTeX 编辑器（合并 4 个）
- `ui/panels/productivity.py` —— 计时器 / 剪贴板 / 笔记本 / 脚本（合并 4 个）
- `ui/panels/system.py` —— 历史 / 设置 / 快捷键设置（合并 3 个）
- `ui/widgets/dialogs.py` —— 快照 / 更新 / 插件 / 导览 / 欢迎页 / 快捷键编辑器（合并 6 个）
- `ui/widgets/input.py` —— 焦点追踪 / 键按钮 / 输入历史 / 建议 / 差异徽章 / 空状态（合并 6 个）
- `ui/widgets/keyboard.py` —— 键盘布局 DSL + 浮动键盘（合并 2 个）
- `ui/widgets/tools.py` —— 手写 / OCR / 绘图动画（合并 3 个）

#### 删除

- `core/` 旧模块 58 个
- `ui/panels/` 旧模块 26 个
- `ui/widgets/` 旧模块 20 个
- 一次性迁移脚本 3 个（`cleanup_old_files.py` / `migrate_imports.py` / `fix_broken_lines.py`）
- 孤儿文件 3 个（`ui/panels/options.py` / `ui/panels/tax.py` / `ui/panels/snapshot_dialog.py`）

#### 修复

- 修复所有残留的 `core.errors` / `core.logger` / `core.settings` 等旧导入路径
- 添加 `.gitignore`，防止 `.pyc` / `__pycache__` / `.venv/` 等被提交

#### 兼容性

- **不向后兼容**：删除了大量旧模块，如有外部代码引用需同步更新
- **CLI 完全兼容**：`python main.py -e "..."` 行为不变
- **配置完全兼容**：`config/` 目录结构不变
- **数据完全兼容**：`~/.multicalc/` 用户数据不变

---

## [1.3.0] - 2026-09-19

### Added

#### 计算能力

- **管道工作流**：`1 km | to m | * 2 | round(3)` 多步串接（旧 `core/pipeline.py` + `ui/panels/pipeline_panel.py`，现合并至 `core/notebook.py` + `ui/panels/math.py`）
- **数学笔记本**：Code / Markdown cell 混排，Shift+Enter 执行并前进（`core/notebook.py` + 现 `ui/panels/productivity.py`）
- **LaTeX → 表达式**：纯正则实现，覆盖分数 / 根号 / 上下标 / 希腊字母 / 求和积分（现 `core/latex.py`）
- **数字系统转换**：阿拉伯 ↔ 罗马 / 中文小写 / 中文大写 / 英文 / 摩尔斯（现 `core/symbols_lib.py` + `ui/panels/convert.py`）
- **符号字典**：15 个分类、500+ Unicode 符号，支持中文 / 英文 / LaTeX 搜索（现 `core/symbols_lib.py` + `ui/panels/tools.py`）
- **数据运算**：18 种聚合 / 排序 / 11 种筛选 / 分析（现 `core/data.py` + `ui/panels/data.py`）
- **贝叶斯推断**：Beta-Binomial / Normal-Normal / Gamma-Poisson 共轭更新（现 `core/probability.py`）
- **MCMC**：Metropolis-Hastings / Gibbs，ESS / 自相关 / Gelman-Rubin R-hat（现 `core/probability.py`）
- **蒙特卡洛**：π 估算 / 1D / ND 积分 / 对偶变量方差缩减（现 `core/probability.py`）

#### 加密能力

- **PQC（后量子密码）**：ML-KEM（FIPS 203）/ ML-DSA（FIPS 204）/ SLH-DSA（FIPS 205）（现 `core/crypto_tools.py`）
- **对称加密**：ChaCha20-Poly1305（RFC 8439）
- **非对称加密**：Ed25519 / X25519
- **密码哈希**：Argon2id（RFC 9106）/ bcrypt
- **密钥派生**：Argon2id / Scrypt / PBKDF2
- **编码扩展**：Base58 / Base32 / Base85 / Ascii85
- **文件加密 v2**：AES-256-GCM 与 ChaCha20-Poly1305 双算法，流式处理，向后兼容 v1（现 `core/crypto_tools.py` + `ui/panels/tools.py`）
- **高级加密 Tab**：后端能力探测 + 9 个子 Tab（现 `ui/panels/tools.py`）

#### AI 能力

- **AI 多轮对话**：保存上下文、代词解析（"刚才" / "上一步"）（现 `core/ai.py` + `ui/panels/ai.py`）
- **智能建议引擎**：基于规则的轻量推荐，7 类规则（现 `core/ai.py`）

#### 工作流

- **会话快照 / 时间机器**：保存 / 恢复 / diff（现 `core/user_data.py` + `ui/widgets/dialogs.py`）
- **输入框版本历史**：按 key 隔离，每个 key 最多 50 个版本（现 `core/user_data.py` + `ui/widgets/input.py`）
- **最近打开文件**：菜单「文件 → 最近打开」（现 `core/user_data.py`）

#### 界面

- **QStatusBar**：当前面板 / 角度模式 / 内存值 / 汇率新鲜度 / 后台任务（现 `ui/shell.py`）
- 面板底部快捷键提示条
- **启动 Splash Screen**（`main.py`）
- **首次运行欢迎页**：6 个快捷入口卡片 + 最近打开（现 `ui/widgets/dialogs.py`）
- **快速导览**：5 步功能演示（现 `ui/widgets/dialogs.py`）
- **空状态组件**（现 `ui/widgets/input.py`）
- **结果差异徽章**：数值差异 + 百分比 + 单位感知（`core/result_diff.py` + 现 `ui/widgets/input.py`）

#### 插件与配置

- **插件系统**：6 种扩展点（面板 / 命令 / 菜单 / 主题 / 汇率源 / 状态栏组件）（`core/plugins.py`）
- **插件管理器 UI**（现 `ui/widgets/dialogs.py`）
- **示例插件**（`plugins/example_command/`）
- **快捷键自定义**：50+ 命令 / 7 分组 / 3 级作用域 / 4 预设方案（现 `core/shortcuts.py` + `ui/widgets/dialogs.py`）
- **i18n 扩展**：新增繁体中文（`zh_TW.json`）、日本語（`ja_JP.json`）
- **语言包骨架生成器**（`scripts/gen_lang_skeleton.py`）
- **i18n 深度审计**（`scripts/audit_i18n.py`）

#### CLI

- `--pipe`：从 stdin 逐行读取
- `--nb <file>`：执行 Jupyter Notebook
- `-o json / csv / text`：输出格式
- `--quiet`：安静模式
- 每条结果带 `elapsed_ms` 计时字段

#### 更新

- **检查更新**：GitHub Releases API + 流式下载 + SHA256 校验 + 平台匹配（`core/updater.py` + 现 `ui/widgets/dialogs.py`）
- **语义化版本比较**：支持 `1.0.0-alpha < 1.0.0-beta < 1.0.0-rc.1 < 1.0.0`（现 `core/base.py`）

#### 面板（共 6 个新增，总计 31 个）

- `pipeline`（数学组）：管道工作流
- `notebook`（生产力组）：数学笔记本
- `glyph`（工具组）：符号字典
- `number_systems`（转换组）：数字系统转换
- `data_ops`（数据组）：数据运算
- `shortcuts`（系统组）：快捷键设置

### Changed

- **错误分级**：`message` 用户级 + `detail` 技术级，新增 `default_user_message` / `user_message_str()`（现 `core/base.py`）
- **自动重试注入**：`run()` 未显式传 `on_fail` 时走 `_default_on_fail`，自动注入 `retry_cb`（现 `ui/panels/base.py`）
- **CalcPanel.primary_input**：统一主输入框访问入口（现 `ui/panels/base.py`）
- **撤销栈**：`push_undo()` / `undo()`，子类无需自行实现（现 `ui/panels/base.py`）
- **面板懒加载**：工厂函数改为延迟导入，仅在首次访问时 import（现 `ui/panels/registry.py`）
- **主题编辑器**：`_apply()` 以 `settings.palette(theme)` 为基底，避免覆盖主题文件（现 `ui/dialogs.py`）
- **命令面板拼音搜索**：支持拼音首字母 + 全拼（`core/pinyin_map.py` + 现 `ui/dialogs.py`）
- **打包优化**：精细排除 + onefile / onedir 双模式 + UPX 可开关（`MultiCalc.spec`）
- **设置面板**：新增设置项搜索框，语言下拉支持 ja_JP / zh_TW（现 `ui/panels/system.py`）
- **快捷键系统**：从硬编码改为 `shortcut_meta` 元数据驱动（现 `core/shortcuts.py` + `ui/shortcuts.py`）
- **日期面板**：`add` key 改为 `date_add`，避免与通用按钮冲突（现 `ui/panels/finance.py`）
- **BondPanel**：新增独立 Market Price 输入框（现 `ui/panels/finance.py`）

### Removed

- `ui/main_window.py`：移除 4 行 `_focus_shortcut` 相关代码（F11 已由 `install_main_window_shortcuts` 统一接管）
- `ui/shortcuts.py`：移除硬编码的 Ctrl+K / Ctrl+Shift+K / F11 / F1（由 shortcut_meta 元数据驱动）
- `config/i18n/zh_CN.json` / `en_US.json`：移除 5 处冗余重复 key

### Fixed

- `StatsPanel` 调用的 `engine.stats_*` 不存在 → 改为直连 `core.probability`
- `bond_ytm` 误用面值当市场价 → 新增独立 Market Price 输入框
- `PlotPanel` 调用 `engine._parse_lambda2` 私有函数 → 改用 `plot_sample.parse_lambda2`（现 `core.plot`）
- 手写 / OCR 的 `QThread.quit()` 无效 → 改为 `cancel()` + `_cancelled` 标志 + `wait()`
- `ResultView` 右键菜单重复添加 "Copy as JSON" → 删除重复行
- `InlinePreviewBar` 关键词匹配过于激进 → 改用 `\b` 词边界正则
- 主题编辑器 `_apply()` 会覆盖主题文件 → 以实际生效 palette 为基底
- 修复 `core/symbols` 原文件 docstring 乱码
- 随机数面板 `_build_*` 方法中误用裸 `i18n` → 改为 `self.i18n`
- 历史面板删除一行非法的 `from ... import ... if False else None`
- `main.py` 删除未定义的 `sc_focus` 引用
- i18n 修复 `ai_provider` 未翻译、`button_layout` 缺空格、日期面板 `add` → `date_add`
- `core/shortcut_config`：`set()` / `reset()` 中的 `global _CACHE` 提到函数体首行，避免 SyntaxError

### Security

- API 密钥隔离：`~/.multicalc/secrets.json` 与 `settings.json` 分离，导入 / 导出设置不泄露
- 表达式沙箱：`core/engine.py` 拒绝 `__` / `import` / `eval` / `open` 等危险内容
- 公式沙箱：数据表使用 AST 白名单 + `__builtins__` 清空
- 文件加密：AES-256-GCM / ChaCha20-Poly1305 认证加密，每文件独立 salt + nonce
- 更新下载：SHA256 校验（如 release 提供 checksum），半成品保护（`.part` 临时文件）

---

## [1.2.0] - 2026-09-18

### Added

#### 输入方式

- **手写公式画板**：鼠标 / 触控笔画板，支持笔画撤销、清空、导出 PNG（现 `ui/widgets/tools.py`）
- **截图 / 图片识别**：支持打开文件 / Ctrl+V 粘贴 / 拖放，识别后端可选（现 `ui/widgets/tools.py`）
- **`core.visual_input` 分发层**：pix2tex（LaTeX OCR）/ OpenAI 视觉 / 手动输入三级 fallback；探测阶段用 `importlib.util.find_spec` 避免启动时 import torch（现 `core/ai.py`）
- **剪贴板智能识别**：轮询系统剪贴板（700 ms），识别到像表达式的内容时弹 Toast；点击 Toast 直接送往基础面板；自动排除 URL / 邮箱 / 路径 / 长数字串 / 单数字（`core/clipboard_monitor.py`）
- **AI 批量翻译**：AI 面板新增批量 Tab，多行 NL → 一次翻译 → 结果表 → 一键发送到脚本面板 / 复制全部表达式
- **CLI 模式**：`core/cli.py`，支持 `-e/--expr`、`--cli`、`--json`、`--angle`、`--no-format`、`--help`、`--version`，裸表达式亦可
- **URL 参数**：`python main.py "?expr=2%2B3"` 或 `multicalc://expr=...`，启动 GUI 并自动填入表达式

#### 分享与协作

- **分享卡片**：纯 Pillow 渲染，结果区右键 → 分享卡片 → 生成 860×420 PNG（含表达式 / 结果 / LaTeX / 二维码）；未装 qrcode 时自动跳过二维码区域（现 `core/share.py`）
- **可重放会话**：历史面板支持导出 / 导入 `.mcsession`；导入后自动写入历史并送脚本面板
- **Jupyter Notebook 导出**：生成标准 nbformat v4 `.ipynb`（每条目一个 Markdown 头 + 一个代码 cell）（现 `core/notebook.py`）
- **Markdown 复制**：结果区右键 → 复制为 Markdown（\`\`\` 代码块 + `$$...$$` 公式）

#### 交互与体验

- **Toast 非模态通知**：底部中央堆叠、淡入淡出、可点击；全部成功提示（复制 / 导入 / 保存 / 应用设置）改为 Toast（现 `ui/shell.py`）
- **快捷键速查表**：F1 打开，五组分类展示（现 `ui/dialogs.py`）
- **专注模式**：F11 隐藏菜单栏 / 侧边栏，仅留当前面板；右上角悬浮"退出"按钮兜底
- **命令面板增强**：
  - `= 2+2` 结果内联显示（不再弹窗）
  - `> 分类导航`（`▸ theme:  (N)`），`> theme` 展开主题命令
  - Tab 在搜索框 / 列表间切换
  - 打开时自动定位第一项
- **命令面板使用频率学习**：命令按使用次数 + 14 天半衰的时效性加权排序，落盘 `~/.multicalc/usage.json`（现 `core/user_data.py`）
- **内联预览推广**：InlinePreviewBar 接入 finance（贷款月供）、probability（PDF/PMF）、matrix（A^n）
- **数据表公式自动重算**：`itemChanged` + 350 ms 防抖，隐藏的 `_suppress` 标志避免递归
- **侧边栏搜索分组计数**：搜索时分组头显示 `基础 (2)`，清空恢复；同时联动 `visible_modules` 过滤
- **浮动键盘智能插入增强**：`(` 自动补 `)`，光标停在括号中间
- **绘图**：新增 LaTeX 坐标轴标签复选框
- **MainWindow.show_toast()** 公共入口
- **ResultView 内联校验辅助**：`mark_field_error` / `clear_field_error`

#### 架构与可维护性

- `core/plot_sample.py`：从 `core.engine` 拆出绘图采样（现 `core/plot.py`），engine 保留同名转发层
- `ui/panels/registry.PanelSpec.keywords`：面板元数据新增关键词字段，供命令面板分类 / 侧边栏搜索 / 使用统计复用
- `ui/panels/__init__.py` 补齐全部 25 个面板导出（含 AIPanel / ScriptPanel / ClipboardHistoryPanel）
- **新增测试基础设施**：`tests/conftest.py`、`tests/test_smoke.py`、`tests/test_imports.py`

### Changed

- `main.py` 完全重写：CLI 路径不加载 Qt / matplotlib，启动 < 200 ms；URL 参数通过 `MULTICALC_INIT_EXPR` 环境变量传给 MainWindow
- LaTeX 渲染改用 `functools.lru_cache(maxsize=512)`：容量固定、线程安全、无手动加锁；新增 `clear_cache()` 供主题切换调用（现 `ui/dialogs.py`）
- F11 改用独立 QShortcut 注册（不再挂菜单 action，避免菜单隐藏后快捷键失效）
- AI 翻译 / RSA 密钥生成搬进 Worker：长任务不再冻结 UI
- 设置面板成功提示从 QMessageBox 改为 Toast
- `history.py` 的 `from __future__ import annotations` 位置修正到文件第一行
- `ResultView._flash` 高亮动画不再污染 styleSheet（改为叠加层淡出）
- `HistoryPanel.refresh()` 保留选中项
- `Plot3DPanel.closeEvent` / `hideEvent` 停止定时器与动画，避免泄漏
- 识别过程搬进 QThread：pix2tex 首次加载模型（30–60 s）不再冻结 UI，状态栏给出明确阶段提示
- `_insert_into_target` 统一处理手写 / OCR 结果：优先插入到打开对话框前获得焦点的输入框；失效则复制到剪贴板并 Toast 提示
- `_collect_for_export` 支持"选中优先 / 否则当前页"
- `requirements.txt` 标注可选依赖（pix2tex / vosk / Ollama）
- `README.md` 大幅扩充

### Fixed

- **P0 - `ui/widgets/__init__.py` ImportError**：`COMPACT_LAYOUT` / `SCI_LAYOUT` 不再从 `keyboard_layouts` 导入，改为在 `__init__.py` 定义别名
- **P0 - 进制转换小数不联动**：`_on_live` 改用显式 `sender_widget` 参数（不再依赖脆弱的 `sender()`），并改用 `base_convert_float` 支持小数
- **P0 - AI 翻译冻结 UI（20 s）**：`ai_mod.translate()` 搬进 Worker
- **P0 - RSA 密钥生成冻结 UI**：`ct.rsa_generate()` 搬进 Worker
- **P0 - 无冒烟测试**：新增 `tests/test_smoke.py` + `tests/conftest.py`
- **P0 - QShortcut 从 PySide6.QtWidgets 导入导致启动崩溃**：改从 PySide6.QtGui 导入
- `history.py` 的 `from __future__ import annotations` 位置错误（导致全部面板导入失败）
- `core/constants.all_constants` 4 元组解包错误（现 `core/engine.py`）
- 日期面板补 QWidget 导入
- 科学计算面板变量名 `shead` 未定义 → 改为 `head`
- `ui/widgets/key_button.py` 用 `QSizePolicy.Expanding` 类属性（原用实例属性导致构造失败）
- `core/engine._norm` 支持 Unicode 上标（² / ³ / ⁻¹）与前导零（09）
- `core/engine.basic_calc` 用 `complex(val)` + `math.isnan/isinf` 替代 `val.is_nan`（SymPy Float 无此属性）
- `run_async` 取消按钮不再重复 disconnect（消除 C++ 层警告）
- `core/crypto_tools.b64_decode` 对非 ASCII 输入给出友好的 InputError 提示

### Removed

- LaTeX widget 的全局缓存字典（改用 `lru_cache`）（现 `ui/dialogs.py`）
- `core.engine` 中重复的绘图采样实现（保留兼容转发）

---

## [1.1.1-alpha] - 2026-09-15

**alpha 版，有 bug，不建议使用。**

---

## [1.0.0] - 2026-09-12

### Added

- 首个版本，共 25 个面板
- 基础计算 / 科学计算 / 单位换算 / 汇率 / 进制 / 矩阵
- 统计 / 概率 / 随机数 / 数据表
- 绘图 / 3D 绘图 / 财务 / 日期
- 位运算 / 加密工具 / LaTeX 编辑器 / 工具 / 片段 / 计时器 / 剪贴板
- 历史记录 / 设置 / 快捷键
- 浮动键盘 / 命令面板 / 主题系统 / i18n（zh_CN + en_US）
