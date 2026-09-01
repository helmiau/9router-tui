"""Shim — keeps python app.py and PyInstaller working. Real code is in tui/."""
from tui.app import NineRouterTUI, APP_VERSION
from tui.screens.picker import ServerPickerScreen
from client import NinerouterClient, load_config_from_env_and_file, _get_app_dir
import os
import sys
import traceback
from datetime import datetime


def _global_excepthook(exc_type, exc_value, exc_tb):
    """Fallback: write any uncaught exception to a crash log so it isn't lost."""
    try:
        base = _get_app_dir()
        os.makedirs(os.path.join(base, "logs"), exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d-%H%M%S")
        path = os.path.join(base, "logs", f"9router-tui-crash-{ts}.log")
        tb = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
        with open(path, "w", encoding="utf-8") as f:
            f.write(f"9Router TUI uncaught exception\nTime: {datetime.now().isoformat()}\nVersion: {APP_VERSION}\n\n{tb}\n")
        sys.stderr.write(f"\n[9Router TUI] Fatal error logged to: {path}\n{tb}\n")
    except Exception:
        sys.stderr.write("".join(traceback.format_exception(exc_type, exc_value, exc_tb)))


sys.excepthook = _global_excepthook

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description=f"9Router Terminal Dashboard v{APP_VERSION} (standalone)")
    parser.add_argument("--version", action="version", version=f"%(prog)s {APP_VERSION}")
    parser.add_argument("--url", default=None, help="9Router base URL (default: NINEROUTER_URL or http://localhost:20128)")
    parser.add_argument("--api-key", default=None, help="API key (default: NINEROUTER_KEY)")
    parser.add_argument("--config", default=None, help="Path to config.toml")
    args = parser.parse_args()
    cfg = load_config_from_env_and_file(args.config)
    if args.url:
        cfg.url = args.url
    if args.api_key:
        cfg.api_key = args.api_key
    if os.getenv("NINEROUTER_URL"):
        cfg.url = os.getenv("NINEROUTER_URL", cfg.url)
    if os.getenv("NINEROUTER_KEY"):
        cfg.api_key = os.getenv("NINEROUTER_KEY", cfg.api_key)
    client = NinerouterClient(cfg)
    app = NineRouterTUI(client)
    app.run()
