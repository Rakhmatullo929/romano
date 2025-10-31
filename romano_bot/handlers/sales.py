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

from ..models.schema import Sale
from ..services.database import get_session
from ..utils.helpers import format_currency, logger
from ..config import PRODUCT_PRICES


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
        
        self.products_keyboard = ReplyKeyboardMarkup([
            ['☕ Американо', '☕ Капучино'],
            ['☕ Латте', '🍵 Чай', '🍰 Десерт'],
            ['🔙 Назад к продажам']
        ], resize_keyboard=True)
        
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
        """Start adding new sale - show products menu"""
        # Clear any previous sale data
        context.user_data.pop('sale_data', None)
        context.user_data.pop('state', None)
        
        message = "☕ <b>Выберите продукт:</b>\n\n"
        for product, price in PRODUCT_PRICES.items():
            message += f"• {product}: {format_currency(price)}\n"
        
        await update.message.reply_text(
            message,
            reply_markup=self.products_keyboard,
            parse_mode='HTML'
        )
        context.user_data['state'] = 'selecting_product'
    
    async def handle_product_selection(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle product selection"""
        product_text = update.message.text
        
        # Map emoji buttons to product names
        product_mapping = {
            '☕ Американо': 'Американо',
            '☕ Капучино': 'Капучино', 
            '☕ Латте': 'Латте',
            '🍵 Чай': 'Чай',
            '🍰 Десерт': 'Десерт'
        }
        
        # Check if it's a valid product selection
        if product_text not in product_mapping:
            await update.message.reply_text(
                "❌ Неверный выбор продукта. Попробуйте еще раз.",
                reply_markup=self.products_keyboard
            )
            return
        
        # Get the actual product name without emoji
        product_name = product_mapping[product_text]
        
        # Store product selection
        context.user_data['sale_data'] = {
            'product_name': product_name,
            'unit_price': PRODUCT_PRICES[product_name]
        }
        
        await update.message.reply_text(
            f"☕ <b>Выбран продукт:</b> {product_name}\n"
            f"💰 <b>Цена:</b> {format_currency(PRODUCT_PRICES[product_name])}\n\n"
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
            await update.message.reply_text(
                "Введите процент скидки (от 1 до 50):",
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
        """Handle discount percentage input"""
        user_id = update.effective_user.id
        logger.info(f"Handling discount input for user {user_id}: {update.message.text}")
        
        try:
            discount_percent = float(update.message.text.strip())
            
            if discount_percent < 0 or discount_percent > 50:
                raise ValueError("Скидка должна быть от 0 до 50 процентов")
            
            # Calculate discount
            subtotal = context.user_data['sale_data']['subtotal']
            discount_amount = subtotal * (discount_percent / 100)
            total_amount = subtotal - discount_amount
            
            # Store discount data
            context.user_data['sale_data']['discount_percent'] = discount_percent
            context.user_data['sale_data']['discount_amount'] = discount_amount
            context.user_data['sale_data']['total_amount'] = total_amount
            
            await update.message.reply_text(
                f"🎯 <b>Скидка:</b> {discount_percent}%\n"
                f"💰 <b>Сумма скидки:</b> {format_currency(discount_amount)}\n"
                f"💵 <b>Итого к оплате:</b> {format_currency(total_amount)}\n\n"
                "Выберите способ оплаты:",
                reply_markup=self.payment_keyboard,
                parse_mode='HTML'
            )
            context.user_data['state'] = 'selecting_payment'
            
        except ValueError as e:
            await update.message.reply_text(
                f"❌ Ошибка: {str(e)}\n\n"
                "Введите корректный процент скидки (от 0 до 50):",
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
        message += f"☕ <b>Продукт:</b> {sale_data['product_name']}\n"
        message += f"📦 <b>Количество:</b> {sale_data['quantity']} шт.\n"
        message += f"💰 <b>Цена за единицу:</b> {format_currency(sale_data['unit_price'])}\n"
        message += f"💵 <b>Сумма без скидки:</b> {format_currency(sale_data['subtotal'])}\n"
        
        if sale_data.get('discount_percent', 0) > 0:
            message += f"🎯 <b>Скидка:</b> {sale_data['discount_percent']}%\n"
            message += f"💸 <b>Сумма скидки:</b> {format_currency(sale_data['discount_amount'])}\n"
        
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
                session.commit()
            
            # Success message
            message = "✅ <b>Продажа успешно добавлена!</b>\n\n"
            message += f"☕ <b>Продукт:</b> {sale_data['product_name']}\n"
            message += f"📦 <b>Количество:</b> {sale_data['quantity']} шт.\n"
            message += f"💵 <b>Итого:</b> {format_currency(sale_data['total_amount'])}\n"
            message += f"💳 <b>Оплата:</b> {sale_data['payment_method']}\n"
            message += f"🕐 <b>Время:</b> {datetime.now().strftime('%d.%m.%Y %H:%M')}"
            
            await update.message.reply_text(
                message,
                reply_markup=self.main_keyboard,
                parse_mode='HTML'
            )
            
            # Clear sale data
            context.user_data.pop('sale_data', None)
            context.user_data.pop('state', None)
            
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
            
            total_amount = sum(sale.total_amount for sale in sales)
            total_quantity = sum(sale.quantity for sale in sales)
            total_discount = sum(sale.discount_amount or 0 for sale in sales)
            
            message = f"📊 <b>Продажи за сегодня</b>\n"
            message += f"({today.strftime('%d.%m.%Y')})\n\n"
            message += f"📈 <b>Общая статистика:</b>\n"
            message += f"• Количество продаж: {len(sales)}\n"
            message += f"• Общее количество товаров: {total_quantity}\n"
            message += f"• Общая сумма: {format_currency(total_amount)}\n"
            message += f"• Общая скидка: {format_currency(total_discount)}\n\n"
            
            # Group by product
            product_stats = {}
            for sale in sales:
                if sale.product_name not in product_stats:
                    product_stats[sale.product_name] = {
                        'quantity': 0,
                        'amount': 0
                    }
                product_stats[sale.product_name]['quantity'] += sale.quantity
                product_stats[sale.product_name]['amount'] += sale.total_amount
            
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
            
            total_amount = sum(sale.total_amount for sale in sales)
            total_quantity = sum(sale.quantity for sale in sales)
            
            message = f"📈 <b>Продажи за неделю</b>\n"
            message += f"({start_date.strftime('%d.%m')} - {end_date.strftime('%d.%m.%Y')})\n\n"
            message += f"📊 <b>Общая статистика:</b>\n"
            message += f"• Количество продаж: {len(sales)}\n"
            message += f"• Общее количество товаров: {total_quantity}\n"
            message += f"• Общая сумма: {format_currency(total_amount)}\n"
            message += f"• Средняя продажа: {format_currency(total_amount / len(sales))}\n\n"
            
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
            
            total_amount = sum(sale.total_amount for sale in sales)
            total_quantity = sum(sale.quantity for sale in sales)
            
            message = f"📅 <b>Продажи за месяц</b>\n"
            message += f"({month_start.strftime('%B %Y')})\n\n"
            message += f"📊 <b>Общая статистика:</b>\n"
            message += f"• Количество продаж: {len(sales)}\n"
            message += f"• Общее количество товаров: {total_quantity}\n"
            message += f"• Общая сумма: {format_currency(total_amount)}\n"
            message += f"• Средняя продажа: {format_currency(total_amount / len(sales))}\n\n"
            
            await update.message.reply_text(
                message,
                reply_markup=self.main_keyboard,
                parse_mode='HTML'
            )