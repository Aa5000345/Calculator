"""应用入口：CLI / URL 参数 / 全局异常钩子 + 高 DPI + 初始化 + 主窗口。

设计：
- CLI 解析放在最前面，走 CLI 路径时完全不加载 Qt / matplotlib
- URL 参数（?expr=1+1）通过环境变量传给 MainWindow
"""
import os

os.environ.setdefault("QT_API", "pyside6")
os.environ.setdefault("QT_ENABLE_HIGHDPI_SCALING", "1")

import sys

# CLI 模块只依赖标准库；提前导入不拖慢 GUI 启动
from core import cli as _cli


def main():
    # 0) CLI 优先处理（无需 GUI）
    handled, code = _cli.try_run_cli(sys.argv[1:])
    if handled:
        sys.exit(code)

    # 1) URL 参数：?expr=1+1 / multicalc://expr=1+1
    init_expr = _cli.extract_expr_from_argv(sys.argv[1:])
    if init_expr:
        os.environ["MULTICALC_INIT_EXPR"] = init_expr

    # 2) 之后才导入 matplotlib / Qt —— 保证 CLI 路径不受影响
    import matplotlib
    matplotlib.use("QtAgg")

    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QApplication

    from core import error_handler
    from core.settings import Settings
    from core.i18n import I18n
    from core.history import History
    from ui.main_window import MainWindow

    # 3) 安装异常钩子（尽早，覆盖初始化阶段）
    error_handler.install()

    # 4) 高 DPI（Qt6 已默认开启；这里只调整取整策略以获得更平滑缩放）
    try:
        QApplication.setHighDpiScaleFactorRoundingPolicy(
            Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    except Exception:
        pass

    app = QApplication(sys.argv)
    app.setApplicationName("MultiCalc")
    app.setOrganizationName("MultiCalc")

    base_path = os.path.dirname(os.path.abspath(__file__))

    settings = Settings(
        os.path.join(base_path, "config", "default_settings.json"))

    from core import rates as rates_mod
    rates_mod.init(base_path,
                   plugin_dir=os.path.join(base_path, "plugins", "rates"))

    i18n = I18n(
        os.path.join(base_path, "config", "i18n"),
        settings.get("language", "zh_CN"),
    )
    history = History()

    win = MainWindow(base_path, settings, i18n, history)
    win.show()

    # 关闭时优雅退出
    def _cleanup():
        try:
            history.close()
        except Exception:
            pass
    app.aboutToQuit.connect(_cleanup)

    sys.exit(app.exec())


if __name__ == "__main__":
    main()