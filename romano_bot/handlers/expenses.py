"""
Expenses handlers for Romano Bot
"""
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import ContextTypes
from decimal import Decimal
from datetime import datetime

from ..models.schema import Expense
from ..services.database import get_session
from ..utils.helpers import format_currency
from ..config import EXPENSE_CATEGORIES


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
            ['🔙 Назад к расходам']
        ], resize_keyboard=True)
        
        self.confirm_keyboard = ReplyKeyboardMarkup([
            ['✅ Подтвердить', '❌ Отменить'],
            ['🔙 Назад к расходам']
        ], resize_keyboard=True)
    
    async def show_expenses_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Show expenses menu"""
        await update.message.reply_text(
            "💸 <b>Управление расходами</b>\n\n"
            "Выберите тип расхода:",
            reply_markup=self.main_keyboard,
            parse_mode='HTML'
        )
    
    async def add_purchase(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Start adding purchase expense"""
        # Clear any previous expense data
        context.user_data.pop('expense_data', None)
        context.user_data.pop('state', None)
        
        await update.message.reply_text(
            "🛒 <b>Добавление закупа</b>\n\n"
            "Введите данные в формате:\n"
            "<code>Сумма — Описание</code>\n\n"
            "Пример: <code>500000 — 5 кг кофе</code>\n"
            "Пример: <code>150000 — Молоко и сливки</code>",
            reply_markup=ReplyKeyboardRemove(),
            parse_mode='HTML'
        )
        context.user_data['state'] = 'entering_purchase_data'
        context.user_data['expense_data'] = {'category': 'Закуп'}
    
    async def add_salary(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Start adding salary expense"""
        # Clear any previous expense data
        context.user_data.pop('expense_data', None)
        context.user_data.pop('state', None)
        
        await update.message.reply_text(
            "👥 <b>Добавление зарплаты</b>\n\n"
            "Введите данные в формате:\n"
            "<code>Имя сотрудника — Сумма</code>\n\n"
            "Пример: <code>Ахмед — 800000</code>\n"
            "Пример: <code>Мария — 750000</code>",
            reply_markup=ReplyKeyboardRemove(),
            parse_mode='HTML'
        )
        context.user_data['state'] = 'entering_salary_data'
        context.user_data['expense_data'] = {'category': 'Зарплата'}
    
    async def add_write_off(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Start adding write-off expense"""
        # Clear any previous expense data
        context.user_data.pop('expense_data', None)
        context.user_data.pop('state', None)
        
        await update.message.reply_text(
            "📉 <b>Добавление списания</b>\n\n"
            "Введите данные в формате:\n"
            "<code>Сумма — Причина списания</code>\n\n"
            "Пример: <code>25000 — Испортились сливки</code>\n"
            "Пример: <code>50000 — Сломался блендер</code>",
            reply_markup=ReplyKeyboardRemove(),
            parse_mode='HTML'
        )
        context.user_data['state'] = 'entering_writeoff_data'
        context.user_data['expense_data'] = {'category': 'Списание'}
    
    async def handle_purchase_data(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle purchase data input"""
        try:
            data = update.message.text.strip()
            
            # Parse format: "Сумма — Описание"
            if '—' not in data:
                raise ValueError("Используйте формат: Сумма — Описание")
            
            parts = data.split('—', 1)
            if len(parts) != 2:
                raise ValueError("Неверный формат данных")
            
            amount_str, description = parts
            amount_str = amount_str.strip()
            description = description.strip()
            
            if not amount_str or not description:
                raise ValueError("Сумма и описание не могут быть пустыми")
            
            amount = Decimal(amount_str)
            if amount <= 0:
                raise ValueError("Сумма должна быть больше 0")
            
            # Store expense data
            context.user_data['expense_data'].update({
                'amount': amount,
                'description': description,
                'comment': f"Закуп: {description}"
            })
            
            # Show confirmation
            await self._show_expense_confirmation(update, context)
            
        except (ValueError, TypeError) as e:
            await update.message.reply_text(
                f"❌ Ошибка: {str(e)}\n\n"
                "Попробуйте еще раз в правильном формате:\n"
                "<code>Сумма — Описание</code>",
                reply_markup=ReplyKeyboardRemove(),
                parse_mode='HTML'
            )
    
    async def handle_salary_data(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle salary data input"""
        try:
            data = update.message.text.strip()
            
            # Parse format: "Имя — Сумма"
            if '—' not in data:
                raise ValueError("Используйте формат: Имя — Сумма")
            
            parts = data.split('—', 1)
            if len(parts) != 2:
                raise ValueError("Неверный формат данных")
            
            employee_name, amount_str = parts
            employee_name = employee_name.strip()
            amount_str = amount_str.strip()
            
            if not employee_name or not amount_str:
                raise ValueError("Имя сотрудника и сумма не могут быть пустыми")
            
            amount = Decimal(amount_str)
            if amount <= 0:
                raise ValueError("Сумма должна быть больше 0")
            
            # Store expense data
            context.user_data['expense_data'].update({
                'amount': amount,
                'description': f"Зарплата {employee_name}",
                'employee_name': employee_name,
                'comment': f"Зарплата сотрудника: {employee_name}"
            })
            
            # Show confirmation
            await self._show_expense_confirmation(update, context)
            
        except (ValueError, TypeError) as e:
            await update.message.reply_text(
                f"❌ Ошибка: {str(e)}\n\n"
                "Попробуйте еще раз в правильном формате:\n"
                "<code>Имя — Сумма</code>",
                reply_markup=ReplyKeyboardRemove(),
                parse_mode='HTML'
            )
    
    async def handle_writeoff_data(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle write-off data input"""
        try:
            data = update.message.text.strip()
            
            # Parse format: "Сумма — Причина"
            if '—' not in data:
                raise ValueError("Используйте формат: Сумма — Причина")
            
            parts = data.split('—', 1)
            if len(parts) != 2:
                raise ValueError("Неверный формат данных")
            
            amount_str, reason = parts
            amount_str = amount_str.strip()
            reason = reason.strip()
            
            if not amount_str or not reason:
                raise ValueError("Сумма и причина не могут быть пустыми")
            
            amount = Decimal(amount_str)
            if amount <= 0:
                raise ValueError("Сумма должна быть больше 0")
            
            # Store expense data
            context.user_data['expense_data'].update({
                'amount': amount,
                'description': f"Списание: {reason}",
                'comment': reason
            })
            
            # Show confirmation
            await self._show_expense_confirmation(update, context)
            
        except (ValueError, TypeError) as e:
            await update.message.reply_text(
                f"❌ Ошибка: {str(e)}\n\n"
                "Попробуйте еще раз в правильном формате:\n"
                "<code>Сумма — Причина</code>",
                reply_markup=ReplyKeyboardRemove(),
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
            
            with get_session() as session:
                expense = Expense(
                    category=expense_data['category'],
                    description=expense_data['description'],
                    amount=expense_data['amount'],
                    comment=expense_data.get('comment'),
                    employee_name=expense_data.get('employee_name'),
                    payment_method=None  # Not required for these expense types
                )
                session.add(expense)
                session.commit()
            
            # Success message
            message = f"✅ <b>Расход успешно добавлен!</b>\n\n"
            message += f"📂 <b>Категория:</b> {expense_data['category']}\n"
            message += f"💰 <b>Сумма:</b> {format_currency(expense_data['amount'])}\n"
            message += f"📝 <b>Описание:</b> {expense_data['description']}\n"
            
            if expense_data.get('employee_name'):
                message += f"👤 <b>Сотрудник:</b> {expense_data['employee_name']}\n"
            
            message += f"🕐 <b>Время:</b> {datetime.now().strftime('%d.%m.%Y %H:%M')}"
            
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