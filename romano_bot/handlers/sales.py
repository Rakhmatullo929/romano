"""
Sales handlers for Romano Bot

This module handles all sales-related operations including product selection,
quantity input, discount application, payment method selection, and confirmation.

Author: Romano Bot Team
Version: 1.0.0
"""
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import ContextTypes
from decimal import Decimal
from datetime import datetime

from ..models.schema import Sale, Balance
from ..services.database import get_session
from ..utils.helpers import format_currency, logger
from ..config import PRODUCT_PRICES, MENU_CATEGORIES
from ..services.notifier import notify_group, format_sale_notification


class SalesHandler:
    """
    Handle sales-related operations.
    
    Manages the complete sales flow from product selection to confirmation,
    including discount application and payment method selection.
    """
    
    def __init__(self):
        self.main_keyboard = ReplyKeyboardMarkup([
            ['💰 Добавить продажу', '📊 Продажи за день'],
            ['📈 Продажи за неделю', '📅 Продажи за месяц'],
            ['🔙 Главное меню']
        ], resize_keyboard=True)
        
        # Build categories keyboard dynamically
        categories = list(MENU_CATEGORIES.keys())
        categories_buttons = []
        for i in range(0, len(categories), 2):
            row = categories[i:i+2]
            categories_buttons.append(row)
        categories_buttons.append(['🔙 Назад к продажам'])
        self.categories_keyboard = ReplyKeyboardMarkup(categories_buttons, resize_keyboard=True)
        
        self.discount_keyboard = ReplyKeyboardMarkup([
            ['✅ Да', '❌ Нет'],
            ['🔙 Назад к продажам']
        ], resize_keyboard=True)
        
        self.payment_keyboard = ReplyKeyboardMarkup([
            ['💵 Наличные', '💳 Карта'],
            ['📱 Перевод', '🔙 Назад к продажам']
        ], resize_keyboard=True)
        
        self.confirm_keyboard = ReplyKeyboardMarkup([
            ['✅ Подтвердить', '❌ Отменить'],
            ['🔙 Назад к продажам']
        ], resize_keyboard=True)
    
    async def show_sales_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Show sales menu"""
        user_id = update.effective_user.id
        
        try:
            logger.info(f"User {user_id} opened sales menu")
            await update.message.reply_text(
                "💰 <b>Управление продажами</b>\n\n"
                "Выберите действие:",
                reply_markup=self.main_keyboard,
                parse_mode='HTML'
            )
            logger.info(f"Sales menu shown to user {user_id}")
        except Exception as e:
            logger.error(f"Error showing sales menu: {str(e)}", user_id)
            await update.message.reply_text(
                "❌ Произошла ошибка. Попробуйте еще раз."
            )
    
    async def add_sale(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Start adding new sale - show categories menu"""
        # Clear any previous sale data
        context.user_data.pop('sale_data', None)
        context.user_data.pop('state', None)
        context.user_data.pop('selected_category', None)
        
        message = "📋 <b>Выберите категорию:</b>\n\n"
        for category in MENU_CATEGORIES.keys():
            product_count = len(MENU_CATEGORIES[category])
            message += f"• {category} ({product_count} товаров)\n"
        
        await update.message.reply_text(
            message,
            reply_markup=self.categories_keyboard,
            parse_mode='HTML'
        )
        context.user_data['state'] = 'selecting_category'
    
    async def handle_category_selection(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle category selection - show products in selected category"""
        category_name = update.message.text
        
        # Check if user wants to go back to sales menu
        if category_name == '🔙 Назад к продажам':
            context.user_data.pop('selected_category', None)
            context.user_data.pop('state', None)
            await self.show_sales_menu(update, context)
            return
        
        # Check if it's a valid category
        if category_name not in MENU_CATEGORIES:
            await update.message.reply_text(
                "❌ Неверный выбор категории. Попробуйте еще раз.",
                reply_markup=self.categories_keyboard
            )
            return
        
        # Store selected category
        context.user_data['selected_category'] = category_name
        products = MENU_CATEGORIES[category_name]
        
        # Build products keyboard
        product_buttons = []
        product_list = list(products.keys())
        for i in range(0, len(product_list), 2):
            row = product_list[i:i+2]
            product_buttons.append(row)
        product_buttons.append(['🔙 Назад к категориям'])
        products_keyboard = ReplyKeyboardMarkup(product_buttons, resize_keyboard=True)
        
        # Show products with prices
        message = f"📋 <b>Категория: {category_name}</b>\n\n"
        message += "<b>Выберите товар:</b>\n\n"
        for product, price in products.items():
            message += f"• {product}: {format_currency(price)}\n"
        
        await update.message.reply_text(
            message,
            reply_markup=products_keyboard,
            parse_mode='HTML'
        )
        context.user_data['state'] = 'selecting_product'
    
    async def handle_product_selection(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle product selection"""
        product_name = update.message.text
        selected_category = context.user_data.get('selected_category')
        
        # Check if user wants to go back to categories
        if product_name == '🔙 Назад к категориям':
            await self.add_sale(update, context)
            return
        
        # Validate category exists
        if not selected_category or selected_category not in MENU_CATEGORIES:
            await update.message.reply_text(
                "❌ Ошибка: категория не выбрана. Начните заново.",
                reply_markup=self.categories_keyboard
            )
            context.user_data.pop('selected_category', None)
            context.user_data['state'] = 'selecting_category'
            return
        
        # Check if product exists in selected category
        products = MENU_CATEGORIES[selected_category]
        if product_name not in products:
            # Build products keyboard again
            product_buttons = []
            product_list = list(products.keys())
            for i in range(0, len(product_list), 2):
                row = product_list[i:i+2]
                product_buttons.append(row)
            product_buttons.append(['🔙 Назад к категориям'])
            products_keyboard = ReplyKeyboardMarkup(product_buttons, resize_keyboard=True)
            
            await update.message.reply_text(
                "❌ Неверный выбор товара. Попробуйте еще раз.",
                reply_markup=products_keyboard
            )
            return
        
        # Store product selection
        context.user_data['sale_data'] = {
            'category': selected_category,
            'product_name': product_name,
            'unit_price': products[product_name]
        }
        
        await update.message.reply_text(
            f"📋 <b>Категория:</b> {selected_category}\n"
            f"☕ <b>Выбран товар:</b> {product_name}\n"
            f"💰 <b>Цена:</b> {format_currency(products[product_name])}\n\n"
            "Введите количество (в штуках):",
            reply_markup=ReplyKeyboardRemove(),
            parse_mode='HTML'
        )
        context.user_data['state'] = 'entering_quantity'
    
    async def handle_quantity_input(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle quantity input"""
        try:
            quantity = int(update.message.text.strip())
            
            if quantity <= 0:
                raise ValueError("Количество должно быть больше 0")
            
            if quantity > 100:
                raise ValueError("Максимальное количество: 100 штук")
            
            # Store quantity
            context.user_data['sale_data']['quantity'] = quantity
            
            # Calculate subtotal
            subtotal = context.user_data['sale_data']['unit_price'] * quantity
            context.user_data['sale_data']['subtotal'] = subtotal
            
            await update.message.reply_text(
                f"📦 <b>Количество:</b> {quantity} шт.\n"
                f"💰 <b>Сумма без скидки:</b> {format_currency(subtotal)}\n\n"
                "Применить скидку?",
                reply_markup=self.discount_keyboard,
                parse_mode='HTML'
            )
            context.user_data['state'] = 'asking_discount'
            
        except ValueError as e:
            await update.message.reply_text(
                f"❌ Ошибка: {str(e)}\n\n"
                "Введите корректное количество (число от 1 до 100):",
                reply_markup=ReplyKeyboardRemove()
            )
    
    async def handle_discount_choice(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle discount choice"""
        user_id = update.effective_user.id
        choice = update.message.text
        
        logger.info(f"User {user_id} discount choice: {choice}")
        
        if choice == "✅ Да":
            subtotal = context.user_data['sale_data']['subtotal']
            await update.message.reply_text(
                f"Введите сумму скидки (максимум {format_currency(subtotal)}):",
                reply_markup=ReplyKeyboardRemove()
            )
            context.user_data['state'] = 'entering_discount'
            logger.info(f"Set state to 'entering_discount' for user {user_id}")
        elif choice == "❌ Нет":
            # No discount, proceed to payment method
            context.user_data['sale_data']['discount_percent'] = 0
            context.user_data['sale_data']['discount_amount'] = 0
            context.user_data['sale_data']['total_amount'] = context.user_data['sale_data']['subtotal']
            
            await self._show_payment_selection(update, context)
        else:
            await update.message.reply_text(
                "❌ Неверный выбор. Выберите Да или Нет:",
                reply_markup=self.discount_keyboard
            )
    
    async def handle_discount_input(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle discount amount input"""
        user_id = update.effective_user.id
        logger.info(f"Handling discount input for user {user_id}: {update.message.text}")
        
        try:
            discount_amount = float(update.message.text.strip())
            subtotal = context.user_data['sale_data']['subtotal']
            
            if discount_amount < 0:
                raise ValueError("Скидка не может быть отрицательной")
            
            if discount_amount > subtotal:
                raise ValueError(f"Скидка не может быть больше суммы без скидки ({format_currency(subtotal)})")
            
            # Calculate total amount
            total_amount = subtotal - discount_amount
            
            if total_amount < 0:
                raise ValueError("Итоговая сумма не может быть отрицательной")
            
            # Store discount data
            context.user_data['sale_data']['discount_percent'] = 0  # Не используем проценты, но сохраняем для совместимости
            context.user_data['sale_data']['discount_amount'] = discount_amount
            context.user_data['sale_data']['total_amount'] = total_amount
            
            await update.message.reply_text(
                f"🎯 <b>Сумма скидки:</b> {format_currency(discount_amount)}\n"
                f"💰 <b>Сумма без скидки:</b> {format_currency(subtotal)}\n"
                f"💵 <b>Итого к оплате:</b> {format_currency(total_amount)}\n\n"
                "Выберите способ оплаты:",
                reply_markup=self.payment_keyboard,
                parse_mode='HTML'
            )
            context.user_data['state'] = 'selecting_payment'
            
        except ValueError as e:
            subtotal = context.user_data['sale_data']['subtotal']
            await update.message.reply_text(
                f"❌ Ошибка: {str(e)}\n\n"
                f"Введите корректную сумму скидки (максимум {format_currency(subtotal)}):",
                reply_markup=ReplyKeyboardRemove()
            )
        except Exception as e:
            subtotal = context.user_data['sale_data']['subtotal']
            await update.message.reply_text(
                f"❌ Ошибка: Введите корректное число.\n\n"
                f"Введите сумму скидки (максимум {format_currency(subtotal)}):",
                reply_markup=ReplyKeyboardRemove()
            )
    
    async def handle_payment_selection(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle payment method selection"""
        payment_method = update.message.text
        
        if payment_method not in ['💵 Наличные', '💳 Карта', '📱 Перевод']:
            await update.message.reply_text(
                "❌ Неверный выбор способа оплаты. Попробуйте еще раз:",
                reply_markup=self.payment_keyboard
            )
            return
        
        # Map emoji to text
        payment_map = {
            '💵 Наличные': 'наличные',
            '💳 Карта': 'карта',
            '📱 Перевод': 'перевод'
        }
        
        context.user_data['sale_data']['payment_method'] = payment_map[payment_method]
        
        # Show confirmation
        await self._show_confirmation(update, context)
    
    async def _show_payment_selection(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Show payment method selection"""
        await update.message.reply_text(
            "💳 <b>Выберите способ оплаты:</b>",
            reply_markup=self.payment_keyboard,
            parse_mode='HTML'
        )
        context.user_data['state'] = 'selecting_payment'
    
    async def _show_confirmation(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Show sale confirmation"""
        sale_data = context.user_data['sale_data']
        
        message = "📋 <b>Подтверждение продажи</b>\n\n"
        if sale_data.get('category'):
            message += f"📋 <b>Категория:</b> {sale_data['category']}\n"
        message += f"☕ <b>Товар:</b> {sale_data['product_name']}\n"
        message += f"📦 <b>Количество:</b> {sale_data['quantity']} шт.\n"
        message += f"💰 <b>Цена за единицу:</b> {format_currency(sale_data['unit_price'])}\n"
        message += f"💵 <b>Сумма без скидки:</b> {format_currency(sale_data['subtotal'])}\n"
        
        if sale_data.get('discount_amount', 0) > 0:
            message += f"🎯 <b>Сумма скидки:</b> {format_currency(sale_data['discount_amount'])}\n"
        
        message += f"💳 <b>Способ оплаты:</b> {sale_data['payment_method']}\n"
        message += f"💵 <b>Итого к оплате:</b> {format_currency(sale_data['total_amount'])}\n\n"
        message += "Подтвердить продажу?"
        
        await update.message.reply_text(
            message,
            reply_markup=self.confirm_keyboard,
            parse_mode='HTML'
        )
        context.user_data['state'] = 'confirming_sale'
    
    async def handle_sale_confirmation(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle sale confirmation"""
        choice = update.message.text
        
        if choice == "✅ Подтвердить":
            await self._save_sale(update, context)
        elif choice == "❌ Отменить":
            await update.message.reply_text(
                "❌ Продажа отменена.",
                reply_markup=self.main_keyboard
            )
            context.user_data.pop('sale_data', None)
            context.user_data.pop('state', None)
            context.user_data.pop('selected_category', None)
        else:
            await update.message.reply_text(
                "❌ Неверный выбор. Подтвердите или отмените продажу:",
                reply_markup=self.confirm_keyboard
            )
    
    async def _save_sale(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Save sale to database"""
        try:
            sale_data = context.user_data['sale_data']
            
            with get_session() as session:
                sale = Sale(
                    product_name=sale_data['product_name'],
                    quantity=sale_data['quantity'],
                    unit_price=sale_data['unit_price'],
                    discount_percent=sale_data.get('discount_percent', 0),
                    discount_amount=sale_data.get('discount_amount', 0),
                    subtotal=sale_data['subtotal'],
                    total_amount=sale_data['total_amount'],
                    payment_method=sale_data['payment_method']
                )
                session.add(sale)
                session.flush()  # Flush to get sale.id
                
                # Create balance transaction for sale
                balance_record = Balance(
                    amount=sale_data['total_amount'],
                    transaction_type='income',
                    description=f"Продажа: {sale_data['product_name']} ({sale_data['quantity']} шт.)",
                    reference_id=sale.id,
                    reference_type='sale'
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
            
            # Send notification to group
            sale_timestamp = datetime.now()
            notification_message = format_sale_notification(
                username=username,
                product_name=sale_data['product_name'],
                quantity=sale_data['quantity'],
                total_price=sale_data['total_amount'],
                timestamp=sale_timestamp
            )
            await notify_group(context, notification_message)
            
            # Get current balance
            from .balance import BalanceHandler
            balance_handler = BalanceHandler()
            current_balance = balance_handler.get_current_balance_amount()
            
            # Success message
            message = "✅ <b>Продажа успешно добавлена!</b>\n\n"
            if sale_data.get('category'):
                message += f"📋 <b>Категория:</b> {sale_data['category']}\n"
            message += f"☕ <b>Товар:</b> {sale_data['product_name']}\n"
            message += f"📦 <b>Количество:</b> {sale_data['quantity']} шт.\n"
            message += f"💵 <b>Итого:</b> {format_currency(sale_data['total_amount'])}\n"
            message += f"💳 <b>Оплата:</b> {sale_data['payment_method']}\n"
            message += f"🕐 <b>Время:</b> {sale_timestamp.strftime('%d.%m.%Y %H:%M')}\n\n"
            message += f"💰 <b>Текущий баланс:</b> {format_currency(current_balance)}"
            
            await update.message.reply_text(
                message,
                reply_markup=self.main_keyboard,
                parse_mode='HTML'
            )
            
            # Clear sale data
            context.user_data.pop('sale_data', None)
            context.user_data.pop('state', None)
            context.user_data.pop('selected_category', None)
            
        except Exception as e:
            await update.message.reply_text(
                f"❌ Ошибка при сохранении продажи: {str(e)}\n\n"
                "Попробуйте еще раз.",
                reply_markup=self.main_keyboard
            )
    
    async def get_daily_sales(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Get daily sales report"""
        today = datetime.now().date()
        
        with get_session() as session:
            sales = session.query(Sale).filter(
                Sale.created_at >= today
            ).all()
            
            if not sales:
                await update.message.reply_text(
                    "📊 <b>Продажи за сегодня</b>\n\n"
                    "Продаж не было",
                    reply_markup=self.main_keyboard,
                    parse_mode='HTML'
                )
                return
            
            # Extract data to simple structures before session closes
            sales_data = [
                {
                    'product_name': sale.product_name,
                    'quantity': int(sale.quantity),
                    'total_amount': float(sale.total_amount),
                    'discount_amount': float(sale.discount_amount or 0)
                }
                for sale in sales
            ]
        
        # Build message outside session context
        total_amount = sum(sale['total_amount'] for sale in sales_data)
        total_quantity = sum(sale['quantity'] for sale in sales_data)
        total_discount = sum(sale['discount_amount'] for sale in sales_data)
        
        message = f"📊 <b>Продажи за сегодня</b>\n"
        message += f"({today.strftime('%d.%m.%Y')})\n\n"
        message += f"📈 <b>Общая статистика:</b>\n"
        message += f"• Количество продаж: {len(sales_data)}\n"
        message += f"• Общее количество товаров: {total_quantity}\n"
        message += f"• Общая сумма: {format_currency(total_amount)}\n"
        message += f"• Общая скидка: {format_currency(total_discount)}\n\n"
        
        # Group by product
        product_stats = {}
        for sale in sales_data:
            if sale['product_name'] not in product_stats:
                product_stats[sale['product_name']] = {
                    'quantity': 0,
                    'amount': 0
                }
            product_stats[sale['product_name']]['quantity'] += sale['quantity']
            product_stats[sale['product_name']]['amount'] += sale['total_amount']
        
        message += "📦 <b>По продуктам:</b>\n"
        for product, stats in product_stats.items():
            message += f"• {product}: {stats['quantity']} шт. = {format_currency(stats['amount'])}\n"
        
        await update.message.reply_text(
            message,
            reply_markup=self.main_keyboard,
            parse_mode='HTML'
        )
    
    async def get_weekly_sales(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Get weekly sales report"""
        from datetime import timedelta
        
        end_date = datetime.now().date()
        start_date = end_date - timedelta(days=7)
        
        with get_session() as session:
            sales = session.query(Sale).filter(
                Sale.created_at >= start_date,
                Sale.created_at <= end_date
            ).all()
            
            if not sales:
                await update.message.reply_text(
                    "📈 <b>Продажи за неделю</b>\n\n"
                    "Продаж не было",
                    reply_markup=self.main_keyboard,
                    parse_mode='HTML'
                )
                return
            
            # Extract data to simple structures before session closes
            sales_data = [
                {
                    'quantity': int(sale.quantity),
                    'total_amount': float(sale.total_amount)
                }
                for sale in sales
            ]
        
        # Build message outside session context
        total_amount = sum(sale['total_amount'] for sale in sales_data)
        total_quantity = sum(sale['quantity'] for sale in sales_data)
        
        message = f"📈 <b>Продажи за неделю</b>\n"
        message += f"({start_date.strftime('%d.%m')} - {end_date.strftime('%d.%m.%Y')})\n\n"
        message += f"📊 <b>Общая статистика:</b>\n"
        message += f"• Количество продаж: {len(sales_data)}\n"
        message += f"• Общее количество товаров: {total_quantity}\n"
        message += f"• Общая сумма: {format_currency(total_amount)}\n"
        message += f"• Средняя продажа: {format_currency(total_amount / len(sales_data))}\n\n"
        
        await update.message.reply_text(
            message,
            reply_markup=self.main_keyboard,
            parse_mode='HTML'
        )
    
    async def get_monthly_sales(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Get monthly sales report"""
        from datetime import timedelta
        
        today = datetime.now().date()
        month_start = today.replace(day=1)
        
        with get_session() as session:
            sales = session.query(Sale).filter(
                Sale.created_at >= month_start,
                Sale.created_at <= today
            ).all()
            
            if not sales:
                await update.message.reply_text(
                    "📅 <b>Продажи за месяц</b>\n\n"
                    "Продаж не было",
                    reply_markup=self.main_keyboard,
                    parse_mode='HTML'
                )
                return
            
            # Extract data to simple structures before session closes
            sales_data = [
                {
                    'quantity': int(sale.quantity),
                    'total_amount': float(sale.total_amount)
                }
                for sale in sales
            ]
        
        # Build message outside session context
        total_amount = sum(sale['total_amount'] for sale in sales_data)
        total_quantity = sum(sale['quantity'] for sale in sales_data)
        
        message = f"📅 <b>Продажи за месяц</b>\n"
        message += f"({month_start.strftime('%B %Y')})\n\n"
        message += f"📊 <b>Общая статистика:</b>\n"
        message += f"• Количество продаж: {len(sales_data)}\n"
        message += f"• Общее количество товаров: {total_quantity}\n"
        message += f"• Общая сумма: {format_currency(total_amount)}\n"
        message += f"• Средняя продажа: {format_currency(total_amount / len(sales_data))}\n\n"
        
        await update.message.reply_text(
            message,
            reply_markup=self.main_keyboard,
            parse_mode='HTML'
        )