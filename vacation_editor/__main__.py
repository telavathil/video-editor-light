import sys


def main() -> None:
    # Full GUI launch implemented in Phase 5 (Step 5.2).
    # For now, verify the package imports cleanly.
    from vacation_editor.config import load_config
    from vacation_editor.utils.paths import ensure_project_dirs

    config = load_config()
    ensure_project_dirs(config)
    print("Vacation Video Editor — GUI coming in Phase 5.")


if __name__ == "__main__":
    main()
    sys.exit(0)
