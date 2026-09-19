"""应用入口：CLI / URL 参数 / 全局异常钩子 + 高 DPI + Splash + 初始化。

设计：
- CLI 解析放在最前面，走 CLI 路径时完全不加载 Qt / matplotlib
- URL 参数（?expr=1+1）通过环境变量传给 MainWindow
- Splash Screen 在导入 Qt / matplotlib 之后、MainWindow 构造之前显示

导入路径（合并后）：
    core.cli      —— try_run_cli / extract_expr_from_argv /
                     APP_VERSION
    core.runtime  —— install_error_handler
    core.state    —— Settings / I18n / History
    core.rates    —— init
    ui.main_window —— MainWindow
"""
import os

os.environ.setdefault("QT_API", "pyside6")
os.environ.setdefault("QT_ENABLE_HIGHDPI_SCALING", "1")

import sys

from core import cli as _cli
from core.cli import APP_VERSION as _APP_VERSION


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
    from PySide6.QtGui import QPixmap
    from PySide6.QtWidgets import QApplication, QSplashScreen

    from core.runtime import install_error_handler
    from core.state import I18n, History, Settings
    from ui.main_window import MainWindow

    # 3) 安装异常钩子（尽早，覆盖初始化阶段）
    install_error_handler()

    # 4) 高 DPI（Qt6 已默认开启；调整取整策略获得更平滑缩放）
    try:
        QApplication.setHighDpiScaleFactorRoundingPolicy(
            Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    except Exception:
        pass

    app = QApplication(sys.argv)
    app.setApplicationName("MultiCalc")
    app.setOrganizationName("MultiCalc")
    app.setApplicationVersion(_APP_VERSION)

    base_path = os.path.dirname(os.path.abspath(__file__))

    # 5) Splash Screen —— 让用户在慢启动时看到反馈
    splash = _show_splash(base_path, QPixmap, QSplashScreen, Qt)

    # 6) 初始化
    try:
        settings = Settings(
            os.path.join(base_path, "config",
                         "default_settings.json"))
    except Exception as e:
        print(f"设置加载失败: {e}", file=sys.stderr)
        if splash is not None:
            try:
                splash.close()
            except Exception:
                pass
        sys.exit(3)

    from core import rates as rates_mod
    try:
        rates_mod.init(
            base_path,
            plugin_dir=os.path.join(
                base_path, "plugins", "rates"))
    except Exception:
        pass

    i18n = I18n(
        os.path.join(base_path, "config", "i18n"),
        settings.get("language", "zh_CN"),
    )
    history = History()

    # 7) 主窗口
    win = MainWindow(base_path, settings, i18n, history)
    win.show()

    # 8) 关闭 splash
    if splash is not None:
        try:
            splash.finish(win)
        except Exception:
            pass

    # 9) 清理
    def _cleanup():
        try:
            history.close()
        except Exception:
            pass
        try:
            settings.flush()
        except Exception:
            pass
    app.aboutToQuit.connect(_cleanup)

    sys.exit(app.exec())


def _show_splash(base_path, QPixmap, QSplashScreen, Qt):
    """尝试显示启动画面。失败时返回 None。"""
    try:
        icon_path = os.path.join(base_path, "assets", "icon.ico")
        if not os.path.exists(icon_path):
            icon_path = os.path.join(
                base_path, "assets", "icon.png")

        if os.path.exists(icon_path):
            pm = QPixmap(icon_path).scaled(
                320, 320, Qt.KeepAspectRatio,
                Qt.SmoothTransformation)
            splash = QSplashScreen(pm)
        else:
            pm = QPixmap(320, 200)
            pm.fill(Qt.darkGray)
            splash = QSplashScreen(pm)

        splash.show()
        splash.showMessage(
            "MultiCalc 正在启动…",
            Qt.AlignBottom | Qt.AlignHCenter, Qt.white)

        try:
            from PySide6.QtWidgets import QApplication
            QApplication.processEvents()
        except Exception:
            pass

        return splash
    except Exception:
        return None


if __name__ == "__main__":
    main()