"""Build script to compile Trading Agent Desktop GUI into a standalone Windows .exe using PyInstaller."""

import os
import sys
import PyInstaller.__main__


def build():
    print("Starting compilation of TradingAgent.exe...")

    args = [
        "run_gui.py",
        "--name=TradingAgent",
        "--onefile",
        "--noconsole",
        "--clean",
        "--hidden-import=pandas",
        "--hidden-import=numpy",
        "--hidden-import=yfinance",
        "--hidden-import=ccxt",
        "--hidden-import=pydantic",
        "--hidden-import=requests",
        "--hidden-import=rich",
        "--hidden-import=trading_agent",
        "--hidden-import=trading_agent.core",
        "--hidden-import=trading_agent.strategies",
        "--hidden-import=trading_agent.risk",
        "--hidden-import=trading_agent.engine",
        "--hidden-import=trading_agent.github_tool",
        "--hidden-import=trading_agent.gui",
    ]

    PyInstaller.__main__.run(args)
    print("\nCompilation completed!")
    if os.path.exists("dist/TradingAgent.exe"):
        size_mb = os.path.getsize("dist/TradingAgent.exe") / (1024 * 1024)
        print(f"Success! Executable generated at: dist/TradingAgent.exe ({size_mb:.2f} MB)")
    else:
        print("Warning: Executable not found in dist/")


if __name__ == "__main__":
    build()
