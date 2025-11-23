"""
Shift management service for Romano Bot

This module provides shift management functionality including opening/closing shifts,
checking shift status, and calculating shift duration.

Author: Romano Bot Team
Version: 1.0.0
"""
from datetime import datetime, timedelta
from typing import Optional

from ..models.schema import Shift
from ..services.database import get_session
from ..utils.helpers import logger


class ShiftManager:
    """
    Управление сменами.
    
    Предоставляет функциональность для открытия и закрытия смен,
    проверки статуса смены и расчета длительности.
    """
    
    @staticmethod
    def get_current_open_shift() -> Optional[Shift]:
        """
        Получить текущую открытую смену.
        
        Returns:
            Optional[Shift]: Объект открытой смены или None если смена не открыта
        """
        try:
            with get_session() as session:
                shift = session.query(Shift).filter(
                    Shift.is_open == True
                ).order_by(Shift.opened_at.desc()).first()
                
                if shift:
                    # Явно загрузить все атрибуты в память и сохранить в __dict__
                    # Это гарантирует доступность атрибутов после закрытия сессии
                    shift_dict = {
                        'id': shift.id,
                        'opened_by_user_id': shift.opened_by_user_id,
                        'closed_by_user_id': shift.closed_by_user_id,
                        'opened_at': shift.opened_at,
                        'closed_at': shift.closed_at,
                        'is_open': shift.is_open,
                        'notes': shift.notes,
                        'created_at': shift.created_at,
                        'updated_at': getattr(shift, 'updated_at', None)
                    }
                    
                    # Отсоединить объект от сессии
                    session.expunge(shift)
                    
                    # Установить значения напрямую в __dict__ для гарантированного доступа
                    for key, value in shift_dict.items():
                        if value is not None or key in ['is_open']:  # is_open может быть False
                            shift.__dict__[key] = value
                
                return shift
        except Exception as e:
            logger.error(f"Error getting current open shift: {str(e)}", exc_info=True)
            return None
    
    @staticmethod
    def is_shift_open() -> bool:
        """
        Проверить, есть ли открытая смена.
        
        Returns:
            bool: True если есть открытая смена, False в противном случае
        """
        shift = ShiftManager.get_current_open_shift()
        return shift is not None
    
    @staticmethod
    def open_shift(user_id: int) -> Optional[Shift]:
        """
        Открыть новую смену.
        
        Args:
            user_id (int): ID пользователя, открывающего смену
            
        Returns:
            Optional[Shift]: Объект созданной смены или None при ошибке
        """
        try:
            # Проверить, нет ли уже открытой смены
            if ShiftManager.is_shift_open():
                logger.warning(f"Attempted to open shift while one is already open (user: {user_id})")
                return None
            
            with get_session() as session:
                opened_at_time = datetime.utcnow()
                shift = Shift(
                    opened_by_user_id=user_id,
                    opened_at=opened_at_time,
                    is_open=True
                )
                session.add(shift)
                session.flush()  # Получить ID без commit
                session.refresh(shift)  # Загрузить все атрибуты из БД
                session.commit()
                
                # Явно загрузить все атрибуты в память и сохранить в __dict__
                # Это гарантирует доступность атрибутов после закрытия сессии
                # Используем __dict__ для прямого доступа к атрибутам
                shift_dict = {
                    'id': shift.id,
                    'opened_by_user_id': shift.opened_by_user_id,
                    'opened_at': shift.opened_at,
                    'is_open': shift.is_open,
                    'created_at': shift.created_at,
                    'closed_by_user_id': shift.closed_by_user_id,
                    'closed_at': shift.closed_at,
                    'notes': shift.notes,
                    'updated_at': getattr(shift, 'updated_at', None)
                }
                
                # Отсоединить объект от сессии
                session.expunge(shift)
                
                # Установить значения напрямую в __dict__ для гарантированного доступа
                for key, value in shift_dict.items():
                    if value is not None or key in ['is_open']:  # is_open может быть False
                        shift.__dict__[key] = value
                
                logger.info(f"Shift opened by user {user_id}")
                return shift
                
        except Exception as e:
            logger.error(f"Error opening shift for user {user_id}: {str(e)}", exc_info=True)
            return None
    
    @staticmethod
    def close_shift(user_id: int, notes: Optional[str] = None) -> Optional[Shift]:
        """
        Закрыть текущую открытую смену.
        
        Args:
            user_id (int): ID пользователя, закрывающего смену
            notes (Optional[str]): Дополнительные заметки при закрытии
            
        Returns:
            Optional[Shift]: Объект закрытой смены или None при ошибке
        """
        try:
            # Получить текущую открытую смену
            shift = ShiftManager.get_current_open_shift()
            if not shift:
                logger.warning(f"Attempted to close shift but no open shift found (user: {user_id})")
                return None
            
            with get_session() as session:
                # Загрузить смену заново для обновления
                shift_to_close = session.query(Shift).filter(Shift.id == shift.id).first()
                if not shift_to_close:
                    logger.error(f"Shift {shift.id} not found in database")
                    return None
                
                shift_to_close.closed_by_user_id = user_id
                shift_to_close.closed_at = datetime.utcnow()
                shift_to_close.is_open = False
                if notes:
                    shift_to_close.notes = notes
                
                session.commit()
                session.refresh(shift_to_close)  # Загрузить все атрибуты из БД после commit
                
                # Явно загрузить все атрибуты в память и сохранить в __dict__
                # Это гарантирует доступность атрибутов после закрытия сессии
                shift_dict = {
                    'id': shift_to_close.id,
                    'opened_by_user_id': shift_to_close.opened_by_user_id,
                    'closed_by_user_id': shift_to_close.closed_by_user_id,
                    'opened_at': shift_to_close.opened_at,
                    'closed_at': shift_to_close.closed_at,
                    'is_open': shift_to_close.is_open,
                    'notes': shift_to_close.notes,
                    'created_at': shift_to_close.created_at,
                    'updated_at': getattr(shift_to_close, 'updated_at', None)
                }
                
                # Отсоединить объект от сессии
                session.expunge(shift_to_close)
                
                # Установить значения напрямую в __dict__ для гарантированного доступа
                for key, value in shift_dict.items():
                    if value is not None or key in ['is_open']:  # is_open может быть False
                        shift_to_close.__dict__[key] = value
                
                logger.info(f"Shift {shift_to_close.id} closed by user {user_id}")
                return shift_to_close
                
        except Exception as e:
            logger.error(f"Error closing shift for user {user_id}: {str(e)}", exc_info=True)
            return None
    
    @staticmethod
    def get_shift_duration(opened_at: datetime, closed_at: Optional[datetime] = None) -> str:
        """
        Вычислить длительность смены в читаемом формате.
        
        Args:
            opened_at (datetime): Время открытия смены
            closed_at (Optional[datetime]): Время закрытия смены (если None, используется текущее время)
            
        Returns:
            str: Отформатированная длительность смены (например, "2ч 30м")
        """
        if closed_at is None:
            closed_at = datetime.utcnow()
        
        duration = closed_at - opened_at
        
        total_seconds = int(duration.total_seconds())
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        
        if hours > 0 and minutes > 0:
            return f"{hours}ч {minutes}м"
        elif hours > 0:
            return f"{hours}ч"
        elif minutes > 0:
            return f"{minutes}м"
        else:
            return "менее минуты"
    
    @staticmethod
    def get_recent_shifts(limit: int = 10) -> list[Shift]:
        """
        Получить список последних смен.
        
        Args:
            limit (int): Максимальное количество смен для возврата
            
        Returns:
            list[Shift]: Список последних смен
        """
        try:
            with get_session() as session:
                shifts = session.query(Shift).order_by(
                    Shift.opened_at.desc()
                ).limit(limit).all()
                
                # Отсоединить объекты от сессии
                for shift in shifts:
                    session.expunge(shift)
                
                return shifts
        except Exception as e:
            logger.error(f"Error getting recent shifts: {str(e)}", exc_info=True)
            return []

