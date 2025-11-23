"""
Main entry point for Romano Bot

This module contains the main application logic for the Romano Coffee Shop
Telegram bot. It handles user interactions, command routing, and error management.

Author: Romano Bot Team
Version: 1.0.0
"""
import sys
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import (
    Application, 
    CommandHandler, 
    MessageHandler, 
    filters, 
    ContextTypes
)

try:
    from .config import BOT_TOKEN, ADMIN_IDS, validate_config
    from .services.database import init_database
    from .handlers.sales import SalesHandler
    from .handlers.expenses import ExpensesHandler
    from .handlers.reports import ReportsHandler
    from .handlers.balance import BalanceHandler
    from .handlers.users import UsersHandler
    from .handlers.shifts import ShiftsHandler
    from .utils.helpers import logger, GracefulShutdown, AuthManager, FileLock
    from .models.schema import User, Shift  # Import Shift to ensure it's registered in Base.metadata
    from .services.barista_session import BaristaSessionManager
    from .services.shift_manager import ShiftManager
except ImportError:
    # Fallback for direct execution
    from config import BOT_TOKEN, ADMIN_IDS, validate_config
    from services.database import init_database
    from handlers.sales import SalesHandler
    from handlers.expenses import ExpensesHandler
    from handlers.reports import ReportsHandler
    from handlers.balance import BalanceHandler
    from handlers.users import UsersHandler
    from handlers.shifts import ShiftsHandler
    from utils.helpers import logger, GracefulShutdown, AuthManager, FileLock
    from models.schema import User, Shift  # Import Shift to ensure it's registered in Base.metadata
    from services.shift_manager import ShiftManager

# Initialize handlers
sales_handler = SalesHandler()
expenses_handler = ExpensesHandler()
reports_handler = ReportsHandler()
balance_handler = BalanceHandler()
users_handler = UsersHandler()
shifts_handler = ShiftsHandler()

# Main menu keyboard (will be dynamically generated with active barista info)
def get_main_keyboard(show_barista_switch: bool = True, context: ContextTypes.DEFAULT_TYPE = None) -> ReplyKeyboardMarkup:
    """
    Получить главное меню с учетом активного бариста и статуса смены.
    
    Args:
        show_barista_switch (bool): Показывать ли кнопку переключения бариста
        context (ContextTypes.DEFAULT_TYPE, optional): Bot context для проверки статуса смены
        
    Returns:
        ReplyKeyboardMarkup: Клавиатура главного меню
    """
    buttons = [
        ['💰 Продажа', '💸 Расходы'],
        ['📊 Отчеты', '💰 Баланс']
    ]
    
    # Добавить кнопки смены в зависимости от статуса
    is_shift_open = ShiftManager.is_shift_open() if context is None else False
    # Если context передан, можно проверить статус смены
    # Но для простоты используем статическую проверку
    try:
        is_shift_open = ShiftManager.is_shift_open()
    except Exception:
        is_shift_open = False
    
    if is_shift_open:
        buttons.append(['🔴 Закрыть смену'])
    else:
        buttons.append(['🟢 Открыть смену'])
    
    if show_barista_switch:
        buttons.append(['👤 Переключить бариста'])
    
    buttons.append(['👥 Пользователи', 'ℹ️ Помощь'])
    
    return ReplyKeyboardMarkup(buttons, resize_keyboard=True)

# Registration keyboard
REGISTRATION_KEYBOARD = ReplyKeyboardMarkup([
    ['📝 Зарегистрироваться', 'ℹ️ Помощь']
], resize_keyboard=True)


def is_admin(user_id: int) -> bool:
    """
    Check if user is admin.
    
    Args:
        user_id (int): Telegram user ID to check
        
    Returns:
        bool: True if user is admin, False otherwise
    """
    return user_id in ADMIN_IDS


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle /start command.
    
    Welcomes the user and shows appropriate menu based on their authorization status.
    Handles both registered and unregistered users.
    
    Args:
        update (Update): Telegram update object
        context (ContextTypes.DEFAULT_TYPE): Bot context
    """
    # Ignore messages from groups and supergroups
    chat_type = update.effective_chat.type
    if chat_type in ["group", "supergroup"]:
        return
    
    user_id = update.effective_user.id
    
    try:
        logger.info(f"User {user_id} started the bot")
        
        # Check if user exists in database
        user = AuthManager.get_user(user_id)
        
        if not user:
            # User not registered
            await update.message.reply_text(
                "☕ <b>Добро пожаловать в Romano Bot!</b>\n\n"
                "Это бот для управления кофейней Romano.uz\n\n"
                "Для использования бота необходимо зарегистрироваться.\n"
                "Нажмите кнопку ниже для регистрации:",
                reply_markup=REGISTRATION_KEYBOARD,
                parse_mode='HTML'
            )
            logger.info(f"Unregistered user {user_id} started the bot")
            return
        
        # Check user status
        if user.status == User.STATUS_PENDING:
            await update.message.reply_text(
                "⏳ <b>Ваш аккаунт ожидает активации</b>\n\n"
                "Администратор должен активировать ваш аккаунт.\n"
                "После активации вы сможете использовать бота.",
                parse_mode='HTML'
            )
            return
        
        if user.status == User.STATUS_INACTIVE:
            await update.message.reply_text(
                "❌ <b>Ваш аккаунт деактивирован</b>\n\n"
                "Обратитесь к администратору для активации аккаунта.",
                parse_mode='HTML'
            )
            return
        
        # User is active, show appropriate menu
        role_text = "Администратор" if user.is_admin() else "Бариста"
        name = user.first_name or "Пользователь"
        
        # Проверить наличие активного бариста (для бариста обязательно)
        active_barista = BaristaSessionManager.get_active_barista(context)
        active_barista_message = ""
        
        if user.is_barista():
            if not active_barista:
                # Для бариста нужно выбрать активного бариста перед началом работы
                baristas = BaristaSessionManager.get_all_active_baristas()
                
                if not baristas:
                    await update.message.reply_text(
                        "⚠️ <b>Нет активных бариста</b>\n\n"
                        "В системе нет активных бариста.\n"
                        "Обратитесь к администратору.",
                        parse_mode='HTML'
                    )
                    return
                
                # Показать меню выбора бариста
                await users_handler.switch_barista(update, context)
                return
            else:
                # Показать информацию об активном бариста
                barista_name = BaristaSessionManager.format_barista_name(active_barista)
                active_barista_message = f"\n👤 <b>Активный бариста:</b> {barista_name}\n"
        
        # Сформировать приветственное сообщение
        welcome_message = (
            f"☕ <b>Добро пожаловать, {name}!</b>\n\n"
            f"Роль: {role_text}"
            f"{active_barista_message}\n"
            f"Это бот для управления кофейней Romano.uz\n\n"
            "Выберите раздел для работы:"
        )
        
        # Получить главное меню (для бариста показывать кнопку переключения)
        main_keyboard = get_main_keyboard(show_barista_switch=user.is_barista() or user.is_admin())
        
        await update.message.reply_text(
            welcome_message,
            reply_markup=main_keyboard,
            parse_mode='HTML'
        )
        
        # Update user activity
        AuthManager.update_user_activity(user_id)
        logger.info(f"Successfully started bot for user {user_id} (role: {user.role})")
        
    except Exception as e:
        logger.error(f"Error in start command: {str(e)}", user_id)
        await update.message.reply_text(
            "❌ Произошла ошибка. Попробуйте еще раз."
        )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle /help command.
    
    Shows help information about bot usage and available commands.
    
    Args:
        update (Update): Telegram update object
        context (ContextTypes.DEFAULT_TYPE): Bot context
    """
    # Ignore messages from groups and supergroups
    chat_type = update.effective_chat.type
    if chat_type in ["group", "supergroup"]:
        return
    
    user_id = update.effective_user.id
    
    try:
        logger.info(f"User {user_id} requested help")
        
        help_text = """
ℹ️ <b>Помощь по использованию бота</b>

<b>Основные разделы:</b>
💰 <b>Продажа</b> - добавление и просмотр продаж
💸 <b>Расходы</b> - управление расходами
📊 <b>Отчеты</b> - генерация отчетов и аналитика
💰 <b>Баланс</b> - управление балансом

<b>Формат добавления продажи:</b>
<code>Название товара | Количество | Цена за единицу | Способ оплаты</code>

<b>Формат добавления расхода:</b>
<code>Категория | Описание | Сумма | Способ оплаты</code>

<b>Способы оплаты:</b>
• наличные
• карта

<b>Поддержка:</b>
Если у вас есть вопросы, обратитесь к администратору.
        """
        
        await update.message.reply_text(help_text, parse_mode='HTML')
        logger.info(f"Help sent to user {user_id}")
        
    except Exception as e:
        logger.error(f"Error in help command: {str(e)}", user_id)
        await update.message.reply_text(
            "❌ Произошла ошибка. Попробуйте еще раз."
        )


async def get_chat_id(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle /get_chat_id command.
    
    Shows the current chat ID (useful for getting group chat ID).
    Works in both private chats and groups.
    
    Args:
        update (Update): Telegram update object
        context (ContextTypes.DEFAULT_TYPE): Bot context
    """
    user_id = update.effective_user.id
    
    try:
        chat = update.effective_chat
        chat_id = chat.id
        chat_type = chat.type
        
        # Determine chat type display name
        type_names = {
            'private': 'Личный чат',
            'group': 'Группа',
            'supergroup': 'Супергруппа',
            'channel': 'Канал'
        }
        chat_type_display = type_names.get(chat_type, chat_type)
        
        # Get chat title/username if available
        chat_title = ""
        if chat.title:
            chat_title = f"\n📝 <b>Название:</b> {chat.title}"
        elif chat.username:
            chat_title = f"\n👤 <b>Username:</b> @{chat.username}"
        
        # Check if user is admin and if this is a group/supergroup
        is_group = chat_type in ('group', 'supergroup')
        is_admin_user = is_admin(user_id)
        
        # Import current GROUP_CHAT_ID to check
        from .config import GROUP_CHAT_ID
        
        message = (
            f"🆔 <b>Информация о чате</b>\n\n"
            f"💬 <b>Тип чата:</b> {chat_type_display}\n"
            f"🔢 <b>Chat ID:</b> <code>{chat_id}</code>{chat_title}\n\n"
        )
        
        # Add instructions for groups
        if is_group:
            if GROUP_CHAT_ID and str(chat_id) == str(GROUP_CHAT_ID):
                message += "✅ <b>Этот Chat ID уже настроен для уведомлений!</b>\n\n"
            elif is_admin_user:
                message += (
                    f"📌 <b>Для настройки уведомлений:</b>\n"
                    f"Отправьте команду <code>/set_group_chat_id</code> в этой группе,\n"
                    f"чтобы автоматически установить этот Chat ID для уведомлений.\n\n"
                )
            else:
                message += (
                    f"📋 Скопируйте Chat ID выше и передайте администратору\n"
                    f"для настройки уведомлений в группу.\n\n"
                )
        else:
            message += "📋 Скопируйте Chat ID выше для использования в конфигурации.\n\n"
        
        if not GROUP_CHAT_ID:
            message += "⚠️ <b>GROUP_CHAT_ID не настроен!</b> Уведомления не отправляются."
        
        await update.message.reply_text(message, parse_mode='HTML')
        logger.info(f"User {user_id} requested chat ID: {chat_id} (type: {chat_type})")
        
    except Exception as e:
        logger.error(f"Error in get_chat_id command: {str(e)}", user_id)
        await update.message.reply_text(
            "❌ Произошла ошибка при получении Chat ID. Попробуйте еще раз."
        )


async def set_group_chat_id(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle /set_group_chat_id command (admin only).
    
    Sets the GROUP_CHAT_ID for notifications from the current chat.
    Works only in groups/supergroups and only for admins.
    
    Args:
        update (Update): Telegram update object
        context (ContextTypes.DEFAULT_TYPE): Bot context
    """
    user_id = update.effective_user.id
    
    try:
        # Check if user is admin
        if not is_admin(user_id):
            await update.message.reply_text(
                "❌ Эта команда доступна только администраторам."
            )
            return
        
        chat = update.effective_chat
        chat_id = chat.id
        chat_type = chat.type
        
        # Check if this is a group or supergroup
        if chat_type not in ('group', 'supergroup'):
            await update.message.reply_text(
                "❌ Эта команда работает только в группах и супергруппах.\n\n"
                "Используйте команду <code>/get_chat_id</code> в группе для получения Chat ID.",
                parse_mode='HTML'
            )
            return
        
        # Read or create .env file (in project root)
        import os
        # Get project root directory (parent of romano_bot directory)
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        env_file_path = os.path.join(project_root, '.env')
        
        # Read existing .env file if it exists
        env_vars = {}
        if os.path.exists(env_file_path):
            with open(env_file_path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#') and '=' in line:
                        key, value = line.split('=', 1)
                        env_vars[key.strip()] = value.strip()
        
        # Update GROUP_CHAT_ID
        env_vars['GROUP_CHAT_ID'] = str(chat_id)
        
        # Write back to .env file
        with open(env_file_path, 'w', encoding='utf-8') as f:
            for key, value in env_vars.items():
                f.write(f"{key}={value}\n")
        
        chat_title = f" ({chat.title})" if chat.title else ""
        
        message = (
            f"✅ <b>GROUP_CHAT_ID успешно установлен!</b>\n\n"
            f"🔢 <b>Chat ID:</b> <code>{chat_id}</code>{chat_title}\n\n"
            f"📝 Настройка сохранена в файл <code>.env</code>\n\n"
            f"⚠️ <b>Важно:</b> Перезапустите бота, чтобы изменения вступили в силу.\n"
            f"Используйте команду <code>python stop_bot.py</code>, затем <code>python run_bot.py</code>"
        )
        
        await update.message.reply_text(message, parse_mode='HTML')
        logger.info(f"Admin {user_id} set GROUP_CHAT_ID to {chat_id} in {chat_type}")
        
    except Exception as e:
        logger.error(f"Error in set_group_chat_id command: {str(e)}", user_id)
        await update.message.reply_text(
            f"❌ Произошла ошибка при установке GROUP_CHAT_ID: {str(e)}\n\n"
            "Попробуйте установить GROUP_CHAT_ID вручную через переменную окружения или файл .env"
        )


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle text messages from users.
    
    Routes messages to appropriate handlers based on user state and message content.
    Handles both state-based responses and menu selections with role-based access control.
    
    Args:
        update (Update): Telegram update object
        context (ContextTypes.DEFAULT_TYPE): Bot context
    """
    # Ignore messages from groups and supergroups
    chat_type = update.effective_chat.type
    if chat_type in ["group", "supergroup"]:
        return
    
    user_id = update.effective_user.id
    
    try:
        logger.info(f"User {user_id} sent message: {update.message.text}")
        
        # Handle /get_chat_id, /chatid, and /set_group_chat_id commands as fallback
        text = update.message.text
        if text in ['/get_chat_id', '/chatid']:
            await get_chat_id(update, context)
            return
        elif text == '/set_group_chat_id':
            await set_group_chat_id(update, context)
            return
        
        # Get user from database
        user = AuthManager.get_user(user_id)
        
        # Handle unregistered users
        if not user:
            if update.message.text == "📝 Зарегистрироваться":
                await users_handler.register_user(update, context)
            elif update.message.text == "ℹ️ Помощь":
                await help_command(update, context)
            else:
                await update.message.reply_text(
                    "❌ Вы не зарегистрированы в системе.\n"
                    "Нажмите '📝 Зарегистрироваться' для создания аккаунта.",
                    reply_markup=REGISTRATION_KEYBOARD
                )
            return
        
        # Check user status
        if user.status != User.STATUS_ACTIVE:
            if user.status == User.STATUS_PENDING:
                await update.message.reply_text(
                    "⏳ Ваш аккаунт ожидает активации администратором."
                )
            else:
                await update.message.reply_text(
                    "❌ Ваш аккаунт деактивирован. Обратитесь к администратору."
                )
            return
        
        # Update user activity
        AuthManager.update_user_activity(user_id)
        
        # Add user to context
        context.user = user
        
        text = update.message.text
        user_state = context.user_data.get('state')
        
        # Debug logging
        logger.info(f"User {user_id} state: {user_state}, message: {text}, state type: {type(user_state)}")
        
        # Handle navigation buttons (check before state processing)
        if text == '🔙 Главное меню':
            # Clear any active state
            context.user_data.pop('state', None)
            context.user_data.pop('sale_data', None)
            context.user_data.pop('selected_category', None)
            context.user_data.pop('selected_user_id', None)
            context.user_data.pop('manual_quantity_input', None)
            await start(update, context)
            return
        elif text == '👤 Переключить бариста':
            await users_handler.switch_barista(update, context)
            return
        elif text == '🔙 Назад к пользователям':
            # Clear any active state
            context.user_data.pop('state', None)
            context.user_data.pop('selected_user_id', None)
            await users_handler.show_users_menu(update, context)
            return
        elif text == '🔙 Назад к балансу':
            # Clear any active state
            context.user_data.pop('state', None)
            await balance_handler.show_balance_menu(update, context)
            return
        
        # Handle state-based responses
        # Check state again after navigation buttons to ensure it hasn't changed
        current_state = context.user_data.get('state')
        if current_state == 'selecting_category':
            logger.info(f"Processing category selection for user {user_id}, category: {text}")
            try:
                await sales_handler.handle_category_selection(update, context)
                logger.info(f"Category selection completed for user {user_id}")
            except Exception as e:
                logger.error(f"Error in handle_category_selection: {str(e)}", user_id, exc_info=True)
                await update.message.reply_text(
                    "❌ Произошла ошибка при выборе категории. Попробуйте еще раз.",
                    reply_markup=sales_handler.categories_keyboard
                )
            # Always return after processing state
            return
        elif user_state == 'selecting_product':
            await sales_handler.handle_product_selection(update, context)
            return
        elif user_state == 'entering_quantity':
            await sales_handler.handle_quantity_input(update, context)
            return
        elif user_state == 'asking_discount':
            await sales_handler.handle_discount_choice(update, context)
            return
        elif user_state == 'entering_discount':
            await sales_handler.handle_discount_input(update, context)
            return
        elif user_state == 'selecting_payment':
            await sales_handler.handle_payment_selection(update, context)
            return
        elif user_state == 'confirming_sale':
            await sales_handler.handle_sale_confirmation(update, context)
            return
        elif user_state == 'entering_expense_amount':
            await expenses_handler.handle_expense_amount(update, context)
            return
        elif user_state == 'entering_expense_description':
            await expenses_handler.handle_expense_description(update, context)
            return
        elif user_state == 'confirming_expense':
            await expenses_handler.handle_expense_confirmation(update, context)
            return
        elif user_state == 'waiting_income_data':
            await balance_handler.process_income_data(update, context)
            return
        elif user_state == 'waiting_expense_transaction_data':
            await balance_handler.process_expense_transaction_data(update, context)
            return
        elif user_state == 'adding_user':
            await users_handler.handle_add_user_data(update, context)
            return
        elif user_state == 'selecting_user_for_role':
            await users_handler.handle_user_selection(update, context)
            return
        elif user_state == 'selecting_role':
            await users_handler.handle_role_selection(update, context)
            return
        elif user_state == 'selecting_user_for_activation':
            # Check if it's a button press first
            if text == '✅ Активировать':
                # User clicked activate button without selecting user first
                await update.message.reply_text(
                    "⚠️ Сначала введите ID пользователя из списка выше, затем нажмите кнопку активации.",
                    reply_markup=users_handler.user_management_keyboard
                )
                return
            elif text == '❌ Деактивировать':
                await update.message.reply_text(
                    "⚠️ Сначала введите ID пользователя из списка выше, затем нажмите кнопку деактивации.",
                    reply_markup=users_handler.user_management_keyboard
                )
                return
            else:
                # User typed ID, process it
                await users_handler.handle_user_activation_selection(update, context)
                return
        elif user_state == 'selecting_barista':
            # Handle barista selection
            await users_handler.handle_barista_selection(update, context)
            return
        elif user_state == 'managing_user_status':
            # Handle activation/deactivation buttons
            if text == '✅ Активировать':
                await users_handler.activate_user(update, context)
                return
            elif text == '❌ Деактивировать':
                await users_handler.deactivate_user(update, context)
                return
            else:
                # If user typed ID directly, try to select user
                await users_handler.handle_user_activation_selection(update, context)
                return
        elif user_state == 'selecting_barista':
            # Handle barista selection
            await users_handler.handle_barista_selection(update, context)
            return
        
        # Handle menu selections
        if text == '💰 Продажа':
            if user.can_add_sales():
                await sales_handler.add_sale(update, context)
            else:
                await update.message.reply_text("❌ У вас нет прав для работы с продажами.")
        elif text == '💸 Расходы':
            if user.can_add_expenses():
                await expenses_handler.show_expenses_menu(update, context)
            else:
                await update.message.reply_text("❌ У вас нет прав для работы с расходами.")
        elif text == '📊 Отчеты':
            if user.can_view_reports():
                await reports_handler.show_reports_menu(update, context)
            else:
                await update.message.reply_text("❌ У вас нет прав для просмотра отчетов.")
        elif text == '💰 Баланс':
            await balance_handler.show_balance_menu(update, context)
        elif text == '👥 Пользователи':
            if user.can_manage_users():
                await users_handler.show_users_menu(update, context)
            else:
                await update.message.reply_text("❌ У вас нет прав для управления пользователями.")
        elif text == 'ℹ️ Помощь':
            await help_command(update, context)
        elif text == '🟢 Открыть смену':
            await shifts_handler.open_shift(update, context)
        elif text == '🔴 Закрыть смену':
            await shifts_handler.close_shift(update, context)
    
        # Sales menu handlers
        elif text == '💰 Добавить продажу':
            await sales_handler.add_sale(update, context)
        elif text == '📊 Продажи за день':
            await sales_handler.get_daily_sales(update, context)
        elif text == '📈 Продажи за неделю':
            await sales_handler.get_weekly_sales(update, context)
        elif text == '📅 Продажи за месяц':
            await sales_handler.get_monthly_sales(update, context)
        
        # Expenses menu handlers
        elif text == '🛒 Закуп':
            await expenses_handler.add_purchase(update, context)
        elif text == '👥 Зарплата':
            await expenses_handler.add_salary(update, context)
        elif text == '📉 Списание':
            await expenses_handler.add_write_off(update, context)
        elif text == '📊 Расходы за день':
            await expenses_handler.get_daily_expenses(update, context)
        elif text == '📈 Расходы за неделю':
            await expenses_handler.get_weekly_expenses(update, context)
        elif text == '📅 Расходы за месяц':
            await expenses_handler.get_monthly_expenses(update, context)
        elif text == '🔙 Назад к расходам':
            await expenses_handler.show_expenses_menu(update, context)
        
        # Reports menu handlers
        elif text == '📊 Отчет за день':
            await reports_handler.get_daily_report(update, context)
        elif text == '📈 Отчет за неделю':
            await reports_handler.get_weekly_report(update, context)
        elif text == '📅 Отчет за месяц':
            await reports_handler.get_monthly_report(update, context)
        elif text == '💰 Финансовый отчет':
            await reports_handler.get_financial_report(update, context)
        elif text == '📥 Скачать CSV':
            await reports_handler.show_csv_menu(update, context)
        elif text == '📊 CSV за день':
            await reports_handler.download_daily_csv(update, context)
        elif text == '📈 CSV за неделю':
            await reports_handler.download_weekly_csv(update, context)
        elif text == '📅 CSV за месяц':
            await reports_handler.download_monthly_csv(update, context)
        elif text == '🔙 Назад к отчетам':
            await reports_handler.show_reports_menu(update, context)
        
        # Balance menu handlers
        elif text == '💰 Текущий баланс':
            await balance_handler.get_current_balance(update, context)
        elif text == '📊 История операций':
            await balance_handler.get_transaction_history(update, context)
        elif text == '💵 Пополнить баланс':
            await balance_handler.add_income(update, context)
        elif text == '💸 Снять средства':
            await balance_handler.add_expense_transaction(update, context)
        elif text == '🔄 Обновить данные':
            await balance_handler.refresh_data(update, context)
        elif text == '📊 Сформировать отчет':
            await reports_handler.show_reports_menu(update, context)
        
        # Users menu handlers (admin only)
        elif text == '👥 Список пользователей':
            await users_handler.list_users(update, context)
        elif text == '➕ Добавить пользователя':
            await users_handler.add_user(update, context)
        elif text == '⏳ Ожидающие активации':
            await users_handler.list_pending_users(update, context)
        elif text == '🔧 Управление ролями':
            await users_handler.manage_user_roles(update, context)
        elif text == '📊 Статистика пользователей':
            await users_handler.user_statistics(update, context)
        elif text == '👑 Администратор':
            await users_handler.handle_role_selection(update, context)
        elif text == '☕ Бариста':
            await users_handler.handle_role_selection(update, context)
        elif text == '✅ Активировать':
            await users_handler.activate_user(update, context)
        elif text == '❌ Деактивировать':
            await users_handler.deactivate_user(update, context)
        
        else:
            # Получить динамическую клавиатуру с учетом статуса смены
            main_keyboard = get_main_keyboard(
                show_barista_switch=user.is_barista() or user.is_admin()
            )
            await update.message.reply_text(
                "❓ Неизвестная команда. Используйте меню для навигации.",
                reply_markup=main_keyboard
            )
            logger.warning(f"Unknown command from user {user_id}: {text}")
    
    except Exception as e:
        logger.error(f"Error in handle_message: {str(e)}", user_id)
        await update.message.reply_text(
            "❌ Произошла ошибка при обработке сообщения. Попробуйте еще раз."
        )


async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle errors that occur during bot operation.
    
    Logs errors and attempts to send error message to user.
    Handles critical errors like bot conflicts.
    
    Args:
        update (Update): Telegram update object
        context (ContextTypes.DEFAULT_TYPE): Bot context
    """
    user_id = update.effective_user.id if update and update.effective_user else None
    error = context.error
    
    # Handle critical errors that require bot shutdown
    if error and isinstance(error, Exception):
        error_str = str(error)
        
        # Check for bot conflict error
        if "Conflict" in error_str and "getUpdates" in error_str:
            logger.critical(
                f"Bot conflict detected: {error_str}\n"
                "Another bot instance is running. Please stop all bot instances and restart.",
                user_id
            )
            logger.critical(
                "⚠️  CRITICAL: Multiple bot instances detected!\n"
                "Run 'python stop_bot.py' to stop all instances, then restart the bot."
            )
            # Don't try to stop application here - it may not be running yet
            # The conflict will be caught in run_polling() and handled there
            return
        
        # Log other errors
        logger.error(f"Update {update} caused error: {error_str}", user_id, exc_info=True)
    else:
        logger.error(f"Update {update} caused error {error}", user_id)
    
    # Try to send error message to user (only for non-critical errors)
    if update and update.message and error:
        error_str = str(error) if error else "Unknown error"
        
        # Don't send user message for conflict errors
        if "Conflict" not in error_str or "getUpdates" not in error_str:
            try:
                await update.message.reply_text(
                    "❌ Произошла внутренняя ошибка. Попробуйте еще раз или обратитесь к администратору."
                )
            except Exception as e:
                logger.error(f"Failed to send error message to user: {str(e)}", user_id)


def main() -> None:
    """
    Main function to run the bot.
    
    Initializes the bot application, sets up handlers, and starts polling.
    Handles graceful shutdown and error management.
    """
    lock = FileLock()
    
    try:
        # Try to acquire lock - prevents multiple instances
        if not lock.acquire():
            print("\n❌ Ошибка: Бот уже запущен!")
            print("Пожалуйста, остановите существующий экземпляр бота перед запуском нового.\n")
            sys.exit(1)
        
        logger.info("=" * 50)
        logger.info("Starting Romano Bot...")
        logger.info("=" * 50)
        
        # Validate configuration
        try:
            validate_config()
            logger.info("Configuration validated successfully")
        except ValueError as e:
            logger.error(f"Configuration error: {e}")
            return
        
        # Initialize database
        try:
            if not init_database():
                logger.error("Failed to initialize database")
                return
            logger.info("Database initialized successfully")
        except Exception as e:
            logger.error(f"Database initialization error: {e}")
            return
        
        # Create application
        try:
            application = Application.builder().token(BOT_TOKEN).build()
            logger.info("Application created successfully")
        except Exception as e:
            logger.error(f"Failed to create application: {e}")
            return
        
        # Setup graceful shutdown
        graceful_shutdown = GracefulShutdown(application)
        
        # Add handlers
        try:
            application.add_handler(CommandHandler("start", start))
            application.add_handler(CommandHandler("help", help_command))
            application.add_handler(CommandHandler("get_chat_id", get_chat_id))
            application.add_handler(CommandHandler("chatid", get_chat_id))  # Alias for convenience
            application.add_handler(CommandHandler("set_group_chat_id", set_group_chat_id))
            application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
            application.add_error_handler(error_handler)
            logger.info("Handlers added successfully")
        except Exception as e:
            logger.error(f"Failed to add handlers: {e}")
            return
        
        # Start the bot
        logger.info("Starting bot polling...")
        logger.info("Bot is now running. Press Ctrl+C to stop.")
        
        conflict_detected = False
        try:
            application.run_polling(
                drop_pending_updates=True,  # Drop pending updates on start
                allowed_updates=None
            )
        except KeyboardInterrupt:
            logger.info("Received KeyboardInterrupt, stopping bot...")
        except Exception as e:
            error_str = str(e)
            if "Conflict" in error_str and "getUpdates" in error_str:
                conflict_detected = True
                logger.critical(
                    f"Bot conflict error detected: {error_str}\n"
                    "Please stop all running bot instances using 'python stop_bot.py'"
                )
                print("\n" + "=" * 60)
                print("❌ ОШИБКА: Запущено несколько экземпляров бота!")
                print("=" * 60)
                print("\nДействия для исправления:")
                print("1. Остановите все экземпляры командой: python stop_bot.py")
                print("2. Убедитесь, что файл .bot.lock удален")
                print("3. Запустите бота снова: python run_bot.py")
                print("\n" + "=" * 60)
            else:
                logger.error(f"Error during bot execution: {e}", exc_info=True)
        finally:
            # Release lock
            try:
                lock.release()
            except Exception as e:
                logger.error(f"Error releasing lock: {e}")
            
            logger.info("=" * 50)
            logger.info("Romano Bot stopped")
            logger.info("=" * 50)
            
            # Exit with error code if conflict was detected
            if conflict_detected:
                sys.exit(1)
    
    except RuntimeError as e:
        # Lock acquisition failed
        print(f"\n❌ Ошибка: {e}\n")
        sys.exit(1)
    except Exception as e:
        logger.critical(f"Critical error in main: {e}")
        lock.release()
        raise


if __name__ == '__main__':
    main()
