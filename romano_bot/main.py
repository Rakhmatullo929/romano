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
    from .utils.helpers import logger, GracefulShutdown, AuthManager, FileLock
    from .models.schema import User
except ImportError:
    # Fallback for direct execution
    from config import BOT_TOKEN, ADMIN_IDS, validate_config
    from services.database import init_database
    from handlers.sales import SalesHandler
    from handlers.expenses import ExpensesHandler
    from handlers.reports import ReportsHandler
    from handlers.balance import BalanceHandler
    from handlers.users import UsersHandler
    from utils.helpers import logger, GracefulShutdown, AuthManager, FileLock
    from models.schema import User

# Initialize handlers
sales_handler = SalesHandler()
expenses_handler = ExpensesHandler()
reports_handler = ReportsHandler()
balance_handler = BalanceHandler()
users_handler = UsersHandler()

# Main menu keyboard
MAIN_KEYBOARD = ReplyKeyboardMarkup([
    ['💰 Продажи', '💸 Расходы'],
    ['📊 Отчеты', '💰 Баланс'],
    ['👥 Пользователи', 'ℹ️ Помощь']
], resize_keyboard=True)

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
        
        await update.message.reply_text(
            f"☕ <b>Добро пожаловать, {name}!</b>\n\n"
            f"Роль: {role_text}\n"
            f"Это бот для управления кофейней Romano.uz\n\n"
            "Выберите раздел для работы:",
            reply_markup=MAIN_KEYBOARD,
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
    user_id = update.effective_user.id
    
    try:
        logger.info(f"User {user_id} requested help")
        
        help_text = """
ℹ️ <b>Помощь по использованию бота</b>

<b>Основные разделы:</b>
💰 <b>Продажи</b> - добавление и просмотр продаж
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
• перевод

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


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle text messages from users.
    
    Routes messages to appropriate handlers based on user state and message content.
    Handles both state-based responses and menu selections with role-based access control.
    
    Args:
        update (Update): Telegram update object
        context (ContextTypes.DEFAULT_TYPE): Bot context
    """
    user_id = update.effective_user.id
    
    try:
        logger.info(f"User {user_id} sent message: {update.message.text}")
        
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
        logger.info(f"User {user_id} state: {user_state}, message: {text}")
        
        # Handle navigation buttons (check before state processing)
        if text == '🔙 Назад к пользователям':
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
        if user_state == 'selecting_product':
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
        elif user_state == 'entering_purchase_data':
            await expenses_handler.handle_purchase_data(update, context)
            return
        elif user_state == 'entering_salary_data':
            await expenses_handler.handle_salary_data(update, context)
            return
        elif user_state == 'entering_writeoff_data':
            await expenses_handler.handle_writeoff_data(update, context)
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
        
        # Handle menu selections
        if text == '💰 Продажи':
            if user.can_add_sales():
                await sales_handler.show_sales_menu(update, context)
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
        elif text == '🔙 Главное меню':
            await start(update, context)
    
        # Sales menu handlers
        elif text == '💰 Добавить продажу':
            await sales_handler.add_sale(update, context)
        elif text == '📊 Продажи за день':
            await sales_handler.get_daily_sales(update, context)
        elif text == '📈 Продажи за неделю':
            await sales_handler.get_weekly_sales(update, context)
        elif text == '📅 Продажи за месяц':
            await sales_handler.get_monthly_sales(update, context)
        elif text == '🔙 Назад к продажам':
            await sales_handler.show_sales_menu(update, context)
        
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
        elif text == '📅 День':
            await balance_handler.set_period_day(update, context)
        elif text == '📈 Неделя':
            await balance_handler.set_period_week(update, context)
        elif text == '📊 Месяц':
            await balance_handler.set_period_month(update, context)
        elif text == '🔄 Обновить данные':
            await balance_handler.refresh_data(update, context)
        elif text == '📊 Сформировать отчет':
            await reports_handler.show_reports_menu(update, context)
        
        # Users menu handlers (admin only)
        elif text == '👥 Список пользователей':
            await users_handler.list_users(update, context)
        elif text == '➕ Добавить пользователя':
            await users_handler.add_user(update, context)
        elif text == '🔧 Управление ролями':
            await users_handler.manage_user_roles(update, context)
        elif text == '📊 Статистика пользователей':
            await users_handler.user_statistics(update, context)
        elif text == '👑 Администратор':
            await users_handler.handle_role_selection(update, context)
        elif text == '☕ Бариста':
            await users_handler.handle_role_selection(update, context)
        
        else:
            await update.message.reply_text(
                "❓ Неизвестная команда. Используйте меню для навигации.",
                reply_markup=MAIN_KEYBOARD
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
    
    Args:
        update (Update): Telegram update object
        context (ContextTypes.DEFAULT_TYPE): Bot context
    """
    user_id = update.effective_user.id if update and update.effective_user else None
    logger.error(f"Update {update} caused error {context.error}", user_id)
    
    # Try to send error message to user
    if update and update.message:
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
            application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
            application.add_error_handler(error_handler)
            logger.info("Handlers added successfully")
        except Exception as e:
            logger.error(f"Failed to add handlers: {e}")
            return
        
        # Start the bot
        logger.info("Starting bot polling...")
        logger.info("Bot is now running. Press Ctrl+C to stop.")
        
        try:
            application.run_polling()
        except KeyboardInterrupt:
            logger.info("Received KeyboardInterrupt, stopping bot...")
        except Exception as e:
            logger.error(f"Error during bot execution: {e}")
        finally:
            lock.release()
            logger.info("=" * 50)
            logger.info("Romano Bot stopped")
            logger.info("=" * 50)
    
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
