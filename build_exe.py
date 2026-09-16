"""Build script to compile Trading Agent Pro Desktop Launcher into a standalone Windows .exe using PyInstaller."""

import os
import sys
import PyInstaller.__main__


def build():
    print("Starting compilation of new TradingAgent.exe...")

    work_dir = os.path.join(os.environ.get("TEMP", "."), "pyinstaller_build")
    args = [
        "launch_app.py",
        "--name=TradingAgent",
        "--onefile",
        "--clean",
        f"--workpath={work_dir}",
        "--add-data=trading_agent/web/templates;trading_agent/web/templates",
        "--hidden-import=uvicorn",
        "--hidden-import=uvicorn.logging",
        "--hidden-import=uvicorn.loops",
        "--hidden-import=uvicorn.loops.auto",
        "--hidden-import=uvicorn.protocols",
        "--hidden-import=uvicorn.protocols.http",
        "--hidden-import=uvicorn.protocols.http.auto",
        "--hidden-import=uvicorn.lifespan",
        "--hidden-import=uvicorn.lifespan.on",
        "--hidden-import=fastapi",
        "--hidden-import=starlette",
        "--hidden-import=jinja2",
        "--hidden-import=anyio",
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
        "--hidden-import=trading_agent.live",
        "--hidden-import=trading_agent.ai",
        "--hidden-import=trading_agent.ai.chat_engine",
        "--hidden-import=trading_agent.web",
        "--hidden-import=trading_agent.web.app",
    ]

    PyInstaller.__main__.run(args)
    print("\nCompilation completed!")
    if os.path.exists("dist/TradingAgent.exe"):
        size_mb = os.path.getsize("dist/TradingAgent.exe") / (1024 * 1024)
        print(f"Success! Executable generated at: dist/TradingAgent.exe ({size_mb:.2f} MB)")
        # Copy to root workspace
        import shutil
        shutil.copy("dist/TradingAgent.exe", "TradingAgent.exe")
        print("Copied TradingAgent.exe to root folder.")
    else:
        print("Warning: Executable not found in dist/")


if __name__ == "__main__":
    build()
