"""
User management handlers for Romano Bot

This module handles user registration, role management, and user administration
for the Romano Coffee Shop bot with role-based access control.

Author: Romano Bot Team
Version: 1.0.0
"""
from datetime import datetime
from typing import Optional

from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import ContextTypes

from ..models.schema import User
from ..utils.helpers import logger, AuthManager, require_auth
from ..services.barista_session import BaristaSessionManager


class UsersHandler:
    """
    Handle user management operations.
    
    Manages user registration, role assignment, activation/deactivation,
    and user administration for admins.
    """
    
    def __init__(self):
        self.admin_keyboard = ReplyKeyboardMarkup([
            ['👥 Список пользователей', '➕ Добавить пользователя'],
            ['⏳ Ожидающие активации', '🔧 Управление ролями'],
            ['📊 Статистика пользователей', '🔙 Главное меню']
        ], resize_keyboard=True)
        
        self.role_keyboard = ReplyKeyboardMarkup([
            ['👑 Администратор', '☕ Бариста'],
            ['🔙 Назад к пользователям']
        ], resize_keyboard=True)
        
        self.user_management_keyboard = ReplyKeyboardMarkup([
            ['✅ Активировать', '❌ Деактивировать'],
            ['👑 Сделать админом', '☕ Сделать бариста'],
            ['🔙 Назад к пользователям']
        ], resize_keyboard=True)
        
        self.back_to_users_keyboard = ReplyKeyboardMarkup([
            ['🔙 Назад к пользователям']
        ], resize_keyboard=True)
    
    @staticmethod
    def _format_role_value(role: Optional[str]) -> str:
        """
        Convert stored role value to a user-friendly Russian label.
        
        Args:
            role (Optional[str]): Stored role value
        
        Returns:
            str: Readable role string for UI
        """
        if not role:
            return "не указана"
        
        try:
            return AuthManager.normalize_role(role)
        except ValueError:
            return role
    
    async def show_users_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Show users management menu (admin only)"""
        user_id = update.effective_user.id
        
        try:
            logger.info(f"Admin {user_id} opened users menu")
            
            await update.message.reply_text(
                "👥 <b>Управление пользователями</b>\n\n"
                "Выберите действие:",
                reply_markup=self.admin_keyboard,
                parse_mode='HTML'
            )
        except Exception as e:
            logger.error(f"Error showing users menu: {str(e)}", user_id)
            await update.message.reply_text(
                "❌ Произошла ошибка. Попробуйте еще раз."
            )
    
    async def list_users(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """List all users (admin only)"""
        user_id = update.effective_user.id
        
        try:
            logger.info(f"Admin {user_id} requested users list")
            
            users = AuthManager.get_all_users()
            
            if not users:
                await update.message.reply_text(
                    "👥 <b>Список пользователей</b>\n\n"
                    "Пользователи не найдены",
                    reply_markup=self.admin_keyboard,
                    parse_mode='HTML'
                )
                return
            
            message = "👥 <b>Список пользователей</b>\n\n"
            admin_role_values = {User.ROLE_ADMIN, User.ROLE_ADMIN_LEGACY}
            
            for user_obj in users:
                try:
                    role_emoji = "👑" if user_obj.role in admin_role_values else "☕"
                    status_emoji = "✅" if user_obj.status == User.STATUS_ACTIVE else "❌" if user_obj.status == User.STATUS_INACTIVE else "⏳"
                    
                    name = user_obj.first_name or "Неизвестно"
                    if user_obj.last_name:
                        name += f" {user_obj.last_name}"
                    
                    # Safely get created_at
                    created_date = ""
                    try:
                        if user_obj.created_at:
                            created_date = user_obj.created_at.strftime('%d.%m.%Y') if isinstance(user_obj.created_at, datetime) else str(user_obj.created_at)
                    except Exception:
                        created_date = "Неизвестно"
                    
                    role_label = self._format_role_value(user_obj.role)
                    
                    message += f"{role_emoji} <b>{name}</b>\n"
                    message += f"   ID: {user_obj.telegram_id}\n"
                    message += f"   Роль: {role_label}\n"
                    message += f"   Статус: {status_emoji} {user_obj.status}\n"
                    message += f"   Создан: {created_date}\n\n"
                except Exception as e:
                    logger.error(f"Error processing user {user_obj.telegram_id}: {str(e)}")
                    message += f"❌ <b>Ошибка обработки пользователя</b>\n"
                    message += f"   ID: {user_obj.telegram_id}\n\n"
            
            await update.message.reply_text(
                message,
                reply_markup=self.admin_keyboard,
                parse_mode='HTML'
            )
            
        except Exception as e:
            logger.error(f"Error listing users: {str(e)}", user_id)
            await update.message.reply_text(
                "❌ Произошла ошибка при получении списка пользователей."
            )
    
    async def add_user(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Start adding new user (admin only)"""
        user_id = update.effective_user.id
        
        try:
            logger.info(f"Admin {user_id} started adding user")
            
            await update.message.reply_text(
                "➕ <b>Добавление пользователя</b>\n\n"
                "Введите данные в формате:\n"
                "<code>Telegram ID | Имя | Фамилия | Роль</code>\n\n"
                "Пример: <code>123456789 | Иван | Петров | бариста</code>\n"
                "Роли: админ, бариста",
                reply_markup=self.back_to_users_keyboard,
                parse_mode='HTML'
            )
            context.user_data['state'] = 'adding_user'
            
        except Exception as e:
            logger.error(f"Error starting add user: {str(e)}", user_id)
            await update.message.reply_text(
                "❌ Произошла ошибка. Попробуйте еще раз."
            )
    
    async def handle_add_user_data(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle add user data input"""
        user_id = update.effective_user.id
        
        try:
            data = update.message.text.strip()
            
            # Parse format: "Telegram ID | Имя | Фамилия | Роль"
            if '|' not in data:
                raise ValueError("Используйте формат: Telegram ID | Имя | Фамилия | Роль")
            
            parts = [part.strip() for part in data.split('|')]
            if len(parts) != 4:
                raise ValueError("Неверный формат данных")
            
            telegram_id, first_name, last_name, role = parts
            
            # Validate telegram ID
            try:
                telegram_id = int(telegram_id)
            except ValueError:
                raise ValueError("Telegram ID должен быть числом")
            
            # Validate role
            try:
                normalized_role = AuthManager.normalize_role(role)
            except ValueError:
                raise ValueError("Роль должна быть 'админ' или 'бариста'")
            
            # Get admin user for created_by
            admin_user = AuthManager.get_user(user_id)
            created_by = admin_user.id if admin_user else None
            
            # Create user
            new_user = AuthManager.create_user(
                telegram_id=telegram_id,
                first_name=first_name,
                last_name=last_name,
                role=normalized_role,
                created_by=created_by
            )
            
            if new_user:
                await update.message.reply_text(
                    f"✅ <b>Пользователь добавлен!</b>\n\n"
                    f"👤 <b>Имя:</b> {first_name} {last_name}\n"
                    f"🆔 <b>ID:</b> {telegram_id}\n"
                    f"👑 <b>Роль:</b> {normalized_role}\n"
                    f"⏳ <b>Статус:</b> Ожидает активации",
                    reply_markup=self.admin_keyboard,
                    parse_mode='HTML'
                )
                actor_id = admin_user.telegram_id if admin_user else user_id
                logger.info(f"Admin {actor_id} added user {telegram_id}")
            else:
                await update.message.reply_text(
                    "❌ Ошибка при создании пользователя.",
                    reply_markup=self.admin_keyboard
                )
            
            context.user_data.pop('state', None)
            
        except Exception as e:
            await update.message.reply_text(
                f"❌ Ошибка: {str(e)}\n\n"
                "Попробуйте еще раз в правильном формате:\n"
                "<code>Telegram ID | Имя | Фамилия | Роль</code>",
                reply_markup=self.back_to_users_keyboard,
                parse_mode='HTML'
            )
    
    async def manage_user_roles(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Show user role management (admin only)"""
        user_id = update.effective_user.id
        
        try:
            logger.info(f"Admin {user_id} opened role management")
            
            # Get users that can be managed
            users = AuthManager.get_all_users()
            active_users = [u for u in users if u.status == User.STATUS_ACTIVE]
            
            if not active_users:
                await update.message.reply_text(
                    "👥 <b>Управление ролями</b>\n\n"
                    "Нет активных пользователей для управления",
                    reply_markup=self.admin_keyboard,
                    parse_mode='HTML'
                )
                return
            
            message = "👥 <b>Управление ролями</b>\n\n"
            message += "Введите ID пользователя для изменения роли:\n\n"
            
            admin_role_values = {User.ROLE_ADMIN, User.ROLE_ADMIN_LEGACY}
            
            for user_obj in active_users:
                role_emoji = "👑" if user_obj.role in admin_role_values else "☕"
                name = user_obj.first_name or "Неизвестно"
                if user_obj.last_name:
                    name += f" {user_obj.last_name}"
                
                message += f"{role_emoji} <b>{name}</b> (ID: {user_obj.telegram_id})\n"
            
            await update.message.reply_text(
                message,
                reply_markup=self.back_to_users_keyboard,
                parse_mode='HTML'
            )
            context.user_data['state'] = 'selecting_user_for_role'
            
        except Exception as e:
            logger.error(f"Error showing role management: {str(e)}", user_id)
            await update.message.reply_text(
                "❌ Произошла ошибка. Попробуйте еще раз."
            )
    
    async def handle_user_selection(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle user selection for role management"""
        user = context.user
        
        try:
            telegram_id = int(update.message.text.strip())
            
            # Get selected user
            selected_user = AuthManager.get_user(telegram_id)
            if not selected_user:
                await update.message.reply_text(
                    "❌ Пользователь не найден. Попробуйте еще раз:",
                    reply_markup=self.back_to_users_keyboard
                )
                return
            
            # Store selected user
            context.user_data['selected_user_id'] = telegram_id
            
            name = selected_user.first_name or "Неизвестно"
            if selected_user.last_name:
                name += f" {selected_user.last_name}"
            
            current_role = self._format_role_value(selected_user.role)
            
            await update.message.reply_text(
                f"👤 <b>Выбран пользователь:</b> {name}\n"
                f"🆔 <b>ID:</b> {telegram_id}\n"
                f"👑 <b>Текущая роль:</b> {current_role}\n\n"
                "Выберите новую роль:",
                reply_markup=self.role_keyboard,
                parse_mode='HTML'
            )
            context.user_data['state'] = 'selecting_role'
            
        except ValueError:
            await update.message.reply_text(
                "❌ Неверный ID пользователя. Введите числовой ID:",
                reply_markup=self.back_to_users_keyboard
            )
        except Exception as e:
            logger.error(f"Error handling user selection: {str(e)}", user.telegram_id)
            await update.message.reply_text(
                "❌ Произошла ошибка. Попробуйте еще раз."
            )
    
    async def handle_role_selection(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle role selection for user"""
        user = context.user
        
        try:
            role_text = update.message.text
            selected_user_id = context.user_data.get('selected_user_id')
            
            if not selected_user_id:
                await update.message.reply_text(
                    "❌ Ошибка: пользователь не выбран.",
                    reply_markup=self.admin_keyboard
                )
                return
            
            # Map role text to role constant
            if "Администратор" in role_text:
                new_role = User.ROLE_ADMIN
            elif "Бариста" in role_text:
                new_role = User.ROLE_BARISTA
            else:
                raise ValueError("Неверная роль")
            
            # Update user role
            from ..services.database import get_session
            with get_session() as session:
                user_to_update = session.query(User).filter(
                    User.telegram_id == selected_user_id
                ).first()
                
                if user_to_update:
                    old_role = user_to_update.role
                    user_to_update.role = new_role
                    session.commit()
                    
                    old_role_label = self._format_role_value(old_role)
                    new_role_label = self._format_role_value(new_role)
                    
                    name = user_to_update.first_name or "Неизвестно"
                    if user_to_update.last_name:
                        name += f" {user_to_update.last_name}"
                    
                    await update.message.reply_text(
                        f"✅ <b>Роль изменена!</b>\n\n"
                        f"👤 <b>Пользователь:</b> {name}\n"
                        f"👑 <b>Старая роль:</b> {old_role_label}\n"
                        f"👑 <b>Новая роль:</b> {new_role_label}",
                        reply_markup=self.admin_keyboard,
                        parse_mode='HTML'
                    )
                    logger.info(
                        f"Admin {user.telegram_id} changed role for user "
                        f"{selected_user_id} from {old_role_label} to {new_role_label}"
                    )
                else:
                    await update.message.reply_text(
                        "❌ Пользователь не найден.",
                        reply_markup=self.admin_keyboard
                    )
            
            context.user_data.pop('selected_user_id', None)
            context.user_data.pop('state', None)
            
        except Exception as e:
            logger.error(f"Error handling role selection: {str(e)}", user.telegram_id)
            await update.message.reply_text(
                f"❌ Ошибка: {str(e)}",
                reply_markup=self.admin_keyboard
            )
    
    @require_auth('админ')
    async def user_statistics(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Show user statistics (admin only)"""
        user = context.user
        
        try:
            logger.info(f"Admin {user.telegram_id} requested user statistics")
            
            users = AuthManager.get_all_users()
            
            # Calculate statistics
            total_users = len(users)
            active_users = len([u for u in users if u.status == User.STATUS_ACTIVE])
            inactive_users = len([u for u in users if u.status == User.STATUS_INACTIVE])
            pending_users = len([u for u in users if u.status == User.STATUS_PENDING])
            admin_users = len([u for u in users if u.role in {User.ROLE_ADMIN, User.ROLE_ADMIN_LEGACY}])
            barista_users = len([u for u in users if u.role in {User.ROLE_BARISTA, User.ROLE_BARISTA_LEGACY}])
            
            message = "📊 <b>Статистика пользователей</b>\n\n"
            message += f"👥 <b>Всего пользователей:</b> {total_users}\n"
            message += f"✅ <b>Активных:</b> {active_users}\n"
            message += f"❌ <b>Неактивных:</b> {inactive_users}\n"
            message += f"⏳ <b>Ожидающих активации:</b> {pending_users}\n\n"
            message += f"👑 <b>Администраторов:</b> {admin_users}\n"
            message += f"☕ <b>Бариста:</b> {barista_users}\n\n"
            
            # Recent activity
            recent_users = [u for u in users if u.last_activity and 
                          (datetime.utcnow() - u.last_activity).days <= 7]
            message += f"🕐 <b>Активны за неделю:</b> {len(recent_users)}"
            
            await update.message.reply_text(
                message,
                reply_markup=self.admin_keyboard,
                parse_mode='HTML'
            )
            
        except Exception as e:
            logger.error(f"Error showing user statistics: {str(e)}", user.telegram_id)
            await update.message.reply_text(
                "❌ Произошла ошибка при получении статистики."
            )
    
    async def list_pending_users(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """
        Show list of users waiting for activation (admin only).
        
        Args:
            update (Update): Telegram update object
            context (ContextTypes.DEFAULT_TYPE): Bot context
        """
        user_id = update.effective_user.id
        
        try:
            logger.info(f"Admin {user_id} requested pending users list")
            
            users = AuthManager.get_all_users()
            pending_users = [u for u in users if u.status == User.STATUS_PENDING]
            
            if not pending_users:
                await update.message.reply_text(
                    "⏳ <b>Ожидающие активации</b>\n\n"
                    "Нет пользователей, ожидающих активации.",
                    reply_markup=self.admin_keyboard,
                    parse_mode='HTML'
                )
                return
            
            message = "⏳ <b>Пользователи, ожидающие активации</b>\n\n"
            message += "Введите ID пользователя для активации:\n\n"
            
            admin_role_values = {User.ROLE_ADMIN, User.ROLE_ADMIN_LEGACY}
            
            for user_obj in pending_users:
                role_emoji = "👑" if user_obj.role in admin_role_values else "☕"
                name = user_obj.first_name or "Неизвестно"
                if user_obj.last_name:
                    name += f" {user_obj.last_name}"
                
                role_label = self._format_role_value(user_obj.role)
                
                # Safely get created_at
                created_date = ""
                try:
                    if user_obj.created_at:
                        created_date = user_obj.created_at.strftime('%d.%m.%Y') if isinstance(user_obj.created_at, datetime) else str(user_obj.created_at)
                except Exception:
                    created_date = "Неизвестно"
                
                message += f"{role_emoji} <b>{name}</b>\n"
                message += f"   ID: {user_obj.telegram_id}\n"
                message += f"   Роль: {role_label}\n"
                message += f"   Создан: {created_date}\n\n"
            
            await update.message.reply_text(
                message,
                reply_markup=self.user_management_keyboard,
                parse_mode='HTML'
            )
            context.user_data['state'] = 'selecting_user_for_activation'
            
        except Exception as e:
            logger.error(f"Error listing pending users: {str(e)}", user_id)
            await update.message.reply_text(
                "❌ Произошла ошибка при получении списка пользователей."
            )
    
    async def handle_user_activation_selection(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """
        Handle user selection for activation/deactivation.
        
        Args:
            update (Update): Telegram update object
            context (ContextTypes.DEFAULT_TYPE): Bot context
        """
        user = context.user
        
        try:
            telegram_id = int(update.message.text.strip())
            
            # Get selected user
            selected_user = AuthManager.get_user(telegram_id)
            if not selected_user:
                await update.message.reply_text(
                    "❌ Пользователь не найден. Попробуйте еще раз:",
                    reply_markup=self.user_management_keyboard
                )
                return
            
            # Store selected user
            context.user_data['selected_user_id'] = telegram_id
            
            name = selected_user.first_name or "Неизвестно"
            if selected_user.last_name:
                name += f" {selected_user.last_name}"
            
            role_label = self._format_role_value(selected_user.role)
            status_emoji = "✅" if selected_user.status == User.STATUS_ACTIVE else "❌" if selected_user.status == User.STATUS_INACTIVE else "⏳"
            
            await update.message.reply_text(
                f"👤 <b>Выбран пользователь:</b> {name}\n"
                f"🆔 <b>ID:</b> {telegram_id}\n"
                f"👑 <b>Роль:</b> {role_label}\n"
                f"📊 <b>Статус:</b> {status_emoji} {selected_user.status}\n\n"
                "Выберите действие:",
                reply_markup=self.user_management_keyboard,
                parse_mode='HTML'
            )
            context.user_data['state'] = 'managing_user_status'
            
        except ValueError:
            await update.message.reply_text(
                "❌ Неверный ID пользователя. Введите числовой ID:",
                reply_markup=self.user_management_keyboard
            )
        except Exception as e:
            logger.error(f"Error handling user activation selection: {str(e)}", user.telegram_id)
            await update.message.reply_text(
                "❌ Произошла ошибка. Попробуйте еще раз."
            )
    
    async def activate_user(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """
        Activate selected user (admin only).
        
        Args:
            update (Update): Telegram update object
            context (ContextTypes.DEFAULT_TYPE): Bot context
        """
        user = context.user
        
        try:
            selected_user_id = context.user_data.get('selected_user_id')
            
            if not selected_user_id:
                # Try to get from message if user typed ID directly
                try:
                    selected_user_id = int(update.message.text.strip())
                    context.user_data['selected_user_id'] = selected_user_id
                except ValueError:
                    # Show list of pending users if no user selected
                    await update.message.reply_text(
                        "⚠️ <b>Пользователь не выбран</b>\n\n"
                        "Сначала введите ID пользователя из списка выше, "
                        "затем нажмите кнопку '✅ Активировать'.",
                        reply_markup=self.user_management_keyboard,
                        parse_mode='HTML'
                    )
                    # Show list again
                    await self.list_pending_users(update, context)
                    return
            
            # Verify user exists before activation
            selected_user = AuthManager.get_user(selected_user_id)
            if not selected_user:
                await update.message.reply_text(
                    f"❌ Пользователь с ID {selected_user_id} не найден.",
                    reply_markup=self.admin_keyboard
                )
                context.user_data.pop('selected_user_id', None)
                context.user_data.pop('state', None)
                return
            
            # Check if user is already active
            if selected_user.status == User.STATUS_ACTIVE:
                name = selected_user.first_name or "Неизвестно"
                if selected_user.last_name:
                    name += f" {selected_user.last_name}"
                await update.message.reply_text(
                    f"ℹ️ <b>Пользователь уже активирован</b>\n\n"
                    f"👤 <b>Имя:</b> {name}\n"
                    f"🆔 <b>ID:</b> {selected_user_id}\n"
                    f"📊 <b>Статус:</b> ✅ Активен",
                    reply_markup=self.admin_keyboard,
                    parse_mode='HTML'
                )
                context.user_data.pop('selected_user_id', None)
                context.user_data.pop('state', None)
                return
            
            # Activate user
            success = AuthManager.activate_user(selected_user_id)
            
            if success:
                # Refresh user data after activation
                selected_user = AuthManager.get_user(selected_user_id)
                name = selected_user.first_name or "Неизвестно"
                if selected_user.last_name:
                    name += f" {selected_user.last_name}"
                
                await update.message.reply_text(
                    f"✅ <b>Пользователь активирован!</b>\n\n"
                    f"👤 <b>Имя:</b> {name}\n"
                    f"🆔 <b>ID:</b> {selected_user_id}\n"
                    f"📊 <b>Статус:</b> ✅ Активен\n\n"
                    f"Теперь пользователь может использовать бота.",
                    reply_markup=self.admin_keyboard,
                    parse_mode='HTML'
                )
                logger.info(
                    f"Admin {user.telegram_id} activated user {selected_user_id}"
                )
            else:
                await update.message.reply_text(
                    "❌ Ошибка при активации пользователя.\n"
                    "Попробуйте еще раз или обратитесь к администратору.",
                    reply_markup=self.admin_keyboard
                )
                logger.error(
                    f"Failed to activate user {selected_user_id} by admin {user.telegram_id}"
                )
            
            context.user_data.pop('selected_user_id', None)
            context.user_data.pop('state', None)
            
        except Exception as e:
            logger.error(f"Error activating user: {str(e)}", user.telegram_id)
            await update.message.reply_text(
                f"❌ Ошибка: {str(e)}",
                reply_markup=self.admin_keyboard
            )
    
    async def deactivate_user(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """
        Deactivate selected user (admin only).
        
        Args:
            update (Update): Telegram update object
            context (ContextTypes.DEFAULT_TYPE): Bot context
        """
        user = context.user
        
        try:
            selected_user_id = context.user_data.get('selected_user_id')
            
            if not selected_user_id:
                # Try to get from message if user typed ID directly
                try:
                    selected_user_id = int(update.message.text.strip())
                    context.user_data['selected_user_id'] = selected_user_id
                except ValueError:
                    # Show list of all users for deactivation
                    await self.list_users(update, context)
                    await update.message.reply_text(
                        "Введите ID пользователя для деактивации:",
                        reply_markup=self.user_management_keyboard
                    )
                    context.user_data['state'] = 'selecting_user_for_activation'
                    return
            
            # Deactivate user
            success = AuthManager.deactivate_user(selected_user_id)
            
            if success:
                selected_user = AuthManager.get_user(selected_user_id)
                name = selected_user.first_name or "Неизвестно"
                if selected_user.last_name:
                    name += f" {selected_user.last_name}"
                
                await update.message.reply_text(
                    f"❌ <b>Пользователь деактивирован!</b>\n\n"
                    f"👤 <b>Имя:</b> {name}\n"
                    f"🆔 <b>ID:</b> {selected_user_id}\n"
                    f"📊 <b>Статус:</b> ❌ Неактивен",
                    reply_markup=self.admin_keyboard,
                    parse_mode='HTML'
                )
                logger.info(
                    f"Admin {user.telegram_id} deactivated user {selected_user_id}"
                )
            else:
                await update.message.reply_text(
                    "❌ Ошибка при деактивации пользователя.\n"
                    "Пользователь не найден.",
                    reply_markup=self.admin_keyboard
                )
            
            context.user_data.pop('selected_user_id', None)
            context.user_data.pop('state', None)
            
        except Exception as e:
            logger.error(f"Error deactivating user: {str(e)}", user.telegram_id)
            await update.message.reply_text(
                f"❌ Ошибка: {str(e)}",
                reply_markup=self.admin_keyboard
            )
    
    async def register_user(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Register new user (self-registration)"""
        user_id = update.effective_user.id
        
        try:
            logger.info(f"User {user_id} attempted self-registration")
            
            # Check if user already exists
            existing_user = AuthManager.get_user(user_id)
            if existing_user:
                if existing_user.status == User.STATUS_ACTIVE:
                    await update.message.reply_text(
                        "✅ Вы уже зарегистрированы и активны в системе!"
                    )
                elif existing_user.status == User.STATUS_PENDING:
                    await update.message.reply_text(
                        "⏳ Ваша регистрация ожидает подтверждения администратора."
                    )
                else:
                    await update.message.reply_text(
                        "❌ Ваш аккаунт деактивирован. Обратитесь к администратору."
                    )
                return
            
            # Create new user as barista by default
            new_user = AuthManager.create_user(
                telegram_id=user_id,
                username=update.effective_user.username,
                first_name=update.effective_user.first_name,
                last_name=update.effective_user.last_name,
                role=User.ROLE_BARISTA
            )
            
            if new_user:
                await update.message.reply_text(
                    "✅ <b>Регистрация успешна!</b>\n\n"
                    "Ваш аккаунт создан и ожидает активации администратором.\n"
                    "После активации вы сможете использовать бота.",
                    parse_mode='HTML'
                )
                logger.info(f"User {user_id} registered successfully")
            else:
                await update.message.reply_text(
                    "❌ Ошибка при регистрации. Попробуйте еще раз."
                )
                
        except Exception as e:
            logger.error(f"Error in user registration: {str(e)}", user_id)
            await update.message.reply_text(
                "❌ Произошла ошибка при регистрации."
            )
    
    async def switch_barista(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """
        Показать меню выбора активного бариста.
        
        Позволяет выбрать активного бариста из списка всех активных бариста.
        Все последующие операции будут привязаны к выбранному бариста.
        
        Args:
            update (Update): Telegram update object
            context (ContextTypes.DEFAULT_TYPE): Bot context
        """
        user_id = update.effective_user.id
        
        try:
            logger.info(f"User {user_id} opened barista switch menu")
            
            # Получить список всех активных бариста
            baristas = BaristaSessionManager.get_all_active_baristas()
            
            if not baristas:
                await update.message.reply_text(
                    "⚠️ <b>Нет активных бариста</b>\n\n"
                    "В системе нет активных бариста для выбора.\n"
                    "Обратитесь к администратору для добавления бариста.",
                    parse_mode='HTML'
                )
                return
            
            # Получить текущего активного бариста
            current_barista = BaristaSessionManager.get_active_barista(context)
            current_barista_id = current_barista.telegram_id if current_barista else None
            
            # Создать клавиатуру с кнопками бариста
            barista_buttons = []
            for barista in baristas:
                name = BaristaSessionManager.format_barista_name(barista)
                # Добавить индикатор текущего активного бариста
                indicator = "✅ " if current_barista_id == barista.telegram_id else "☕ "
                barista_buttons.append([f"{indicator}{name}"])
            
            barista_buttons.append(['🔙 Главное меню'])
            
            barista_keyboard = ReplyKeyboardMarkup(barista_buttons, resize_keyboard=True)
            
            # Сообщение с инструкцией
            message = "👤 <b>Выбор активного бариста</b>\n\n"
            if current_barista:
                current_name = BaristaSessionManager.format_barista_name(current_barista)
                message += f"✅ <b>Текущий активный бариста:</b> {current_name}\n\n"
            else:
                message += "⚠️ <b>Активный бариста не выбран</b>\n\n"
            
            message += "Выберите бариста из списка:\n\n"
            for barista in baristas:
                name = BaristaSessionManager.format_barista_name(barista)
                message += f"☕ {name}\n"
            
            await update.message.reply_text(
                message,
                reply_markup=barista_keyboard,
                parse_mode='HTML'
            )
            
            # Установить состояние выбора бариста
            context.user_data['state'] = 'selecting_barista'
            
        except Exception as e:
            logger.error(f"Error showing barista switch menu: {str(e)}", user_id)
            await update.message.reply_text(
                "❌ Произошла ошибка. Попробуйте еще раз."
            )
    
    async def handle_barista_selection(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """
        Обработать выбор бариста из списка.
        
        Args:
            update (Update): Telegram update object
            context (ContextTypes.DEFAULT_TYPE): Bot context
        """
        user_id = update.effective_user.id
        
        try:
            selected_text = update.message.text.strip()
            
            # Убрать индикаторы из текста
            selected_text = selected_text.replace("✅ ", "").replace("☕ ", "").strip()
            
            # Найти бариста по имени
            baristas = BaristaSessionManager.get_all_active_baristas()
            selected_barista = None
            
            for barista in baristas:
                barista_name = BaristaSessionManager.format_barista_name(barista)
                if barista_name == selected_text:
                    selected_barista = barista
                    break
            
            if not selected_barista:
                await update.message.reply_text(
                    "❌ Бариста не найден. Пожалуйста, выберите из списка:",
                    reply_markup=self._get_barista_keyboard(context)
                )
                return
            
            # Установить выбранного бариста как активного
            success = BaristaSessionManager.set_active_barista(
                selected_barista.telegram_id,
                context
            )
            
            if success:
                barista_name = BaristaSessionManager.format_barista_name(selected_barista)
                await update.message.reply_text(
                    f"✅ <b>Активный бариста изменен!</b>\n\n"
                    f"👤 <b>Выбранный бариста:</b> {barista_name}\n\n"
                    f"Все последующие операции будут привязаны к этому бариста.",
                    parse_mode='HTML'
                )
                logger.info(f"User {user_id} switched active barista to {selected_barista.telegram_id}")
            else:
                await update.message.reply_text(
                    "❌ Ошибка при установке активного бариста.\n"
                    "Попробуйте еще раз.",
                    reply_markup=self._get_barista_keyboard(context)
                )
            
            # Очистить состояние
            context.user_data.pop('state', None)
            
        except Exception as e:
            logger.error(f"Error handling barista selection: {str(e)}", user_id)
            await update.message.reply_text(
                "❌ Произошла ошибка. Попробуйте еще раз."
            )
    
    def _get_barista_keyboard(self, context: ContextTypes.DEFAULT_TYPE) -> ReplyKeyboardMarkup:
        """
        Получить клавиатуру выбора бариста.
        
        Args:
            context (ContextTypes.DEFAULT_TYPE): Bot context
            
        Returns:
            ReplyKeyboardMarkup: Клавиатура с кнопками бариста
        """
        baristas = BaristaSessionManager.get_all_active_baristas()
        current_barista = BaristaSessionManager.get_active_barista(context)
        current_barista_id = current_barista.telegram_id if current_barista else None
        
        barista_buttons = []
        for barista in baristas:
            name = BaristaSessionManager.format_barista_name(barista)
            indicator = "✅ " if current_barista_id == barista.telegram_id else "☕ "
            barista_buttons.append([f"{indicator}{name}"])
        
        barista_buttons.append(['🔙 Главное меню'])
        
        return ReplyKeyboardMarkup(barista_buttons, resize_keyboard=True)
