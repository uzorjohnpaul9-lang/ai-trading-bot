"""
Setup Script
============
One-time setup for the AI Trading Bot.
"""
import subprocess
import sys
import os


def run(cmd):
    print(f"\n> {cmd}")
    result = subprocess.run(cmd, shell=True)
    return result.returncode == 0


def main():
    print("=" * 50)
    print("  AI Trading Bot - Setup")
    print("=" * 50)

    # Install dependencies
    print("\n[1/3] Installing dependencies...")
    if not run(f"{sys.executable} -m pip install -r requirements.txt"):
        print("Failed to install dependencies!")
        return

    # Create .env if not exists
    print("\n[2/3] Setting up configuration...")
    if not os.path.exists(".env"):
        if os.path.exists(".env.example"):
            run("copy .env.example .env")
            print("Created .env file - edit it with your settings")
        else:
            print("No .env.example found")
    else:
        print(".env already exists")

    # Initialize database
    print("\n[3/3] Initializing database...")
    try:
        from database import init_db
        init_db()
        print("Database initialized!")
    except Exception as e:
        print(f"Database init failed: {e}")

    print("\n" + "=" * 50)
    print("  Setup complete!")
    print("=" * 50)
    print("\nTo run:")
    print("  python bot.py           - Run trading bot")
    print("  python bot.py --backtest - Run backtest")
    print("  python dashboard.py     - Open web dashboard")
    print("  python api.py           - Start API server")
    print("=" * 50)


if __name__ == "__main__":
    main()
