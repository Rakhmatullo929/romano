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

# Menu Structure - Categories and Products with Prices (in UZS)
MENU_CATEGORIES = {
    'Кофе': {
        'Эспрессо': 18000,
        'Доппио': 35000,
        'Лунго': 18000,
        'Ристретто': 18000,
        'Американо': 20000,
        'Лонг Блэк': 20000,
        'Макиато': 25000,
        'Флэт Уайт': 25000,
        'Капучино': 25000,
        'Латте': 25000,
        'Spanish Латте': 28000,
        'Раф': 30000,
        'Горячий шоколад': 25000,
        'Какао': 25000,
        'Мокко': 30000,
        'Аффогато': 35000
    },
    'Холодный кофе': {
        'Ice Американо': 20000,
        'Ice Капучино / Фраппе': 25000,
        'Ice Латте': 25000,
        'Бамбл': 25000
    },
    'Чай': {
        'Черный (0.4л)': 8000,
        'Черный (0.8л)': 12000,
        'Зеленый (0.4л)': 8000,
        'Зеленый (0.8л)': 12000,
        'Пуэр (0.4л)': 16000,
        'Пуэр (0.8л)': 20000,
        'Чай с лимоном (0.4л)': 15000,
        'Чай с лимоном (0.8л)': 20000,
        'Манго маракуя (0.4л)': 20000,
        'Манго маракуя (0.8л)': 30000,
        'Глинтвейн (0.4л)': 25000,
        'Глинтвейн (0.8л)': 35000,
        'Ягодный (0.4л)': 20000,
        'Ягодный (0.8л)': 30000,
        'Маракандский (0.4л)': 20000,
        'Маракандский (0.8л)': 30000,
        'Цитрусовый (0.4л)': 20000,
        'Цитрусовый (0.8л)': 30000,
        'Малиновый (0.4л)': 20000,
        'Малиновый (0.8л)': 30000,
        'Тархун (0.4л)': 20000,
        'Тархун (0.8л)': 30000,
        'Карак чай': 15000
    },
    'Холодные напитки': {
        'Мохито Classic': 25000,
        'Мохито Клубника': 25000,
        'Мохито Малина': 25000,
        'Мохито Голубое крюасао': 25000,
        'Ice Tea': 25000,
        'Пина колада': 30000,
        'Манго-маракуя': 30000,
        'Малиновый сауэр': 30000
    },
    'Милкшейки': {
        'Classic': 30000,
        'Банановый': 30000,
        'Клубничный': 30000,
        'Bounty': 30000,
        'Snickers': 30000,
        'Oreo': 35000,
        'Ореховый': 35000
    },
    'Лимонады': {
        'Classic': 20000,
        'Ягодный': 25000,
        'Тархун': 25000,
        'Малиновый': 25000,
        'Клубничный': 25000
    },
    'Фреш': {
        'Яблочный': 45000,
        'Апельсиновый': 45000,
        'Морковный': 45000,
        'Лимонный': 45000
    },
    'Добавки': {
        'Сироп': 3000
    }
}

# Legacy support - flat product prices for backward compatibility
# Generate flat product prices from menu structure
PRODUCT_PRICES = {}
for category, products in MENU_CATEGORIES.items():
    PRODUCT_PRICES.update(products)

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
