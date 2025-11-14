"""
Balance handlers for Romano Bot
"""
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import ContextTypes
from decimal import Decimal
from datetime import datetime, timedelta

from ..models.schema import Sale, Expense, Balance
from ..services.database import get_session
from ..utils.helpers import format_currency, logger


class BalanceHandler:
    """Handle balance operations and period-based reporting"""
    
    def __init__(self):
        self.main_keyboard = ReplyKeyboardMarkup([
            ['💰 Текущий баланс', '📊 История операций'],
            ['🔄 Обновить данные', '📊 Сформировать отчет'],
            ['🔙 Главное меню']
        ], resize_keyboard=True)
        
        self.admin_keyboard = ReplyKeyboardMarkup([
            ['💰 Текущий баланс', '📊 История операций'],
            ['💵 Пополнить баланс', '💸 Снять средства'],
            ['🔙 Главное меню']
        ], resize_keyboard=True)
        
        self.period_keyboard = ReplyKeyboardMarkup([
            ['📅 День', '📈 Неделя', '📊 Месяц'],
            ['🔙 Назад к балансу']
        ], resize_keyboard=True)
    
    def get_current_balance_amount(self) -> float:
        """
        Calculate current balance from all transactions.
        
        Returns:
            float: Current balance amount
        """
        try:
            with get_session() as session:
                transactions = session.query(Balance).all()
                balance = 0.0
                for transaction in transactions:
                    if transaction.transaction_type == 'income':
                        balance += float(transaction.amount)
                    elif transaction.transaction_type == 'expense':
                        balance -= float(transaction.amount)
                return balance
        except Exception as e:
            logger.error(f"Error calculating balance: {str(e)}")
            return 0.0
    
    async def show_balance_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Show balance main menu"""
        user_id = update.effective_user.id
        user = getattr(context, 'user', None)
        
        # If user not in context, get from database
        if not user:
            from ..utils.helpers import AuthManager
            user = AuthManager.get_user(user_id)
        
        # Get current balance
        current_balance = self.get_current_balance_amount()
        
        # Check if user is admin
        is_admin = user and user.is_admin() if user else False
        
        # Create menu based on user role
        if is_admin:
            message = (
                f"💰 <b>Баланс</b>\n\n"
                f"💵 <b>Текущий баланс:</b> {format_currency(current_balance)}\n\n"
                f"Выберите действие:"
            )
            await update.message.reply_text(
                message,
                reply_markup=self.admin_keyboard,
                parse_mode='HTML'
            )
        else:
            # Regular user menu
            await update.message.reply_text(
                f"💰 <b>Баланс</b>\n\n"
                f"💵 <b>Текущий баланс:</b> {format_currency(current_balance)}\n\n"
                f"Выберите действие:",
                reply_markup=self.main_keyboard,
                parse_mode='HTML'
            )
    
    async def show_balance_data(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Show balance data for selected period"""
        period = context.user_data.get('balance_period', 'day')
        await self._show_balance_data(update, context, period)
    
    async def set_period_day(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Set period to day and show data"""
        context.user_data['balance_period'] = 'day'
        await self._show_balance_data(update, context, 'day')
    
    async def set_period_week(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Set period to week and show data"""
        context.user_data['balance_period'] = 'week'
        await self._show_balance_data(update, context, 'week')
    
    async def set_period_month(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Set period to month and show data"""
        context.user_data['balance_period'] = 'month'
        await self._show_balance_data(update, context, 'month')
    
    async def refresh_data(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Refresh balance data"""
        period = context.user_data.get('balance_period', 'day')
        await self._show_balance_data(update, context, period, refresh=True)
    
    async def _show_balance_data(self, update: Update, context: ContextTypes.DEFAULT_TYPE, period: str, refresh: bool = False) -> None:
        """Show balance data for specified period"""
        try:
            # Get date range based on period
            if period == 'day':
                start_date, end_date, period_name = self._get_day_range()
            elif period == 'week':
                start_date, end_date, period_name = self._get_week_range()
            elif period == 'month':
                start_date, end_date, period_name = self._get_month_range()
            else:
                start_date, end_date, period_name = self._get_day_range()
            
            # Get data from database
            with get_session() as session:
                # Get sales
                sales = session.query(Sale).filter(
                    Sale.created_at >= start_date,
                    Sale.created_at <= end_date
                ).all()
                
                # Get expenses
                expenses = session.query(Expense).filter(
                    Expense.created_at >= start_date,
                    Expense.created_at <= end_date
                ).all()
                
                # Extract data to simple structures before session closes
                sales_data = [
                    {
                        'product_name': sale.product_name,
                        'quantity': int(sale.quantity),
                        'total_amount': float(sale.total_amount),
                        'created_at': sale.created_at.date()
                    }
                    for sale in sales
                ]
                
                expenses_data = [
                    {
                        'category': expense.category,
                        'amount': float(expense.amount),
                        'created_at': expense.created_at.date()
                    }
                    for expense in expenses
                ]
                
                # Calculate totals
                total_sales = sum(sale['total_amount'] for sale in sales_data)
                total_expenses = sum(expense['amount'] for expense in expenses_data)
                profit = total_sales - total_expenses
                
                # Get additional statistics
                sales_count = len(sales_data)
                expenses_count = len(expenses_data)
                avg_sale = total_sales / sales_count if sales_count > 0 else 0
                avg_expense = total_expenses / expenses_count if expenses_count > 0 else 0
            
            # Create message
            refresh_text = "🔄 " if refresh else ""
            message = f"{refresh_text}💰 <b>Баланс - {period_name}</b>\n\n"
            
            # Period info
            if period == 'day':
                message += f"📅 <b>Дата:</b> {start_date.strftime('%d.%m.%Y')}\n"
            elif period == 'week':
                message += f"📅 <b>Период:</b> {start_date.strftime('%d.%m')} - {end_date.strftime('%d.%m.%Y')}\n"
            elif period == 'month':
                message += f"📅 <b>Месяц:</b> {start_date.strftime('%B %Y')}\n"
            
            message += "\n"
            
            # Sales section
            message += f"💰 <b>ПРОДАЖИ:</b>\n"
            message += f"• Сумма: {format_currency(total_sales)}\n"
            message += f"• Количество: {sales_count}\n"
            if sales_count > 0:
                message += f"• Средняя продажа: {format_currency(avg_sale)}\n"
            message += "\n"
            
            # Expenses section
            message += f"💸 <b>РАСХОДЫ:</b>\n"
            message += f"• Сумма: {format_currency(total_expenses)}\n"
            message += f"• Количество: {expenses_count}\n"
            if expenses_count > 0:
                message += f"• Средний расход: {format_currency(avg_expense)}\n"
            message += "\n"
            
            # Profit section
            message += f"📈 <b>ПРИБЫЛЬ:</b>\n"
            message += f"• Итого: {format_currency(profit)}\n"
            
            # Profit status
            if profit > 0:
                message += "✅ Положительная прибыль"
            elif profit < 0:
                message += "❌ Убыток"
            else:
                message += "⚖️ Нулевой результат"
            
            # Additional insights
            if period == 'day' and sales_count > 0:
                # Show top products for day
                product_sales = {}
                for sale in sales_data:
                    if sale['product_name'] not in product_sales:
                        product_sales[sale['product_name']] = {'quantity': 0, 'amount': 0}
                    product_sales[sale['product_name']]['quantity'] += sale['quantity']
                    product_sales[sale['product_name']]['amount'] += sale['total_amount']
                
                top_products = sorted(product_sales.items(), key=lambda x: x[1]['amount'], reverse=True)[:3]
                if top_products:
                    message += f"\n\n🏆 <b>Топ товаров:</b>\n"
                    for product, stats in top_products:
                        message += f"• {product}: {stats['quantity']} шт. = {format_currency(stats['amount'])}\n"
            
            elif period == 'week' and sales_count > 0:
                # Show daily breakdown for week
                daily_data = {}
                for i in range(7):
                    day = end_date - timedelta(days=i)
                    daily_data[day] = {'sales': 0, 'expenses': 0, 'profit': 0}
                
                for sale in sales_data:
                    day = sale['created_at']
                    if day in daily_data:
                        daily_data[day]['sales'] += sale['total_amount']
                
                for expense in expenses_data:
                    day = expense['created_at']
                    if day in daily_data:
                        daily_data[day]['expenses'] += expense['amount']
                
                for day in daily_data:
                    daily_data[day]['profit'] = daily_data[day]['sales'] - daily_data[day]['expenses']
                
                message += f"\n\n📅 <b>По дням:</b>\n"
                for i in range(7):
                    day = end_date - timedelta(days=i)
                    data = daily_data[day]
                    profit_emoji = "✅" if data['profit'] > 0 else "❌" if data['profit'] < 0 else "⚖️"
                    message += f"• {day.strftime('%d.%m')}: {profit_emoji} {format_currency(data['profit'])}\n"
            
            elif period == 'month' and sales_count > 0:
                # Show top products and categories for month
                product_sales = {}
                for sale in sales_data:
                    if sale['product_name'] not in product_sales:
                        product_sales[sale['product_name']] = {'quantity': 0, 'amount': 0}
                    product_sales[sale['product_name']]['quantity'] += sale['quantity']
                    product_sales[sale['product_name']]['amount'] += sale['total_amount']
                
                top_products = sorted(product_sales.items(), key=lambda x: x[1]['amount'], reverse=True)[:3]
                if top_products:
                    message += f"\n\n🏆 <b>Топ товаров:</b>\n"
                    for product, stats in top_products:
                        message += f"• {product}: {stats['quantity']} шт. = {format_currency(stats['amount'])}\n"
                
                # Show top expense categories
                category_expenses = {}
                for expense in expenses_data:
                    if expense['category'] not in category_expenses:
                        category_expenses[expense['category']] = 0
                    category_expenses[expense['category']] += expense['amount']
                
                top_categories = sorted(category_expenses.items(), key=lambda x: x[1], reverse=True)[:3]
                if top_categories:
                    message += f"\n📂 <b>Топ расходов:</b>\n"
                    for category, amount in top_categories:
                        message += f"• {category}: {format_currency(amount)}\n"
            
            # Show period selection buttons
            await update.message.reply_text(
                message,
                reply_markup=self.period_keyboard,
                parse_mode='HTML'
            )
            
        except Exception as e:
            await update.message.reply_text(
                f"❌ Ошибка при получении данных: {str(e)}\n\n"
                "Попробуйте обновить данные.",
                reply_markup=self.main_keyboard
            )
    
    def _get_day_range(self) -> tuple:
        """Get date range for day period"""
        today = datetime.now().date()
        start_date = today
        end_date = today
        period_name = f"День ({today.strftime('%d.%m.%Y')})"
        return start_date, end_date, period_name
    
    def _get_week_range(self) -> tuple:
        """Get date range for week period"""
        end_date = datetime.now().date()
        start_date = end_date - timedelta(days=7)
        period_name = f"Неделя ({start_date.strftime('%d.%m')} - {end_date.strftime('%d.%m.%Y')})"
        return start_date, end_date, period_name
    
    def _get_month_range(self) -> tuple:
        """Get date range for month period"""
        today = datetime.now().date()
        start_date = today.replace(day=1)
        end_date = today
        period_name = f"Месяц ({start_date.strftime('%B %Y')})"
        return start_date, end_date, period_name
    
    async def get_current_balance(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Get current balance amount"""
        user_id = update.effective_user.id
        user = getattr(context, 'user', None)
        
        # If user not in context, get from database
        if not user:
            from ..utils.helpers import AuthManager
            user = AuthManager.get_user(user_id)
        
        current_balance = self.get_current_balance_amount()
        
        # Use admin keyboard if user is admin
        keyboard = self.admin_keyboard if user and user.is_admin() else self.main_keyboard
        
        await update.message.reply_text(
            f"💰 <b>Текущий баланс</b>\n\n"
            f"💵 <b>Баланс:</b> {format_currency(current_balance)}",
            reply_markup=keyboard,
            parse_mode='HTML'
        )
    
    async def get_transaction_history(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Get transaction history"""
        user_id = update.effective_user.id
        user = getattr(context, 'user', None)
        
        # If user not in context, get from database
        if not user:
            from ..utils.helpers import AuthManager
            user = AuthManager.get_user(user_id)
        
        with get_session() as session:
            # Get recent transactions
            recent_balance = session.query(Balance).order_by(
                Balance.created_at.desc()
            ).limit(20).all()
            
            if not recent_balance:
                keyboard = self.admin_keyboard if user and user.is_admin() else self.main_keyboard
                await update.message.reply_text(
                    "📊 <b>История операций</b>\n\n"
                    "Операций не найдено",
                    reply_markup=keyboard,
                    parse_mode='HTML'
                )
                return
            
            # Extract data to simple structures before session closes
            balance_data = [
                {
                    'amount': float(record.amount),
                    'transaction_type': record.transaction_type,
                    'description': record.description,
                    'created_at': record.created_at
                }
                for record in recent_balance
            ]
        
        # Build message outside session context
        message = f"📊 <b>История операций</b>\n\n"
        
        for record in balance_data:
            amount_str = format_currency(record['amount'])
            if record['transaction_type'] == 'income':
                message += f"✅ {amount_str} - {record['description']}\n"
            else:
                message += f"❌ {amount_str} - {record['description']}\n"
            
            message += f"   {record['created_at'].strftime('%d.%m.%Y %H:%M')}\n\n"
        
        keyboard = self.admin_keyboard if user and user.is_admin() else self.main_keyboard
        await update.message.reply_text(
            message,
            reply_markup=keyboard,
            parse_mode='HTML'
        )
    
    async def add_income(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Add income transaction (admin only)"""
        user_id = update.effective_user.id
        user = getattr(context, 'user', None)
        
        # If user not in context, get from database
        if not user:
            from ..utils.helpers import AuthManager
            user = AuthManager.get_user(user_id)
        
        # Check if user is admin
        if not user or not user.is_admin():
            await update.message.reply_text(
                "❌ Эта операция доступна только администраторам.",
                reply_markup=self.admin_keyboard if user and user.is_admin() else self.main_keyboard
            )
            return
        
        await update.message.reply_text(
            "💵 <b>Пополнение баланса</b>\n\n"
            "Введите данные в формате:\n"
            "<code>Сумма | Описание</code>\n\n"
            "Пример: <code>100000 | Пополнение кассы</code>",
            parse_mode='HTML'
        )
        context.user_data['state'] = 'waiting_income_data'
    
    async def add_expense_transaction(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Add expense transaction (admin only)"""
        user_id = update.effective_user.id
        user = getattr(context, 'user', None)
        
        # If user not in context, get from database
        if not user:
            from ..utils.helpers import AuthManager
            user = AuthManager.get_user(user_id)
        
        # Check if user is admin
        if not user or not user.is_admin():
            await update.message.reply_text(
                "❌ Эта операция доступна только администраторам.",
                reply_markup=self.admin_keyboard if user and user.is_admin() else self.main_keyboard
            )
            return
        
        await update.message.reply_text(
            "💸 <b>Снятие средств</b>\n\n"
            "Введите данные в формате:\n"
            "<code>Сумма | Описание</code>\n\n"
            "Пример: <code>50000 | Снятие наличных</code>",
            parse_mode='HTML'
        )
        context.user_data['state'] = 'waiting_expense_transaction_data'
    
    async def process_income_data(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Process income data input (admin only)"""
        user_id = update.effective_user.id
        user = getattr(context, 'user', None)
        
        # If user not in context, get from database
        if not user:
            from ..utils.helpers import AuthManager
            user = AuthManager.get_user(user_id)
        
        # Check if user is admin
        if not user or not user.is_admin():
            await update.message.reply_text(
                "❌ Эта операция доступна только администраторам.",
                reply_markup=self.admin_keyboard if user and user.is_admin() else self.main_keyboard
            )
            context.user_data.pop('state', None)
            return
        
        try:
            data = update.message.text.strip()
            parts = [part.strip() for part in data.split('|')]
            
            if len(parts) != 2:
                raise ValueError("Неверный формат данных")
            
            amount, description = parts
            amount = float(amount)
            
            if amount <= 0:
                raise ValueError("Сумма должна быть положительной")
            
            # Save to database
            with get_session() as session:
                balance_record = Balance(
                    amount=amount,
                    transaction_type='income',
                    description=description
                )
                session.add(balance_record)
                session.commit()
            
            # Get updated balance
            current_balance = self.get_current_balance_amount()
            
            await update.message.reply_text(
                f"✅ <b>Баланс пополнен!</b>\n\n"
                f"💵 <b>Сумма пополнения:</b> {format_currency(amount)}\n"
                f"📝 <b>Описание:</b> {description}\n\n"
                f"💰 <b>Текущий баланс:</b> {format_currency(current_balance)}",
                reply_markup=self.admin_keyboard,
                parse_mode='HTML'
            )
            
            context.user_data.pop('state', None)
            
        except Exception as e:
            user_id = update.effective_user.id
            user = getattr(context, 'user', None)
            if not user:
                from ..utils.helpers import AuthManager
                user = AuthManager.get_user(user_id)
            keyboard = self.admin_keyboard if user and user.is_admin() else self.main_keyboard
            await update.message.reply_text(
                f"❌ Ошибка: {str(e)}\n\n"
                "Попробуйте еще раз в правильном формате.",
                reply_markup=keyboard
            )
    
    async def process_expense_transaction_data(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Process expense transaction data input (admin only)"""
        user_id = update.effective_user.id
        user = getattr(context, 'user', None)
        
        # If user not in context, get from database
        if not user:
            from ..utils.helpers import AuthManager
            user = AuthManager.get_user(user_id)
        
        # Check if user is admin
        if not user or not user.is_admin():
            await update.message.reply_text(
                "❌ Эта операция доступна только администраторам.",
                reply_markup=self.admin_keyboard if user and user.is_admin() else self.main_keyboard
            )
            context.user_data.pop('state', None)
            return
        
        try:
            data = update.message.text.strip()
            parts = [part.strip() for part in data.split('|')]
            
            if len(parts) != 2:
                raise ValueError("Неверный формат данных")
            
            amount, description = parts
            amount = float(amount)
            
            if amount <= 0:
                raise ValueError("Сумма должна быть положительной")
            
            # Save to database
            with get_session() as session:
                balance_record = Balance(
                    amount=amount,
                    transaction_type='expense',
                    description=description
                )
                session.add(balance_record)
                session.commit()
            
            # Get updated balance
            current_balance = self.get_current_balance_amount()
            
            await update.message.reply_text(
                f"✅ <b>Средства сняты!</b>\n\n"
                f"💸 <b>Сумма снятия:</b> {format_currency(amount)}\n"
                f"📝 <b>Описание:</b> {description}\n\n"
                f"💰 <b>Текущий баланс:</b> {format_currency(current_balance)}",
                reply_markup=self.admin_keyboard,
                parse_mode='HTML'
            )
            
            context.user_data.pop('state', None)
            
        except Exception as e:
            user_id = update.effective_user.id
            user = getattr(context, 'user', None)
            if not user:
                from ..utils.helpers import AuthManager
                user = AuthManager.get_user(user_id)
            keyboard = self.admin_keyboard if user and user.is_admin() else self.main_keyboard
            await update.message.reply_text(
                f"❌ Ошибка: {str(e)}\n\n"
                "Попробуйте еще раз в правильном формате.",
                reply_markup=keyboard
            )