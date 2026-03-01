import sys


def main() -> None:
    from PyQt6.QtWidgets import QApplication

    from vacation_editor.config import load_config
    from vacation_editor.gui.main_window import MainWindow
    from vacation_editor.gui.theme import apply_theme
    from vacation_editor.utils.paths import ensure_project_dirs

    config = load_config()
    ensure_project_dirs(config)

    app = QApplication(sys.argv)
    app.setApplicationName("Vacation Editor")
    apply_theme(app)

    window = MainWindow(config)
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
