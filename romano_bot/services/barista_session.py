"""
Barista Session Manager for Romano Bot

This module provides session management for barista switching functionality.
Allows multiple baristas to work with one phone by switching active barista sessions.

Author: Romano Bot Team
Version: 1.0.0
"""
from typing import Optional
from telegram.ext import ContextTypes

from ..models.schema import User
from ..utils.helpers import logger, AuthManager


class BaristaSessionManager:
    """
    Управление сессиями бариста.
    
    Позволяет переключаться между активными бариста для работы на одном телефоне.
    Все операции (продажи, расходы) привязываются к выбранному активному бариста.
    """
    
    SESSION_KEY = 'active_barista_id'
    
    @classmethod
    def set_active_barista(
        cls, 
        user_id: int, 
        context: ContextTypes.DEFAULT_TYPE
    ) -> bool:
        """
        Установить активного бариста для текущей сессии.
        
        Args:
            user_id (int): Telegram ID бариста
            context (ContextTypes.DEFAULT_TYPE): Bot context
            
        Returns:
            bool: True если бариста успешно установлен, False если ошибка
        """
        try:
            # Проверить, что пользователь существует и является активным бариста
            user = AuthManager.get_user(user_id)
            if not user:
                logger.warning(f"Attempted to set non-existent user {user_id} as active barista")
                return False
            
            # Проверить, что пользователь является бариста
            if not user.is_barista():
                logger.warning(
                    f"Attempted to set non-barista user {user_id} (role: {user.role}) as active barista"
                )
                return False
            
            # Проверить, что пользователь активен
            if user.status != User.STATUS_ACTIVE:
                logger.warning(
                    f"Attempted to set inactive user {user_id} (status: {user.status}) as active barista"
                )
                return False
            
            # Сохранить в context
            context.user_data[cls.SESSION_KEY] = user_id
            logger.info(f"Active barista set to user {user_id} ({user.first_name} {user.last_name or ''})")
            return True
            
        except Exception as e:
            logger.error(f"Error setting active barista {user_id}: {str(e)}", exc_info=True)
            return False
    
    @classmethod
    def get_active_barista(
        cls, 
        context: ContextTypes.DEFAULT_TYPE
    ) -> Optional[User]:
        """
        Получить объект активного бариста.
        
        Args:
            context (ContextTypes.DEFAULT_TYPE): Bot context
            
        Returns:
            Optional[User]: Объект пользователя-бариста или None если не выбран
        """
        try:
            user_id = cls.get_active_barista_id(context)
            if not user_id:
                return None
            
            user = AuthManager.get_user(user_id)
            
            # Проверить, что бариста все еще активен
            if user and user.is_barista() and user.status == User.STATUS_ACTIVE:
                return user
            else:
                # Если бариста был деактивирован, очистить выбор
                if user:
                    logger.warning(
                        f"Active barista {user_id} is no longer active (status: {user.status}), clearing selection"
                    )
                cls.clear_active_barista(context)
                return None
                
        except Exception as e:
            logger.error(f"Error getting active barista: {str(e)}", exc_info=True)
            return None
    
    @classmethod
    def get_active_barista_id(
        cls, 
        context: ContextTypes.DEFAULT_TYPE
    ) -> Optional[int]:
        """
        Получить ID активного бариста.
        
        Args:
            context (ContextTypes.DEFAULT_TYPE): Bot context
            
        Returns:
            Optional[int]: Telegram ID активного бариста или None если не выбран
        """
        try:
            return context.user_data.get(cls.SESSION_KEY)
        except (AttributeError, KeyError):
            return None
    
    @classmethod
    def clear_active_barista(
        cls, 
        context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """
        Очистить выбор активного бариста.
        
        Args:
            context (ContextTypes.DEFAULT_TYPE): Bot context
        """
        try:
            if cls.SESSION_KEY in context.user_data:
                removed_id = context.user_data.pop(cls.SESSION_KEY)
                logger.info(f"Active barista cleared (was: {removed_id})")
        except Exception as e:
            logger.error(f"Error clearing active barista: {str(e)}", exc_info=True)
    
    @classmethod
    def get_all_active_baristas(cls) -> list[User]:
        """
        Получить список всех активных бариста.
        
        Returns:
            list[User]: Список активных бариста (отсоединенных от сессии)
        """
        try:
            from ..services.database import get_session
            
            with get_session() as session:
                baristas = session.query(User).filter(
                    User.role.in_([User.ROLE_BARISTA, User.ROLE_BARISTA_LEGACY]),
                    User.status == User.STATUS_ACTIVE
                ).all()
                
                # Загрузить все необходимые атрибуты до закрытия сессии
                # Это гарантирует, что они будут доступны после expunge
                for barista in baristas:
                    # Принудительно загрузить все атрибуты, которые могут понадобиться
                    _ = barista.first_name
                    _ = barista.last_name
                    _ = barista.telegram_id
                    _ = barista.role
                    _ = barista.status
                    
                    # Отсоединить объект от сессии
                    session.expunge(barista)
                
                # Отсортировать по имени
                # Используем безопасный доступ через __dict__ для отсоединенных объектов
                baristas.sort(key=lambda u: (
                    u.__dict__.get('first_name', '') or '',
                    u.__dict__.get('last_name', '') or ''
                ))
                return baristas
                
        except Exception as e:
            logger.error(f"Error getting active baristas: {str(e)}", exc_info=True)
            return []
    
    @classmethod
    def format_barista_name(cls, user: User) -> str:
        """
        Форматировать имя бариста для отображения.
        
        Args:
            user (User): Объект пользователя (может быть отсоединен от сессии)
            
        Returns:
            str: Отформатированное имя
        """
        if not user:
            return "Неизвестно"
        
        try:
            from sqlalchemy import inspect
            
            # Проверить, отсоединен ли объект от сессии
            obj_inspect = inspect(user)
            is_detached = obj_inspect.detached
            
            if is_detached:
                # Если объект отсоединен, использовать __dict__ для доступа к атрибутам
                # без триггера lazy loading
                first_name = user.__dict__.get('first_name', None) or ""
                last_name = user.__dict__.get('last_name', None) or ""
            else:
                # Если объект все еще привязан к сессии, можно использовать обычный доступ
                first_name = getattr(user, 'first_name', None) or ""
                last_name = getattr(user, 'last_name', None) or ""
            
            name = first_name
            if last_name:
                name += f" {last_name}"
            
            return name.strip() or "Неизвестно"
        except Exception as e:
            logger.error(f"Error formatting barista name: {str(e)}", exc_info=True)
            # Fallback: попробовать получить из __dict__ напрямую
            try:
                first_name = user.__dict__.get('first_name', None) or ""
                last_name = user.__dict__.get('last_name', None) or ""
                name = first_name
                if last_name:
                    name += f" {last_name}"
                return name.strip() or "Неизвестно"
            except Exception:
                return "Неизвестно"

