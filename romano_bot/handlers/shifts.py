"""
Shift management handlers for Romano Bot

This module handles shift opening and closing operations with notifications
to the Telegram group.

Author: Romano Bot Team
Version: 1.0.0
"""
from datetime import datetime
from typing import Optional

from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import ContextTypes

from ..models.schema import User
from ..services.shift_manager import ShiftManager
from ..services.notifier import notify_group, format_shift_opened_notification, format_shift_closed_notification
from ..utils.helpers import logger, AuthManager, format_datetime


class ShiftsHandler:
    """
    Обработчик операций со сменами.
    
    Управляет открытием и закрытием смен с уведомлениями в группу.
    """
    
    def __init__(self):
        """Инициализация обработчика смен."""
        pass
    
    async def open_shift(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """
        Открыть новую смену.
        
        Проверяет, нет ли уже открытой смены, создает новую смену,
        отправляет уведомление в группу.
        
        Args:
            update (Update): Telegram update object
            context (ContextTypes.DEFAULT_TYPE): Bot context
        """
        user_id = update.effective_user.id
        
        try:
            # Проверить права доступа
            user = AuthManager.get_user(user_id)
            if not user or user.status != User.STATUS_ACTIVE:
                await update.message.reply_text(
                    "❌ У вас нет прав для открытия смены."
                )
                return
            
            # Проверить, нет ли уже открытой смены
            if ShiftManager.is_shift_open():
                await update.message.reply_text(
                    "⚠️ <b>Смена уже открыта!</b>\n\n"
                    "Сначала закройте текущую смену перед открытием новой.",
                    parse_mode='HTML'
                )
                return
            
            # Открыть смену
            shift = ShiftManager.open_shift(user_id)
            if not shift:
                await update.message.reply_text(
                    "❌ Произошла ошибка при открытии смены. Попробуйте еще раз."
                )
                return
            
            # Форматировать имя пользователя
            username = f"{user.first_name or ''} {user.last_name or ''}".strip() or f"ID: {user_id}"
            
            # Отправить уведомление в группу
            notification = format_shift_opened_notification(
                username=username,
                timestamp=shift.opened_at
            )
            await notify_group(context, notification)
            
            # Подтвердить пользователю
            await update.message.reply_text(
                f"✅ <b>Смена успешно открыта!</b>\n\n"
                f"🕒 <b>Время открытия:</b> {format_datetime(shift.opened_at)}\n\n"
                f"Уведомление отправлено в группу.",
                parse_mode='HTML'
            )
            
            logger.info(f"Shift opened by user {user_id} ({username})")
            
        except Exception as e:
            logger.error(f"Error opening shift: {str(e)}", user_id, exc_info=True)
            await update.message.reply_text(
                "❌ Произошла ошибка при открытии смены. Попробуйте еще раз."
            )
    
    async def close_shift(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """
        Закрыть текущую открытую смену.
        
        Проверяет наличие открытой смены, закрывает её,
        отправляет уведомление в группу с информацией о длительности.
        
        Args:
            update (Update): Telegram update object
            context (ContextTypes.DEFAULT_TYPE): Bot context
        """
        user_id = update.effective_user.id
        
        try:
            # Проверить права доступа
            user = AuthManager.get_user(user_id)
            if not user or user.status != User.STATUS_ACTIVE:
                await update.message.reply_text(
                    "❌ У вас нет прав для закрытия смены."
                )
                return
            
            # Проверить, есть ли открытая смена
            open_shift = ShiftManager.get_current_open_shift()
            if not open_shift:
                await update.message.reply_text(
                    "⚠️ <b>Нет открытой смены!</b>\n\n"
                    "Сначала откройте смену перед закрытием.",
                    parse_mode='HTML'
                )
                return
            
            # Получить информацию о пользователе, открывшем смену
            opened_by_user = AuthManager.get_user(open_shift.opened_by_user_id)
            opened_by_username = "Неизвестно"
            if opened_by_user:
                opened_by_username = (
                    f"{opened_by_user.first_name or ''} {opened_by_user.last_name or ''}".strip()
                    or f"ID: {open_shift.opened_by_user_id}"
                )
            
            # Закрыть смену
            closed_shift = ShiftManager.close_shift(user_id)
            if not closed_shift:
                await update.message.reply_text(
                    "❌ Произошла ошибка при закрытии смены. Попробуйте еще раз."
                )
                return
            
            # Вычислить длительность смены
            duration = ShiftManager.get_shift_duration(
                opened_at=closed_shift.opened_at,
                closed_at=closed_shift.closed_at
            )
            
            # Форматировать имя пользователя, закрывшего смену
            username = f"{user.first_name or ''} {user.last_name or ''}".strip() or f"ID: {user_id}"
            
            # Отправить уведомление в группу
            notification = format_shift_closed_notification(
                username=username,
                opened_by_username=opened_by_username,
                opened_at=closed_shift.opened_at,
                closed_at=closed_shift.closed_at,
                duration=duration
            )
            await notify_group(context, notification)
            
            # Подтвердить пользователю
            await update.message.reply_text(
                f"✅ <b>Смена успешно закрыта!</b>\n\n"
                f"⏱️ <b>Длительность:</b> {duration}\n"
                f"🕒 <b>Время закрытия:</b> {format_datetime(closed_shift.closed_at)}\n\n"
                f"Уведомление отправлено в группу.",
                parse_mode='HTML'
            )
            
            logger.info(f"Shift closed by user {user_id} ({username})")
            
        except Exception as e:
            logger.error(f"Error closing shift: {str(e)}", user_id, exc_info=True)
            await update.message.reply_text(
                "❌ Произошла ошибка при закрытии смены. Попробуйте еще раз."
            )
    
    async def get_shift_status(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """
        Получить статус текущей смены.
        
        Показывает информацию о текущей открытой смене или сообщает,
        что смена не открыта.
        
        Args:
            update (Update): Telegram update object
            context (ContextTypes.DEFAULT_TYPE): Bot context
        """
        user_id = update.effective_user.id
        
        try:
            open_shift = ShiftManager.get_current_open_shift()
            
            if not open_shift:
                await update.message.reply_text(
                    "ℹ️ <b>Статус смены</b>\n\n"
                    "🔴 Смена не открыта",
                    parse_mode='HTML'
                )
                return
            
            # Получить информацию о пользователе, открывшем смену
            opened_by_user = AuthManager.get_user(open_shift.opened_by_user_id)
            opened_by_username = "Неизвестно"
            if opened_by_user:
                opened_by_username = (
                    f"{opened_by_user.first_name or ''} {opened_by_user.last_name or ''}".strip()
                    or f"ID: {open_shift.opened_by_user_id}"
                )
            
            # Вычислить текущую длительность смены
            current_duration = ShiftManager.get_shift_duration(
                opened_at=open_shift.opened_at,
                closed_at=None
            )
            
            await update.message.reply_text(
                f"ℹ️ <b>Статус смены</b>\n\n"
                f"🟢 <b>Смена открыта</b>\n\n"
                f"👤 <b>Открыл:</b> {opened_by_username}\n"
                f"🕒 <b>Время открытия:</b> {format_datetime(open_shift.opened_at)}\n"
                f"⏱️ <b>Длительность:</b> {current_duration}",
                parse_mode='HTML'
            )
            
        except Exception as e:
            logger.error(f"Error getting shift status: {str(e)}", user_id, exc_info=True)
            await update.message.reply_text(
                "❌ Произошла ошибка при получении статуса смены. Попробуйте еще раз."
            )

