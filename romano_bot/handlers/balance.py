"""
Balance handlers for Romano Bot
"""
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import ContextTypes
from decimal import Decimal
from datetime import datetime, timedelta

from ..models.schema import Sale, Expense, Balance
from ..services.database import get_session
from ..utils.helpers import format_currency


class BalanceHandler:
    """Handle balance operations and period-based reporting"""
    
    def __init__(self):
        self.main_keyboard = ReplyKeyboardMarkup([
            ['📅 День', '📈 Неделя', '📊 Месяц'],
            ['🔄 Обновить данные', '📊 Сформировать отчет'],
            ['🔙 Главное меню']
        ], resize_keyboard=True)
        
        self.period_keyboard = ReplyKeyboardMarkup([
            ['📅 День', '📈 Неделя', '📊 Месяц'],
            ['🔙 Назад к балансу']
        ], resize_keyboard=True)
    
    async def show_balance_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Show balance main menu"""
        await update.message.reply_text(
            "💰 <b>Баланс</b>\n\n"
            "Выберите действие:",
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
                
                # Calculate totals
                total_sales = sum(sale.total_amount for sale in sales)
                total_expenses = sum(expense.amount for expense in expenses)
                profit = total_sales - total_expenses
                
                # Get additional statistics
                sales_count = len(sales)
                expenses_count = len(expenses)
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
                for sale in sales:
                    if sale.product_name not in product_sales:
                        product_sales[sale.product_name] = {'quantity': 0, 'amount': 0}
                    product_sales[sale.product_name]['quantity'] += sale.quantity
                    product_sales[sale.product_name]['amount'] += sale.total_amount
                
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
                
                for sale in sales:
                    day = sale.created_at.date()
                    if day in daily_data:
                        daily_data[day]['sales'] += sale.total_amount
                
                for expense in expenses:
                    day = expense.created_at.date()
                    if day in daily_data:
                        daily_data[day]['expenses'] += expense.amount
                
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
                for sale in sales:
                    if sale.product_name not in product_sales:
                        product_sales[sale.product_name] = {'quantity': 0, 'amount': 0}
                    product_sales[sale.product_name]['quantity'] += sale.quantity
                    product_sales[sale.product_name]['amount'] += sale.total_amount
                
                top_products = sorted(product_sales.items(), key=lambda x: x[1]['amount'], reverse=True)[:3]
                if top_products:
                    message += f"\n\n🏆 <b>Топ товаров:</b>\n"
                    for product, stats in top_products:
                        message += f"• {product}: {stats['quantity']} шт. = {format_currency(stats['amount'])}\n"
                
                # Show top expense categories
                category_expenses = {}
                for expense in expenses:
                    if expense.category not in category_expenses:
                        category_expenses[expense.category] = 0
                    category_expenses[expense.category] += expense.amount
                
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
        """Get current balance - show day data"""
        context.user_data['balance_period'] = 'day'
        await self._show_balance_data(update, context, 'day')
    
    async def get_transaction_history(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Get transaction history"""
        with get_session() as session:
            # Get recent transactions
            recent_balance = session.query(Balance).order_by(
                Balance.created_at.desc()
            ).limit(20).all()
            
            if not recent_balance:
                await update.message.reply_text(
                    "📊 <b>История операций</b>\n\n"
                    "Операций не найдено",
                    reply_markup=self.main_keyboard,
                    parse_mode='HTML'
                )
                return
            
            message = f"📊 <b>История операций</b>\n\n"
            
            for record in recent_balance:
                amount_str = format_currency(record.amount)
                if record.transaction_type == 'income':
                    message += f"✅ {amount_str} - {record.description}\n"
                else:
                    message += f"❌ {amount_str} - {record.description}\n"
                
                message += f"   {record.created_at.strftime('%d.%m.%Y %H:%M')}\n\n"
            
            await update.message.reply_text(
                message,
                reply_markup=self.main_keyboard,
                parse_mode='HTML'
            )
    
    async def add_income(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Add income transaction"""
        await update.message.reply_text(
            "💵 <b>Пополнение баланса</b>\n\n"
            "Введите данные в формате:\n"
            "<code>Сумма | Описание</code>\n\n"
            "Пример: <code>100000 | Пополнение кассы</code>",
            parse_mode='HTML'
        )
        context.user_data['state'] = 'waiting_income_data'
    
    async def add_expense_transaction(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Add expense transaction"""
        await update.message.reply_text(
            "💸 <b>Снятие средств</b>\n\n"
            "Введите данные в формате:\n"
            "<code>Сумма | Описание</code>\n\n"
            "Пример: <code>50000 | Снятие наличных</code>",
            parse_mode='HTML'
        )
        context.user_data['state'] = 'waiting_expense_transaction_data'
    
    async def process_income_data(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Process income data input"""
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
            
            await update.message.reply_text(
                f"✅ <b>Доход добавлен!</b>\n\n"
                f"Сумма: {format_currency(amount)}\n"
                f"Описание: {description}",
                reply_markup=self.main_keyboard,
                parse_mode='HTML'
            )
            
            context.user_data.pop('state', None)
            
        except Exception as e:
            await update.message.reply_text(
                f"❌ Ошибка: {str(e)}\n\n"
                "Попробуйте еще раз в правильном формате.",
                reply_markup=self.main_keyboard
            )
    
    async def process_expense_transaction_data(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Process expense transaction data input"""
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
            
            await update.message.reply_text(
                f"✅ <b>Расход добавлен!</b>\n\n"
                f"Сумма: {format_currency(amount)}\n"
                f"Описание: {description}",
                reply_markup=self.main_keyboard,
                parse_mode='HTML'
            )
            
            context.user_data.pop('state', None)
            
        except Exception as e:
            await update.message.reply_text(
                f"❌ Ошибка: {str(e)}\n\n"
                "Попробуйте еще раз в правильном формате.",
                reply_markup=self.main_keyboard
            )