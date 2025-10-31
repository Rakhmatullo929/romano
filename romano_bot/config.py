"""
Configuration settings for Romano Bot

This module contains all configuration constants and settings for the Romano
Coffee Shop Telegram bot, including bot tokens, database settings, product
prices, and validation functions.

Author: Romano Bot Team
Version: 1.0.0
"""
import os

# Bot Configuration
BOT_TOKEN: str = os.getenv('BOT_TOKEN', '7550875001:AAH1eAZRkRML93HGHk-Aewla4OHrJ2Xtyyo')
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
