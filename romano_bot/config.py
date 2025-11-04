"""
Configuration settings for Romano Bot

This module contains all configuration constants and settings for the Romano
Coffee Shop Telegram bot, including bot tokens, database settings, product
prices, and validation functions.

Author: Romano Bot Team
Version: 1.0.0
"""
import os
from pathlib import Path

# Load .env file if it exists
try:
    from dotenv import load_dotenv
    # Get project root directory (parent of romano_bot directory)
    project_root = Path(__file__).parent.parent
    env_path = project_root / '.env'
    if env_path.exists():
        load_dotenv(env_path, override=True)
        # Debug: log if GROUP_CHAT_ID is loaded
        if os.getenv('GROUP_CHAT_ID'):
            print(f"[CONFIG] GROUP_CHAT_ID loaded from .env: {os.getenv('GROUP_CHAT_ID')}")
    else:
        print(f"[CONFIG] .env file not found at {env_path}")
except ImportError:
    # python-dotenv not installed, skip
    print("[CONFIG] python-dotenv not installed, .env file will not be loaded")
    pass
except Exception as e:
    # Error loading .env, log it
    print(f"[CONFIG] Error loading .env file: {e}")
    pass

# Bot Configuration
BOT_TOKEN: str = os.getenv('BOT_TOKEN', '7550875001:AAE14C-W96_Omx8XoNlAIyvxJ6NHiqS0ouM')
ADMIN_IDS: list[int] = [int(x) for x in os.getenv('ADMIN_IDS', '123456789,279498964').split(',') if x.strip()]

# Database Configuration
DATABASE_URL: str = os.getenv('DATABASE_URL', 'sqlite:///romano_bot.db')

# Currency Configuration
CURRENCY: str = 'UZS'
CURRENCY_SYMBOL: str = 'сум'

# Product Prices (in UZS)
PRODUCT_PRICES = {
    'Американо': 12000,
    'Капучино': 15000,
    'Латте': 16000,
    'Чай': 8000,
    'Десерт': 20000
}

# Expense Categories
EXPENSE_CATEGORIES = {
    'Закуп': '🛒',
    'Зарплата': '👥',
    'Списание': '📉'
}

# Bot Settings
MAX_MESSAGE_LENGTH: int = 4096
REQUEST_TIMEOUT: int = 30

# Notifications Configuration
GROUP_CHAT_ID: str = os.getenv('GROUP_CHAT_ID', '')  # ID группы для уведомлений
ENABLE_NOTIFICATIONS: bool = os.getenv('ENABLE_NOTIFICATIONS', 'True').lower() == 'true'  # Включить/выключить уведомления

# Debug: Log GROUP_CHAT_ID status on startup
if GROUP_CHAT_ID:
    print(f"[CONFIG] GROUP_CHAT_ID is configured: {GROUP_CHAT_ID}")
else:
    print("[CONFIG] WARNING: GROUP_CHAT_ID is not configured. Notifications will not be sent.")

# Validation
def validate_config() -> bool:
    """
    Validate that all required configuration is present.
    
    Checks for required environment variables and raises ValueError if any are missing.
    
    Returns:
        bool: True if all required configuration is present
        
    Raises:
        ValueError: If required environment variables are missing
    """
    if not BOT_TOKEN:
        raise ValueError("BOT_TOKEN environment variable is required")
    if not ADMIN_IDS:
        raise ValueError("ADMIN_IDS environment variable is required")
    return True
