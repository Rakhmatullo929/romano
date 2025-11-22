"""
Expenses handlers for Romano Bot
"""
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import ContextTypes
from decimal import Decimal
from datetime import datetime

from ..models.schema import Expense, Balance
from ..services.database import get_session
from ..utils.helpers import format_currency
from ..config import EXPENSE_CATEGORIES
from ..services.notifier import notify_group, format_expense_notification
from ..services.barista_session import BaristaSessionManager


class ExpensesHandler:
    """Handle expenses-related operations"""
    
    def __init__(self):
        self.main_keyboard = ReplyKeyboardMarkup([
            ['🛒 Закуп', '👥 Зарплата'],
            ['📉 Списание', '📊 Расходы за день'],
            ['📈 Расходы за неделю', '📅 Расходы за месяц'],
            ['🔙 Главное меню']
        ], resize_keyboard=True)
        
        self.categories_keyboard = ReplyKeyboardMarkup([
            ['🛒 Закуп', '👥 Зарплата', '📉 Списание'],
            ['🔙 Назад к расходам', '🔙 Главное меню']
        ], resize_keyboard=True)
        
        self.confirm_keyboard = ReplyKeyboardMarkup([
            ['✅ Подтвердить', '❌ Отменить'],
            ['🔙 Назад к расходам', '🔙 Главное меню']
        ], resize_keyboard=True)
        
        self.back_to_main_keyboard = ReplyKeyboardMarkup([
            ['🔙 Главное меню']
        ], resize_keyboard=True)
    
    async def show_expenses_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Show expenses menu"""
        # Clear any active expense state when returning to menu
        context.user_data.pop('expense_data', None)
        context.user_data.pop('state', None)
        
        await update.message.reply_text(
            "💸 <b>Управление расходами</b>\n\n"
            "Выберите тип расхода:",
            reply_markup=self.main_keyboard,
            parse_mode='HTML'
        )
    
    async def add_purchase(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Start adding purchase expense"""
        # Проверить наличие активного бариста
        active_barista = BaristaSessionManager.get_active_barista(context)
        if not active_barista:
            await update.message.reply_text(
                "⚠️ <b>Активный бариста не выбран</b>\n\n"
                "Перед добавлением расхода необходимо выбрать активного бариста.\n"
                "Используйте меню '👤 Переключить бариста' для выбора.",
                parse_mode='HTML'
            )
            return
        
        # Clear any previous expense data
        context.user_data.pop('expense_data', None)
        context.user_data.pop('state', None)
        
        await update.message.reply_text(
            "🛒 <b>Добавление закупа</b>\n\n"
            "Введите сумму расхода:",
            reply_markup=self.back_to_main_keyboard,
            parse_mode='HTML'
        )
        context.user_data['state'] = 'entering_expense_amount'
        context.user_data['expense_data'] = {'category': 'Закуп'}
    
    async def add_salary(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Start adding salary expense"""
        # Проверить наличие активного бариста
        active_barista = BaristaSessionManager.get_active_barista(context)
        if not active_barista:
            await update.message.reply_text(
                "⚠️ <b>Активный бариста не выбран</b>\n\n"
                "Перед добавлением расхода необходимо выбрать активного бариста.\n"
                "Используйте меню '👤 Переключить бариста' для выбора.",
                parse_mode='HTML'
            )
            return
        
        # Clear any previous expense data
        context.user_data.pop('expense_data', None)
        context.user_data.pop('state', None)
        
        await update.message.reply_text(
            "👥 <b>Добавление зарплаты</b>\n\n"
            "Введите сумму расхода:",
            reply_markup=self.back_to_main_keyboard,
            parse_mode='HTML'
        )
        context.user_data['state'] = 'entering_expense_amount'
        context.user_data['expense_data'] = {'category': 'Зарплата'}
    
    async def add_write_off(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Start adding write-off expense"""
        # Проверить наличие активного бариста
        active_barista = BaristaSessionManager.get_active_barista(context)
        if not active_barista:
            await update.message.reply_text(
                "⚠️ <b>Активный бариста не выбран</b>\n\n"
                "Перед добавлением расхода необходимо выбрать активного бариста.\n"
                "Используйте меню '👤 Переключить бариста' для выбора.",
                parse_mode='HTML'
            )
            return
        
        # Clear any previous expense data
        context.user_data.pop('expense_data', None)
        context.user_data.pop('state', None)
        
        await update.message.reply_text(
            "📉 <b>Добавление списания</b>\n\n"
            "Введите сумму расхода:",
            reply_markup=self.back_to_main_keyboard,
            parse_mode='HTML'
        )
        context.user_data['state'] = 'entering_expense_amount'
        context.user_data['expense_data'] = {'category': 'Списание'}
    
    async def handle_expense_amount(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle expense amount input"""
        try:
            amount_str = update.message.text.strip()
            
            if not amount_str:
                raise ValueError("Сумма не может быть пустой")
            
            amount = Decimal(amount_str)
            if amount <= 0:
                raise ValueError("Сумма должна быть больше 0")
            
            # Store amount
            context.user_data['expense_data']['amount'] = amount
            
            # Ask for description/name based on category
            category = context.user_data['expense_data']['category']
            
            if category == 'Зарплата':
                await update.message.reply_text(
                    "👥 <b>Добавление зарплаты</b>\n\n"
                    "Введите имя сотрудника:",
                    reply_markup=self.back_to_main_keyboard,
                    parse_mode='HTML'
                )
            elif category == 'Закуп':
                await update.message.reply_text(
                    "🛒 <b>Добавление закупа</b>\n\n"
                    "Введите название/описание закупа:",
                    reply_markup=self.back_to_main_keyboard,
                    parse_mode='HTML'
                )
            elif category == 'Списание':
                await update.message.reply_text(
                    "📉 <b>Добавление списания</b>\n\n"
                    "Введите причину списания:",
                    reply_markup=self.back_to_main_keyboard,
                    parse_mode='HTML'
                )
            
            context.user_data['state'] = 'entering_expense_description'
            
        except (ValueError, TypeError) as e:
            await update.message.reply_text(
                f"❌ Ошибка: {str(e)}\n\n"
                "Пожалуйста, введите корректную сумму (только число):",
                reply_markup=self.back_to_main_keyboard,
                parse_mode='HTML'
            )
    
    async def handle_expense_description(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle expense description/name input"""
        try:
            description = update.message.text.strip()
            
            if not description:
                raise ValueError("Название/описание не может быть пустым")
            
            category = context.user_data['expense_data']['category']
            
            # Store description based on category
            if category == 'Зарплата':
                employee_name = description
                context.user_data['expense_data'].update({
                    'description': f"Зарплата {employee_name}",
                    'employee_name': employee_name,
                    'comment': f"Зарплата сотрудника: {employee_name}"
                })
            elif category == 'Закуп':
                context.user_data['expense_data'].update({
                    'description': description,
                    'comment': f"Закуп: {description}"
                })
            elif category == 'Списание':
                context.user_data['expense_data'].update({
                    'description': f"Списание: {description}",
                    'comment': description
                })
            
            # Show confirmation
            await self._show_expense_confirmation(update, context)
            
        except (ValueError, TypeError) as e:
            await update.message.reply_text(
                f"❌ Ошибка: {str(e)}\n\n"
                "Пожалуйста, введите название/описание:",
                reply_markup=self.back_to_main_keyboard,
                parse_mode='HTML'
            )
    
    async def _show_expense_confirmation(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Show expense confirmation"""
        expense_data = context.user_data['expense_data']
        
        message = f"📋 <b>Подтверждение расхода</b>\n\n"
        message += f"📂 <b>Категория:</b> {expense_data['category']}\n"
        message += f"💰 <b>Сумма:</b> {format_currency(expense_data['amount'])}\n"
        message += f"📝 <b>Описание:</b> {expense_data['description']}\n"
        
        if expense_data.get('employee_name'):
            message += f"👤 <b>Сотрудник:</b> {expense_data['employee_name']}\n"
        
        if expense_data.get('comment'):
            message += f"💬 <b>Комментарий:</b> {expense_data['comment']}\n"
        
        message += f"🕐 <b>Дата:</b> {datetime.now().strftime('%d.%m.%Y %H:%M')}\n\n"
        message += "Подтвердить расход?"
        
        await update.message.reply_text(
            message,
            reply_markup=self.confirm_keyboard,
            parse_mode='HTML'
        )
        context.user_data['state'] = 'confirming_expense'
    
    async def handle_expense_confirmation(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle expense confirmation"""
        choice = update.message.text
        
        if choice == "✅ Подтвердить":
            await self._save_expense(update, context)
        elif choice == "❌ Отменить":
            await update.message.reply_text(
                "❌ Расход отменен.",
                reply_markup=self.main_keyboard
            )
            context.user_data.pop('expense_data', None)
            context.user_data.pop('state', None)
        else:
            await update.message.reply_text(
                "❌ Неверный выбор. Подтвердите или отмените расход:",
                reply_markup=self.confirm_keyboard
            )
    
    async def _save_expense(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Save expense to database"""
        try:
            expense_data = context.user_data['expense_data']
            
            # Получить активного бариста
            active_barista = BaristaSessionManager.get_active_barista(context)
            if not active_barista:
                await update.message.reply_text(
                    "❌ <b>Ошибка:</b> Активный бариста не выбран.\n"
                    "Пожалуйста, выберите активного бариста перед сохранением расхода.",
                    parse_mode='HTML'
                )
                return
            
            # Получить user_id из базы данных (не telegram_id, а id)
            # Используем тот же session для получения user_id
            with get_session() as session:
                from ..models.schema import User
                db_user = session.query(User).filter(
                    User.telegram_id == active_barista.telegram_id
                ).first()
                user_id = db_user.id if db_user else None
                
                # Теперь создаем расход в том же session
                expense = Expense(
                    category=expense_data['category'],
                    description=expense_data['description'],
                    amount=expense_data['amount'],
                    comment=expense_data.get('comment'),
                    employee_name=expense_data.get('employee_name'),
                    payment_method=None,  # Not required for these expense types
                    user_id=user_id
                )
                session.add(expense)
                session.flush()  # Flush to get expense.id
                
                # Create balance transaction for expense
                balance_record = Balance(
                    amount=expense_data['amount'],
                    transaction_type='expense',
                    description=f"{expense_data['category']}: {expense_data['description']}",
                    reference_id=expense.id,
                    reference_type='expense'
                )
                session.add(balance_record)
                session.commit()
            
            # Get user information for notification
            user = getattr(context, 'user', None)
            if not user:
                from ..utils.helpers import AuthManager
                user = AuthManager.get_user(update.effective_user.id)
            
            # Get username or first_name
            username = user.first_name if user and user.first_name else (
                user.username if user and user.username else (
                    update.effective_user.first_name or update.effective_user.username or 'Неизвестный пользователь'
                )
            )
            
            # Prepare note for notification
            note = expense_data.get('comment', '')
            if not note:
                note = expense_data.get('description', '')
            if expense_data.get('employee_name'):
                note = f"{note} (Сотрудник: {expense_data['employee_name']})" if note else f"Сотрудник: {expense_data['employee_name']}"
            
            # Send notification to group
            expense_timestamp = datetime.now()
            notification_message = format_expense_notification(
                username=username,
                category=expense_data['category'],
                amount=expense_data['amount'],
                note=note or 'Без комментария',
                timestamp=expense_timestamp
            )
            await notify_group(context, notification_message)
            
            # Get current balance
            from .balance import BalanceHandler
            balance_handler = BalanceHandler()
            current_balance = balance_handler.get_current_balance_amount()
            
            # Success message
            message = f"✅ <b>Расход успешно добавлен!</b>\n\n"
            message += f"📂 <b>Категория:</b> {expense_data['category']}\n"
            message += f"💰 <b>Сумма:</b> {format_currency(expense_data['amount'])}\n"
            message += f"📝 <b>Описание:</b> {expense_data['description']}\n"
            
            if expense_data.get('employee_name'):
                message += f"👤 <b>Сотрудник:</b> {expense_data['employee_name']}\n"
            
            message += f"🕐 <b>Время:</b> {expense_timestamp.strftime('%d.%m.%Y %H:%M')}\n\n"
            message += f"💰 <b>Текущий баланс:</b> {format_currency(current_balance)}"
            
            await update.message.reply_text(
                message,
                reply_markup=self.main_keyboard,
                parse_mode='HTML'
            )
            
            # Clear expense data
            context.user_data.pop('expense_data', None)
            context.user_data.pop('state', None)
            
        except Exception as e:
            await update.message.reply_text(
                f"❌ Ошибка при сохранении расхода: {str(e)}\n\n"
                "Попробуйте еще раз.",
                reply_markup=self.main_keyboard
            )
    
    async def get_daily_expenses(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Get daily expenses report"""
        today = datetime.now().date()
        
        with get_session() as session:
            expenses = session.query(Expense).filter(
                Expense.created_at >= today
            ).all()
            
            if not expenses:
                await update.message.reply_text(
                    "📊 <b>Расходы за сегодня</b>\n\n"
                    "Расходов не было",
                    reply_markup=self.main_keyboard,
                    parse_mode='HTML'
                )
                return
            
            total_amount = sum(expense.amount for expense in expenses)
            
            message = f"📊 <b>Расходы за сегодня</b>\n"
            message += f"({today.strftime('%d.%m.%Y')})\n\n"
            message += f"💰 <b>Общая сумма:</b> {format_currency(total_amount)}\n"
            message += f"📈 <b>Количество расходов:</b> {len(expenses)}\n\n"
            
            # Group by category
            categories = {}
            for expense in expenses:
                if expense.category not in categories:
                    categories[expense.category] = {
                        'amount': 0,
                        'count': 0,
                        'items': []
                    }
                categories[expense.category]['amount'] += expense.amount
                categories[expense.category]['count'] += 1
                categories[expense.category]['items'].append(expense)
            
            message += "📂 <b>По категориям:</b>\n"
            for category, data in categories.items():
                emoji = EXPENSE_CATEGORIES.get(category, '📁')
                message += f"\n{emoji} <b>{category}:</b>\n"
                message += f"• Сумма: {format_currency(data['amount'])}\n"
                message += f"• Количество: {data['count']}\n"
                
                # Show recent items (max 3)
                recent_items = data['items'][-3:]
                for item in recent_items:
                    short_desc = item.description[:30] + "..." if len(item.description) > 30 else item.description
                    message += f"  - {format_currency(item.amount)}: {short_desc}\n"
            
            await update.message.reply_text(
                message,
                reply_markup=self.main_keyboard,
                parse_mode='HTML'
            )
    
    async def get_weekly_expenses(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Get weekly expenses report"""
        from datetime import timedelta
        
        end_date = datetime.now().date()
        start_date = end_date - timedelta(days=7)
        
        with get_session() as session:
            expenses = session.query(Expense).filter(
                Expense.created_at >= start_date,
                Expense.created_at <= end_date
            ).all()
            
            if not expenses:
                await update.message.reply_text(
                    "📈 <b>Расходы за неделю</b>\n\n"
                    "Расходов не было",
                    reply_markup=self.main_keyboard,
                    parse_mode='HTML'
                )
                return
            
            total_amount = sum(expense.amount for expense in expenses)
            
            message = f"📈 <b>Расходы за неделю</b>\n"
            message += f"({start_date.strftime('%d.%m')} - {end_date.strftime('%d.%m.%Y')})\n\n"
            message += f"💰 <b>Общая сумма:</b> {format_currency(total_amount)}\n"
            message += f"📈 <b>Количество расходов:</b> {len(expenses)}\n"
            message += f"📊 <b>Средний расход:</b> {format_currency(total_amount / len(expenses))}\n\n"
            
            # Group by category
            categories = {}
            for expense in expenses:
                if expense.category not in categories:
                    categories[expense.category] = 0
                categories[expense.category] += expense.amount
            
            message += "📂 <b>По категориям:</b>\n"
            for category, amount in categories.items():
                emoji = EXPENSE_CATEGORIES.get(category, '📁')
                percentage = (amount / total_amount) * 100
                message += f"• {emoji} {category}: {format_currency(amount)} ({percentage:.1f}%)\n"
            
            await update.message.reply_text(
                message,
                reply_markup=self.main_keyboard,
                parse_mode='HTML'
            )
    
    async def get_monthly_expenses(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Get monthly expenses report"""
        today = datetime.now().date()
        month_start = today.replace(day=1)
        
        with get_session() as session:
            expenses = session.query(Expense).filter(
                Expense.created_at >= month_start,
                Expense.created_at <= today
            ).all()
            
            if not expenses:
                await update.message.reply_text(
                    "📅 <b>Расходы за месяц</b>\n\n"
                    "Расходов не было",
                    reply_markup=self.main_keyboard,
                    parse_mode='HTML'
                )
                return
            
            total_amount = sum(expense.amount for expense in expenses)
            
            message = f"📅 <b>Расходы за месяц</b>\n"
            message += f"({month_start.strftime('%B %Y')})\n\n"
            message += f"💰 <b>Общая сумма:</b> {format_currency(total_amount)}\n"
            message += f"📈 <b>Количество расходов:</b> {len(expenses)}\n"
            message += f"📊 <b>Средний расход:</b> {format_currency(total_amount / len(expenses))}\n\n"
            
            # Group by category
            categories = {}
            for expense in expenses:
                if expense.category not in categories:
                    categories[expense.category] = 0
                categories[expense.category] += expense.amount
            
            message += "📂 <b>По категориям:</b>\n"
            for category, amount in categories.items():
                emoji = EXPENSE_CATEGORIES.get(category, '📁')
                percentage = (amount / total_amount) * 100
                message += f"• {emoji} {category}: {format_currency(amount)} ({percentage:.1f}%)\n"
            
            await update.message.reply_text(
                message,
                reply_markup=self.main_keyboard,
                parse_mode='HTML'
            )