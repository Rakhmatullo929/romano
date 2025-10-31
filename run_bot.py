#!/usr/bin/env python3
"""
Romano Bot Launcher

This script launches the Romano Coffee Shop Telegram bot.
"""
import os
import sys

# Add the project root to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import and run the bot
from romano_bot.main import main

if __name__ == "__main__":
    main()

