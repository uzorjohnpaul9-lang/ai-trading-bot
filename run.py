"""
Run Script - Quick Start
========================
Choose what to run.
"""
import sys
import os


def main():
    print("=" * 50)
    print("  AI Trading Bot")
    print("=" * 50)
    print("\n  What do you want to run?\n")
    print("  1. Trading Bot (CLI)")
    print("  2. Web Dashboard")
    print("  3. API Server")
    print("  4. Backtest")
    print("  5. Setup/Install")
    print("  0. Exit")
    print()

    choice = input("  Enter choice (0-5): ").strip()

    if choice == "1":
        os.system(f"{sys.executable} bot.py")
    elif choice == "2":
        os.system(f"{sys.executable} -m streamlit run dashboard.py")
    elif choice == "3":
        os.system(f"{sys.executable} api.py")
    elif choice == "4":
        symbol = input("  Enter symbol (default: BTCUSDT): ").strip() or "BTCUSDT"
        os.system(f"{sys.executable} bot.py --backtest --symbol {symbol}")
    elif choice == "5":
        os.system(f"{sys.executable} setup.py")
    elif choice == "0":
        print("  Goodbye!")
    else:
        print("  Invalid choice")


if __name__ == "__main__":
    main()
