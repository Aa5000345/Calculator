"""pytest 全局配置：把项目根目录加入 sys.path。

这样无论从哪个目录运行 pytest，`import core` / `import ui` 都能成功。
"""
from __future__ import annotations

import os
import sys

# 项目根 = tests/ 的上一级
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

# 让 matplotlib 全程使用无界面后端，避免 CI / 无显示环境下崩溃
os.environ.setdefault("QT_API", "pyside6")
os.environ.setdefault("MPLBACKEND", "Agg")