# Changelog

本项目遵循 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/) 格式，
版本号遵循 [语义化版本](https://semver.org/lang/zh-CN/)。

## [1.4.0] - 2026-09-19

### 重构（核心变更）

将 `core/` 和 `ui/` 从 **175 个文件**精简为 **89 个文件**（-49%），
所有功能模块合并为高内聚的核心模块和面板模块。

#### 新增（合并后的模块）

**core/：**
- `core/base.py` —— 异常 / 日志 / 密钥 / 版本
- `core/state.py` —— i18n / settings / history / symbols
- `core/runtime.py` —— Worker / 全局异常钩子
- `core/data.py` —— 数据表 / 数据运算
- `core/latex.py` —— LaTeX 渲染 / 解析
- `core/plot.py` —— 绘图采样 / 高级绘图
- `core/share.py` —— 分享卡片 / 工具扩展
- `core/shortcuts.py` —— 快捷键元数据 / 配置 / 方案
- `core/symbols_lib.py` —— 数字系统 / 符号库
- `core/user_data.py` —— 使用统计 / 输入历史 / 最近文件 / 快照 / 片段

**ui/：**
- `ui/shell.py` —— 信号总线 / 状态栏 / 分屏 / Toast / 托盘
- `ui/dialogs.py` —— 命令面板 / 快捷键速查 / 模块可见性 / 主题编辑器 / LaTeX 渲染
- `ui/panels/convert.py` —— 单位 / 汇率 / 数字系统
- `ui/panels/data.py` —— 统计 / 概率 / 随机 / 数据表 / 数据运算 / 贝叶斯
- `ui/panels/math.py` —— 绘图 / 3D 绘图 / 管道 / LaTeX 编辑器
- `ui/panels/productivity.py` —— 计时器 / 剪贴板 / 笔记本 / 脚本
- `ui/panels/system.py` —— 历史 / 设置 / 快捷键设置
- `ui/widgets/dialogs.py` —— 快照 / 更新 / 插件 / 导览 / 欢迎页 / 快捷键编辑器
- `ui/widgets/input.py` —— 焦点追踪 / 键按钮 / 输入历史 / 建议 / 差异徽章 / 空状态
- `ui/widgets/keyboard.py` —— 键盘布局 DSL + 浮动键盘
- `ui/widgets/tools.py` —— 手写 / OCR / 绘图动画

#### 删除

- `core/` 旧模块 58 个
- `ui/panels/` 旧模块 26 个
- `ui/widgets/` 旧模块 20 个
- 一次性迁移脚本 3 个
- 孤儿文件 3 个

#### 修复

- 修复所有残留的 `core.errors` / `core.logger` / `core.settings` 等旧导入路径
- 添加 `.gitignore`，防止 `.pyc` / `__pycache__` 等被提交

#### 兼容性

- **不向后兼容**：删除了大量旧模块，如有外部代码引用需同步更新
- **CLI 完全兼容**：`python main.py -e "..."` 行为不变
- **配置完全兼容**：`config/` 目录结构不变
- **数据完全兼容**：`~/.multicalc/` 用户数据不变

## [1.3.0] - 2025-XX-XX

（历史版本，未详细记录）

## [1.1.0] - 2025-XX-XX

（历史版本，未详细记录）

## [1.0.0] - 2025-XX-XX

首次发布。
