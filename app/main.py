"""Application entry point for ExamSplit AI."""

import sys
import os
import argparse
import logging
from pathlib import Path
from PySide6.QtWidgets import QApplication
from .config import BUNDLE_DIR, DEFAULT_DB_PATH, ensure_data_directories
from .storage.database import init_db
from .ui.main_window import MainWindow

logger = logging.getLogger("examsplit")


def setup_logging(debug: bool = False) -> None:
    """Configure console and file logging."""
    from .config import DATA_DIR, ensure_data_directories
    ensure_data_directories()
    level = logging.DEBUG if debug else logging.INFO
    handlers: list[logging.Handler] = []
    if sys.stdout is not None:
        handlers.append(logging.StreamHandler(sys.stdout))
    try:
        handlers.append(logging.FileHandler(str(DATA_DIR / "app.log"), encoding="utf-8", mode="a"))
    except Exception:
        pass

    if not handlers:
        handlers.append(logging.NullHandler())

    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=handlers,
    )


def main() -> int:
    """Main CLI and GUI runner."""
    parser = argparse.ArgumentParser(description="ExamSplit AI - 试卷 PDF 智能拆题与选题导出系统")
    parser.add_argument("pdf_file", nargs="?", default=None, help="可选：启动时直接打开的试卷 PDF 文件路径")
    parser.add_argument("--dry-run", action="store_true", help="初始化环境与数据库后安全退出，不启动图形界面")
    parser.add_argument("--debug", action="store_true", help="开启调试级别详细日志")
    parser.add_argument("--db-path", type=str, default=str(DEFAULT_DB_PATH), help="指定 SQLite 数据库路径")
    parser.add_argument("--version", action="version", version="ExamSplit AI v0.2.0")

    args = parser.parse_args()
    setup_logging(args.debug)

    logger.info("Initializing ExamSplit AI environment...")
    ensure_data_directories()

    logger.info(f"Initializing SQLite database at: {args.db_path}")
    init_db(args.db_path)

    if args.dry_run:
        logger.info("Dry run completed successfully. Exiting without launching GUI.")
        return 0

    logger.info("Launching PySide6 Application...")
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QIcon
    # Configure Qt platform plugin paths for PyInstaller standalone bundles
    if getattr(sys, "frozen", False):
        from PySide6.QtCore import QCoreApplication
        base_dir = Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
        for p_dir in [
            base_dir / "PySide6" / "plugins",
            base_dir / "plugins",
            base_dir,
        ]:
            if p_dir.exists():
                QCoreApplication.addLibraryPath(str(p_dir))

        for plat_candidate in [
            base_dir / "PySide6" / "plugins" / "platforms",
            base_dir / "plugins" / "platforms",
            base_dir / "platforms",
        ]:
            if plat_candidate.exists():
                os.environ["QT_QPA_PLATFORM_PLUGIN_PATH"] = str(plat_candidate)
                break

    QApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    app = QApplication(sys.argv)
    app.setApplicationName("ExamSplit AI")
    app.setApplicationVersion("0.2.0")

    # Set Windows AppUserModelID so taskbar icon pins correctly
    if sys.platform.startswith("win"):
        try:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("examsplit.ai.app.0.2.0")
        except Exception:
            pass

    # Set window and taskbar icon (.png or .ico)
    icon_path = BUNDLE_DIR / "resources" / "icon.png"
    if not icon_path.exists():
        icon_path = BUNDLE_DIR / "resources" / "icon.ico"
    if icon_path.exists():
        app.setWindowIcon(QIcon(str(icon_path)))

    # Configure Chinese/CJK fonts fallback
    from .ui.font_helper import setup_application_fonts
    setup_application_fonts(app)

    window = MainWindow(initial_pdf=args.pdf_file)
    if icon_path.exists():
        window.setWindowIcon(QIcon(str(icon_path)))
    window.show()

    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
