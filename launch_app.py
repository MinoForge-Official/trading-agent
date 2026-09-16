"""1-Click Launcher for Trading Agent Pro Modern Web Trading Desk."""

import os
import sys
import threading
import time
import webbrowser
import uvicorn


def open_browser():
    time.sleep(1.2)
    print("\nOpening Trading Agent Pro in your web browser...")
    webbrowser.open("http://localhost:8000")


def main():
    print("=" * 65)
    print("  TRADING AGENT PRO - LIVE TRADING SITE AUTOMATION PLATFORM")
    print("  Author: MinoForge-Official")
    print("=" * 65)
    print("\nStarting local high-speed web server on http://localhost:8000 ...")

    threading.Thread(target=open_browser, daemon=True).start()
    uvicorn.run("trading_agent.web.app:app", host="127.0.0.1", port=8000, log_level="info")


if __name__ == "__main__":
    main()
