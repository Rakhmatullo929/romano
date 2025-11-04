"""
Notification service for Romano Bot

This module handles sending notifications to Telegram group
when users perform actions in the bot.

Author: Romano Bot Team
Version: 1.0.0
"""
from datetime import datetime
from telegram.ext import ContextTypes
from decimal import Decimal

from ..config import GROUP_CHAT_ID, ENABLE_NOTIFICATIONS, EXPENSE_CATEGORIES
from ..utils.helpers import logger, format_currency, format_datetime


async def notify_group(context: ContextTypes.DEFAULT_TYPE, message: str) -> None:
    """
    Отправляет сообщение в группу при любом действии пользователя.
    
    Args:
        context (ContextTypes.DEFAULT_TYPE): Bot context
        message (str): Текст уведомления для отправки
    """
    # Проверяем, включены ли уведомления
    if not ENABLE_NOTIFICATIONS:
        return
    
    # Проверяем, что ID группы задан
    if not GROUP_CHAT_ID:
        logger.warning("GROUP_CHAT_ID not configured, skipping notification")
        return
    
    try:
        await context.bot.send_message(
            chat_id=GROUP_CHAT_ID,
            text=message,
            parse_mode='HTML'
        )
        logger.info(f"Notification sent to group {GROUP_CHAT_ID}")
    except Exception as e:
        # Логируем ошибку, но не останавливаем выполнение основной функции
        logger.error(
            f"Failed to send notification to group {GROUP_CHAT_ID}: {str(e)}",
            exc_info=True
        )


def format_sale_notification(
    username: str,
    product_name: str,
    quantity: int,
    total_price: Decimal,
    timestamp: datetime
) -> str:
    """
    Форматирует уведомление о новой продаже.
    
    Args:
        username (str): Имя пользователя (бариста)
        product_name (str): Название продукта
        quantity (int): Количество
        total_price (Decimal): Итоговая сумма
        timestamp (datetime): Время продажи
        
    Returns:
        str: Отформатированное уведомление
    """
    message = "🧾 <b>Новая продажа</b>\n\n"
    message += f"👤 <b>Бариста:</b> {username}\n"
    message += f"☕ <b>Продукт:</b> {product_name}\n"
    message += f"🔢 <b>Количество:</b> {quantity}\n"
    message += f"💰 <b>Сумма:</b> {format_currency(total_price)}\n"
    message += f"🕒 <b>Время:</b> {format_datetime(timestamp)}"
    
    return message


def format_expense_notification(
    username: str,
    category: str,
    amount: Decimal,
    note: str,
    timestamp: datetime
) -> str:
    """
    Форматирует уведомление о новом расходе.
    
    Args:
        username (str): Имя пользователя (сотрудник)
        category (str): Категория расхода
        amount (Decimal): Сумма расхода
        note (str): Комментарий/причина расхода
        timestamp (datetime): Время расхода
        
    Returns:
        str: Отформатированное уведомление
    """
    # Получаем эмодзи для категории
    category_emoji = EXPENSE_CATEGORIES.get(category, '📦')
    
    message = "📉 <b>Новый расход</b>\n\n"
    message += f"👤 <b>Сотрудник:</b> {username}\n"
    message += f"📦 <b>Категория:</b> {category_emoji} {category}\n"
    message += f"💸 <b>Сумма:</b> {format_currency(amount)}\n"
    message += f"📝 <b>Комментарий:</b> {note}\n"
    message += f"🕒 <b>Время:</b> {format_datetime(timestamp)}"
    
    return message


def format_report_notification(
    username: str,
    period: str,
    period_name: str
) -> str:
    """
    Форматирует уведомление о сформированном отчёте.
    
    Args:
        username (str): Имя пользователя
        period (str): Период (day/week/month)
        period_name (str): Название периода
        
    Returns:
        str: Отформатированное уведомление
    """
    # Маппинг периодов на читаемые названия
    period_map = {
        'day': 'день',
        'week': 'неделю',
        'month': 'месяц'
    }
    period_display = period_map.get(period, period)
    
    message = f"📊 <b>Сформирован отчёт ({period_display})</b>\n\n"
    message += f"👤 <b>Пользователь:</b> {username}\n"
    message += f"🗓️ <b>Период:</b> {period_name}\n"
    message += f"📎 <b>Файл отчёта отправлен</b>"
    
    return message

