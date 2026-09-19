"""MultiCalc 核心包。

子模块（合并后的新布局）：

    core.base        基础：异常 / 日志 / 密钥 / 版本
    core.state       全局状态：i18n / settings / history / symbols
    core.runtime     Qt 运行期辅助：Worker / 全局异常钩子
    core.cli         命令行入口（保留）
    core.pinyin_map  拼音首字母映射（保留）
    core.engine      计算内核
    core.ai          AI / 对话 / 建议 / 视觉输入
    core.rates       汇率 + 加密货币
    core.finance     财务 / 债券 / 期权 / 个税
    core.dates       日期 / 农历 / 日出日落
    core.bits        位运算 / CRC / 哈希 / 位图
    core.crypto      编码 / AES / RSA / PQC / 文件加密
    core.data        数据表 / 数据运算
    core.plot        绘图采样 / 高级绘图
    core.probability 概率 / 随机 / 贝叶斯 / MCMC / 蒙特卡洛
    core.latex       LaTeX 渲染 / 解析
    core.notebook    笔记本 / 管道 / 导出
    core.symbols_lib 数字系统 / 符号库
    core.plugins     插件 API / 注册表 / 加载器
    core.user_data   使用统计 / 输入历史 / 最近文件 / 快照 / 片段
    core.shortcuts   快捷键元数据 / 配置 / 方案
    core.updater     自动更新
    core.share       分享卡片 / 工具扩展

设计原则：
    - core/ 不依赖 Qt（`core.runtime` 除外，它需要 QThread）
    - 顶层 __init__ 不做任何子模块导入，保证 CLI 路径不加载 Qt / numpy
"""
from __future__ import annotations

__version__ = "1.4.0"
__app_name__ = "MultiCalc"

__all__ = ["__version__", "__app_name__"]