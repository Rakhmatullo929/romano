"""
Helper utilities for Romano Bot
"""
import os
import logging
import signal
import sys
import fcntl
from decimal import Decimal
from typing import Union, Optional, Callable, Any
from datetime import datetime
from functools import wraps

from ..config import CURRENCY_SYMBOL
from ..models.schema import User


class BotLogger:
    """Centralized logging system for Romano Bot"""
    
    _instance = None
    _logger = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(BotLogger, cls).__new__(cls)
        return cls._instance
    
    def __init__(self):
        if self._logger is None:
            self._setup_logger()
    
    def _setup_logger(self):
        """Setup logger configuration"""
        # Create logs directory if it doesn't exist
        log_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'logs')
        os.makedirs(log_dir, exist_ok=True)
        
        # Configure logger
        self._logger = logging.getLogger('romano_bot')
        self._logger.setLevel(logging.INFO)
        
        # Clear existing handlers
        self._logger.handlers.clear()
        
        # Create formatter
        formatter = logging.Formatter(
            '[%(asctime)s] [%(levelname)s] %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        
        # File handler
        file_handler = logging.FileHandler(
            os.path.join(log_dir, 'bot.log'),
            encoding='utf-8'
        )
        file_handler.setLevel(logging.INFO)
        file_handler.setFormatter(formatter)
        self._logger.addHandler(file_handler)
        
        # Console handler
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(formatter)
        self._logger.addHandler(console_handler)
    
    def info(self, message: str, user_id: Optional[int] = None):
        """Log info message"""
        if user_id:
            message = f"[User:{user_id}] {message}"
        self._logger.info(message)
    
    def warning(self, message: str, user_id: Optional[int] = None):
        """Log warning message"""
        if user_id:
            message = f"[User:{user_id}] {message}"
        self._logger.warning(message)
    
    def error(self, message: str, user_id: Optional[int] = None, exc_info: bool = True):
        """Log error message"""
        if user_id:
            message = f"[User:{user_id}] {message}"
        self._logger.error(message, exc_info=exc_info)
    
    def debug(self, message: str, user_id: Optional[int] = None):
        """Log debug message"""
        if user_id:
            message = f"[User:{user_id}] {message}"
        self._logger.debug(message)
    
    def critical(self, message: str, user_id: Optional[int] = None, exc_info: bool = True):
        """Log critical message"""
        if user_id:
            message = f"[User:{user_id}] {message}"
        self._logger.critical(message, exc_info=exc_info)


# Global logger instance
logger = BotLogger()


class FileLock:
    """File-based locking mechanism to prevent multiple bot instances"""
    
    def __init__(self, lock_file: str = None):
        if lock_file is None:
            project_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
            lock_file = os.path.join(project_root, '.bot.lock')
        self.lock_file = lock_file
        self.lock_fd = None
    
    def acquire(self) -> bool:
        """
        Acquire lock.
        
        Returns:
            bool: True if lock acquired, False if another instance is running
        """
        try:
            # Try to open/create lock file
            self.lock_fd = open(self.lock_file, 'w')
            
            # Try to acquire exclusive lock (non-blocking)
            fcntl.flock(self.lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            
            # Write PID to lock file
            self.lock_fd.write(str(os.getpid()))
            self.lock_fd.flush()
            
            logger.info("Lock acquired successfully")
            return True
            
        except (IOError, BlockingIOError):
            # Lock file exists and is locked by another process
            if self.lock_fd:
                try:
                    self.lock_fd.close()
                except:
                    pass
            return False
    
    def release(self):
        """Release lock"""
        try:
            if self.lock_fd:
                fcntl.flock(self.lock_fd, fcntl.LOCK_UN)
                self.lock_fd.close()
            
            if os.path.exists(self.lock_file):
                os.remove(self.lock_file)
            
            logger.info("Lock released successfully")
        except Exception as e:
            logger.error(f"Error releasing lock: {e}")
    
    def __enter__(self):
        if not self.acquire():
            raise RuntimeError("Could not acquire lock. Another bot instance is running.")
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.release()


def log_function_call(func_name: str, user_id: Optional[int] = None):
    """Decorator to log function calls"""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            logger.info(f"Calling {func_name}", user_id)
            try:
                result = await func(*args, **kwargs)
                logger.info(f"Successfully completed {func_name}", user_id)
                return result
            except Exception as e:
                logger.error(f"Error in {func_name}: {str(e)}", user_id)
                raise
        return async_wrapper
    return decorator


def safe_execute(func: Callable, *args, user_id: Optional[int] = None, **kwargs) -> Any:
    """Safely execute function with error handling"""
    try:
        return func(*args, **kwargs)
    except Exception as e:
        logger.error(f"Error in safe_execute: {str(e)}", user_id)
        return None


async def safe_async_execute(func: Callable, *args, user_id: Optional[int] = None, **kwargs) -> Any:
    """Safely execute async function with error handling"""
    try:
        return await func(*args, **kwargs)
    except Exception as e:
        logger.error(f"Error in safe_async_execute: {str(e)}", user_id)
        return None


class GracefulShutdown:
    """Handle graceful shutdown of the bot"""
    
    def __init__(self, application):
        self.application = application
        self.shutdown_requested = False
        self._setup_signal_handlers()
    
    def _setup_signal_handlers(self):
        """Setup signal handlers for graceful shutdown"""
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
    
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals"""
        logger.info(f"Received signal {signum}, initiating graceful shutdown...")
        self.shutdown_requested = True
        
        # Stop the application
        if self.application and not self.application.running:
            logger.info("Application is not running, exiting...")
            sys.exit(0)
        
        # Schedule shutdown
        import asyncio
        asyncio.create_task(self._shutdown())
    
    async def _shutdown(self):
        """Perform graceful shutdown"""
        try:
            logger.info("Stopping bot application...")
            await self.application.stop()
            logger.info("Bot application stopped successfully")
        except Exception as e:
            logger.error(f"Error during shutdown: {str(e)}")
        finally:
            logger.info("Graceful shutdown completed")
            sys.exit(0)
    
    def is_shutdown_requested(self) -> bool:
        """Check if shutdown was requested"""
        return self.shutdown_requested


def format_currency(amount: Union[Decimal, float, int]) -> str:
    """Format amount as currency string"""
    if isinstance(amount, (int, float)):
        amount = Decimal(str(amount))
    
    # Check if amount is a whole number (no decimal part)
    if amount % 1 == 0:
        # Format without decimal part
        formatted = f"{int(amount):,}".replace(',', ' ')
    else:
        # Format with decimal part
        formatted = f"{amount:,.2f}".replace(',', ' ')
    
    return f"{formatted} {CURRENCY_SYMBOL}"


def format_datetime(dt: datetime, format_str: str = "%d.%m.%Y %H:%M") -> str:
    """Format datetime object as string"""
    return dt.strftime(format_str)


def format_date(dt: datetime, format_str: str = "%d.%m.%Y") -> str:
    """Format date object as string"""
    return dt.strftime(format_str)


def parse_amount(amount_str: str) -> Decimal:
    """Parse amount string to Decimal"""
    try:
        # Remove spaces and currency symbols
        cleaned = amount_str.replace(' ', '').replace(CURRENCY_SYMBOL, '')
        return Decimal(cleaned)
    except (ValueError, TypeError):
        raise ValueError(f"Неверный формат суммы: {amount_str}")


def validate_positive_amount(amount: Union[Decimal, float, int]) -> bool:
    """Validate that amount is positive"""
    if isinstance(amount, (int, float)):
        amount = Decimal(str(amount))
    
    return amount > 0


def truncate_text(text: str, max_length: int = 50) -> str:
    """Truncate text to maximum length"""
    if len(text) <= max_length:
        return text
    return text[:max_length-3] + "..."


def calculate_percentage(part: Union[Decimal, float, int], total: Union[Decimal, float, int]) -> float:
    """Calculate percentage"""
    if total == 0:
        return 0.0
    
    if isinstance(part, (int, float)):
        part = Decimal(str(part))
    if isinstance(total, (int, float)):
        total = Decimal(str(total))
    
    return float((part / total) * 100)


def get_week_dates(date: datetime = None) -> tuple:
    """Get start and end dates of the week for given date"""
    if date is None:
        date = datetime.now()
    
    # Get Monday of the week
    days_since_monday = date.weekday()
    monday = date - datetime.timedelta(days=days_since_monday)
    sunday = monday + datetime.timedelta(days=6)
    
    return monday.date(), sunday.date()


def get_month_dates(year: int = None, month: int = None) -> tuple:
    """Get start and end dates of the month"""
    if year is None or month is None:
        now = datetime.now()
        year = now.year
        month = now.month
    
    start_date = datetime(year, month, 1)
    
    if month == 12:
        end_date = datetime(year + 1, 1, 1)
    else:
        end_date = datetime(year, month + 1, 1)
    
    return start_date.date(), (end_date - datetime.timedelta(days=1)).date()


class AuthManager:
    """User authentication and authorization manager"""
    
    @staticmethod
    def get_user(telegram_id: int) -> Optional[User]:
        """
        Get user by telegram ID.
        
        Args:
            telegram_id (int): Telegram user ID
            
        Returns:
            Optional[User]: User object or None if not found
        """
        from ..services.database import get_session
        
        try:
            with get_session() as session:
                user = session.query(User).filter(
                    User.telegram_id == telegram_id
                ).first()
                # Detach the user from session to avoid session issues
                if user:
                    session.expunge(user)
                return user
        except Exception as e:
            logger.error(f"Error getting user {telegram_id}: {str(e)}")
            return None
    
    @staticmethod
    def normalize_role(role: Optional[str]) -> str:
        """
        Normalize incoming role value to canonical Russian labels.
        
        Args:
            role (Optional[str]): Raw role value (may include legacy English aliases)
        
        Returns:
            str: Normalized role value (админ/бариста)
        
        Raises:
            ValueError: If role is missing or unsupported
        """
        if role is None:
            raise ValueError("Role value is required")
        
        role_value = role.strip().lower()
        if not role_value:
            raise ValueError("Role value is required")
        
        admin_aliases = {
            User.ROLE_ADMIN,
            User.ROLE_ADMIN_LEGACY,
            'администратор',
            'administrator'
        }
        barista_aliases = {
            User.ROLE_BARISTA,
            User.ROLE_BARISTA_LEGACY
        }
        
        if role_value in admin_aliases:
            return User.ROLE_ADMIN
        if role_value in barista_aliases:
            return User.ROLE_BARISTA
        
        raise ValueError(f"Unsupported role value: {role}")
    
    @staticmethod
    def create_user(telegram_id: int, username: str = None, 
                   first_name: str = None, last_name: str = None,
                   role: str = User.ROLE_BARISTA, created_by: int = None) -> Optional[User]:
        """
        Create new user.
        
        Args:
            telegram_id (int): Telegram user ID
            username (str): Telegram username
            first_name (str): User first name
            last_name (str): User last name
            role (str): User role (админ/бариста, legacy английские значения поддерживаются)
            created_by (int): ID of user who created this user
            
        Returns:
            Optional[User]: Created user or None if error
        """
        from ..services.database import get_session
        
        try:
            with get_session() as session:
                # Check if user already exists
                existing_user = session.query(User).filter(
                    User.telegram_id == telegram_id
                ).first()
                
                if existing_user:
                    logger.warning(f"User {telegram_id} already exists")
                    return existing_user
                
                normalized_role = AuthManager.normalize_role(role)
                
                user = User(
                    telegram_id=telegram_id,
                    username=username,
                    first_name=first_name,
                    last_name=last_name,
                    role=normalized_role,
                    status=User.STATUS_PENDING,
                    created_by=created_by
                )
                
                session.add(user)
                session.commit()
                
                logger.info(f"Created user {telegram_id} with role {role}")
                return user
                
        except Exception as e:
            logger.error(f"Error creating user {telegram_id}: {str(e)}")
            return None
    
    @staticmethod
    def activate_user(telegram_id: int) -> bool:
        """
        Activate user account.
        
        Args:
            telegram_id (int): Telegram user ID
            
        Returns:
            bool: True if activated successfully
        """
        from ..services.database import get_session
        
        try:
            with get_session() as session:
                user = session.query(User).filter(
                    User.telegram_id == telegram_id
                ).first()
                
                if not user:
                    logger.warning(f"User {telegram_id} not found for activation")
                    return False
                
                user.status = User.STATUS_ACTIVE
                user.last_activity = datetime.utcnow()
                session.commit()
                
                logger.info(f"Activated user {telegram_id}")
                return True
                
        except Exception as e:
            logger.error(f"Error activating user {telegram_id}: {str(e)}")
            return False
    
    @staticmethod
    def deactivate_user(telegram_id: int) -> bool:
        """
        Deactivate user account.
        
        Args:
            telegram_id (int): Telegram user ID
            
        Returns:
            bool: True if deactivated successfully
        """
        from ..services.database import get_session
        
        try:
            with get_session() as session:
                user = session.query(User).filter(
                    User.telegram_id == telegram_id
                ).first()
                
                if not user:
                    logger.warning(f"User {telegram_id} not found for deactivation")
                    return False
                
                user.status = User.STATUS_INACTIVE
                session.commit()
                
                logger.info(f"Deactivated user {telegram_id}")
                return True
                
        except Exception as e:
            logger.error(f"Error deactivating user {telegram_id}: {str(e)}")
            return False
    
    @staticmethod
    def update_user_activity(telegram_id: int) -> bool:
        """
        Update user last activity timestamp.
        
        Args:
            telegram_id (int): Telegram user ID
            
        Returns:
            bool: True if updated successfully
        """
        from ..services.database import get_session
        
        try:
            with get_session() as session:
                user = session.query(User).filter(
                    User.telegram_id == telegram_id
                ).first()
                
                if user:
                    user.last_activity = datetime.utcnow()
                    session.commit()
                    return True
                return False
                
        except Exception as e:
            logger.error(f"Error updating user activity {telegram_id}: {str(e)}")
            return False
    
    @staticmethod
    def get_all_users() -> list[User]:
        """
        Get all users.
        
        Returns:
            list[User]: List of all users
        """
        from ..services.database import get_session
        
        try:
            with get_session() as session:
                users = session.query(User).all()
                # Detach users from session
                for user in users:
                    session.expunge(user)
                return users
        except Exception as e:
            logger.error(f"Error getting all users: {str(e)}")
            return []
    
    @staticmethod
    def get_users_by_role(role: str) -> list[User]:
        """
        Get users by role.
        
        Args:
            role (str): User role (админ/бариста)
            
        Returns:
            list[User]: List of users with specified role
        """
        from ..services.database import get_session
        
        try:
            normalized_role = AuthManager.normalize_role(role)
        except ValueError:
            logger.error(f"Unsupported role requested: {role}")
            return []
        
        role_values = {normalized_role}
        if normalized_role == User.ROLE_ADMIN:
            role_values.add(User.ROLE_ADMIN_LEGACY)
        else:
            role_values.add(User.ROLE_BARISTA_LEGACY)
        
        try:
            with get_session() as session:
                users = session.query(User).filter(User.role.in_(role_values)).all()
                # Detach users from session
                for user in users:
                    session.expunge(user)
                return users
        except Exception as e:
            logger.error(f"Error getting users by role {role}: {str(e)}")
            return []


def require_auth(required_role: str = None):
    """
    Decorator to require authentication for functions.
    
        Args:
            required_role (str): Required role (админ/бариста), None for any active user
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(self, update, context, *args, **kwargs):
            user_id = update.effective_user.id
            
            # Get user from database
            user = AuthManager.get_user(user_id)
            
            if not user:
                await update.message.reply_text(
                    "❌ Вы не зарегистрированы в системе.\n"
                    "Обратитесь к администратору для получения доступа."
                )
                logger.warning(f"Unauthenticated access attempt from {user_id}")
                return
            
            # Check if user is active
            if user.status != User.STATUS_ACTIVE:
                await update.message.reply_text(
                    "❌ Ваш аккаунт неактивен.\n"
                    "Обратитесь к администратору для активации."
                )
                logger.warning(f"Inactive user {user_id} tried to access {func.__name__}")
                return
            
            # Check role if required
            normalized_required_role = None
            if required_role:
                try:
                    normalized_required_role = AuthManager.normalize_role(required_role)
                except ValueError:
                    normalized_required_role = required_role.strip().lower()
            
            if normalized_required_role == User.ROLE_ADMIN and not user.is_admin():
                await update.message.reply_text(
                    "❌ У вас нет прав администратора для выполнения этого действия."
                )
                logger.warning(f"Non-admin user {user_id} tried to access admin function {func.__name__}")
                return
            
            # Update user activity
            AuthManager.update_user_activity(user_id)
            
            # Add user to context for use in function
            context.user = user
            
            # Call original function
            return await func(self, update, context, *args, **kwargs)
        
        return wrapper
    return decorator
