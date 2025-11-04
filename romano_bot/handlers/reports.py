"""
Reports handlers for Romano Bot
"""
import os
import tempfile
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Tuple

import pandas as pd
from telegram import Update, ReplyKeyboardMarkup, InputFile
from telegram.ext import ContextTypes

from ..models.schema import Sale, Expense
from ..services.database import get_session
from ..utils.helpers import format_currency, format_date
from ..services.notifier import notify_group, format_report_notification


class ReportsHandler:
    """Handle reports generation and CSV export"""
    
    def __init__(self):
        self.main_keyboard = ReplyKeyboardMarkup([
            ['📊 Отчет за день', '📈 Отчет за неделю'],
            ['📅 Отчет за месяц', '💰 Финансовый отчет'],
            ['📥 Скачать CSV', '🔙 Главное меню']
        ], resize_keyboard=True)
        
        self.csv_keyboard = ReplyKeyboardMarkup([
            ['📊 CSV за день', '📈 CSV за неделю'],
            ['📅 CSV за месяц', '🔙 Назад к отчетам']
        ], resize_keyboard=True)
    
    async def show_reports_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Show reports menu"""
        await update.message.reply_text(
            "📊 <b>Отчеты и аналитика</b>\n\n"
            "Выберите тип отчета:",
            reply_markup=self.main_keyboard,
            parse_mode='HTML'
        )
    
    async def get_daily_report(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Generate daily report"""
        today = datetime.now().date()
        
        with get_session() as session:
            # Get sales
            sales = session.query(Sale).filter(
                Sale.created_at >= today
            ).all()
            
            # Get expenses
            expenses = session.query(Expense).filter(
                Expense.created_at >= today
            ).all()
            
            # Extract data to simple structures before session closes
            sales_data = [
                {
                    'product_name': sale.product_name,
                    'quantity': int(sale.quantity),
                    'total_amount': float(sale.total_amount),
                    'discount_amount': float(sale.discount_amount or 0),
                    'payment_method': sale.payment_method
                }
                for sale in sales
            ]
            
            expenses_data = [
                {
                    'category': expense.category,
                    'amount': float(expense.amount)
                }
                for expense in expenses
            ]
            
            # Calculate totals
            total_sales = sum(sale['total_amount'] for sale in sales_data)
            total_expenses = sum(expense['amount'] for expense in expenses_data)
            profit = total_sales - total_expenses
        
        # Build message outside session context
        message = f"📊 <b>Отчет за {today.strftime('%d.%m.%Y')}</b>\n\n"
        
        # Sales section
        message += f"💰 <b>ПРОДАЖИ:</b>\n"
        message += f"• Количество продаж: {len(sales_data)}\n"
        message += f"• Общая сумма: {format_currency(total_sales)}\n"
        message += f"• Средняя продажа: {format_currency(total_sales / len(sales_data)) if sales_data else '0'}\n\n"
        
        # Expenses section
        message += f"💸 <b>РАСХОДЫ:</b>\n"
        message += f"• Количество расходов: {len(expenses_data)}\n"
        message += f"• Общая сумма: {format_currency(total_expenses)}\n"
        message += f"• Средний расход: {format_currency(total_expenses / len(expenses_data)) if expenses_data else '0'}\n\n"
        
        # Profit section
        message += f"📈 <b>ПРИБЫЛЬ:</b>\n"
        message += f"• Общая прибыль: {format_currency(profit)}\n"
        
        if profit > 0:
            message += "✅ Положительная прибыль"
        elif profit < 0:
            message += "❌ Убыток"
        else:
            message += "⚖️ Нулевой результат"
        
        # Top products
        if sales_data:
            product_sales = {}
            for sale in sales_data:
                if sale['product_name'] not in product_sales:
                    product_sales[sale['product_name']] = {'quantity': 0, 'amount': 0}
                product_sales[sale['product_name']]['quantity'] += sale['quantity']
                product_sales[sale['product_name']]['amount'] += sale['total_amount']
            
            top_products = sorted(product_sales.items(), key=lambda x: x[1]['amount'], reverse=True)[:3]
            message += f"\n\n🏆 <b>Топ товаров:</b>\n"
            for product, stats in top_products:
                message += f"• {product}: {stats['quantity']} шт. = {format_currency(stats['amount'])}\n"
        
        # Top expense categories
        if expenses_data:
            category_expenses = {}
            for expense in expenses_data:
                if expense['category'] not in category_expenses:
                    category_expenses[expense['category']] = 0
                category_expenses[expense['category']] += expense['amount']
            
            top_categories = sorted(category_expenses.items(), key=lambda x: x[1], reverse=True)[:3]
            message += f"\n📂 <b>Топ расходов:</b>\n"
            for category, amount in top_categories:
                message += f"• {category}: {format_currency(amount)}\n"
        
        # Payment methods breakdown
        if sales_data:
            payment_methods = {}
            for sale in sales_data:
                if sale['payment_method'] not in payment_methods:
                    payment_methods[sale['payment_method']] = 0
                payment_methods[sale['payment_method']] += sale['total_amount']
            
            message += f"\n💳 <b>По способам оплаты:</b>\n"
            for method, amount in payment_methods.items():
                percentage = (amount / total_sales * 100) if total_sales > 0 else 0
                method_emoji = {
                    'наличные': '💵',
                    'карта': '💳',
                    'перевод': '📱'
                }.get(method, '💳')
                message += f"• {method_emoji} {method}: {format_currency(amount)} ({percentage:.1f}%)\n"
        
        # Discounts summary
        if sales_data:
            total_discount = sum(sale['discount_amount'] for sale in sales_data)
            sales_with_discount = len([s for s in sales_data if s['discount_amount'] > 0])
            if total_discount > 0:
                message += f"\n🎯 <b>Скидки:</b>\n"
                message += f"• Продаж со скидкой: {sales_with_discount} из {len(sales_data)}\n"
                message += f"• Общая сумма скидок: {format_currency(total_discount)}\n"
                message += f"• Средняя скидка: {format_currency(total_discount / sales_with_discount) if sales_with_discount > 0 else '0'}\n"
            
            await update.message.reply_text(
                message,
                reply_markup=self.main_keyboard,
                parse_mode='HTML'
            )
    
    async def get_weekly_report(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Generate weekly report"""
        end_date = datetime.now().date()
        start_date = end_date - timedelta(days=7)
        
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
                    'total_amount': float(sale.total_amount),
                    'created_at': sale.created_at.date()
                }
                for sale in sales
            ]
            
            expenses_data = [
                {
                    'amount': float(expense.amount),
                    'created_at': expense.created_at.date()
                }
                for expense in expenses
            ]
            
            # Calculate totals
            total_sales = sum(sale['total_amount'] for sale in sales_data)
            total_expenses = sum(expense['amount'] for expense in expenses_data)
            profit = total_sales - total_expenses
        
        # Build message outside session context
        message = f"📈 <b>Отчет за неделю</b>\n"
        message += f"({start_date.strftime('%d.%m')} - {end_date.strftime('%d.%m.%Y')})\n\n"
        
        # Summary
        message += f"💰 <b>ПРОДАЖИ:</b> {format_currency(total_sales)}\n"
        message += f"💸 <b>РАСХОДЫ:</b> {format_currency(total_expenses)}\n"
        message += f"📈 <b>ПРИБЫЛЬ:</b> {format_currency(profit)}\n\n"
        
        # Daily breakdown
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
        
        message += "📅 <b>По дням:</b>\n"
        for i in range(7):
            day = end_date - timedelta(days=i)
            data = daily_data[day]
            profit_emoji = "✅" if data['profit'] > 0 else "❌" if data['profit'] < 0 else "⚖️"
            message += f"• {day.strftime('%d.%m')}: {profit_emoji} {format_currency(data['profit'])}\n"
        
        await update.message.reply_text(
            message,
            reply_markup=self.main_keyboard,
            parse_mode='HTML'
        )
    
    async def get_monthly_report(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Generate monthly report"""
        today = datetime.now().date()
        month_start = today.replace(day=1)
        
        with get_session() as session:
            # Get sales
            sales = session.query(Sale).filter(
                Sale.created_at >= month_start,
                Sale.created_at <= today
            ).all()
            
            # Get expenses
            expenses = session.query(Expense).filter(
                Expense.created_at >= month_start,
                Expense.created_at <= today
            ).all()
            
            # Extract data to simple structures before session closes
            sales_data = [
                {
                    'product_name': sale.product_name,
                    'quantity': int(sale.quantity),
                    'total_amount': float(sale.total_amount),
                    'discount_amount': float(sale.discount_amount or 0),
                    'payment_method': sale.payment_method
                }
                for sale in sales
            ]
            
            expenses_data = [
                {
                    'category': expense.category,
                    'amount': float(expense.amount)
                }
                for expense in expenses
            ]
            
            # Calculate totals
            total_sales = sum(sale['total_amount'] for sale in sales_data)
            total_expenses = sum(expense['amount'] for expense in expenses_data)
            profit = total_sales - total_expenses
        
        # Build message outside session context
        message = f"📅 <b>Отчет за месяц</b>\n"
        message += f"({month_start.strftime('%B %Y')})\n\n"
        
        # Summary
        message += f"💰 <b>ПРОДАЖИ:</b> {format_currency(total_sales)}\n"
        message += f"💸 <b>РАСХОДЫ:</b> {format_currency(total_expenses)}\n"
        message += f"📈 <b>ПРИБЫЛЬ:</b> {format_currency(profit)}\n\n"
        
        # Statistics
        message += f"📊 <b>Статистика:</b>\n"
        message += f"• Продаж: {len(sales_data)}\n"
        message += f"• Расходов: {len(expenses_data)}\n"
        message += f"• Средняя продажа: {format_currency(total_sales / len(sales_data)) if sales_data else '0'}\n"
        message += f"• Средний расход: {format_currency(total_expenses / len(expenses_data)) if expenses_data else '0'}\n\n"
        
        # Top products
        if sales_data:
            product_sales = {}
            for sale in sales_data:
                if sale['product_name'] not in product_sales:
                    product_sales[sale['product_name']] = {'quantity': 0, 'amount': 0}
                product_sales[sale['product_name']]['quantity'] += sale['quantity']
                product_sales[sale['product_name']]['amount'] += sale['total_amount']
            
            top_products = sorted(product_sales.items(), key=lambda x: x[1]['amount'], reverse=True)[:5]
            message += f"🏆 <b>Топ товаров:</b>\n"
            for product, stats in top_products:
                message += f"• {product}: {stats['quantity']} шт. = {format_currency(stats['amount'])}\n"
        
        # Top expense categories
        if expenses_data:
            category_expenses = {}
            for expense in expenses_data:
                if expense['category'] not in category_expenses:
                    category_expenses[expense['category']] = 0
                category_expenses[expense['category']] += expense['amount']
            
            top_categories = sorted(category_expenses.items(), key=lambda x: x[1], reverse=True)[:5]
            message += f"\n📂 <b>Топ расходов:</b>\n"
            for category, amount in top_categories:
                message += f"• {category}: {format_currency(amount)}\n"
        
        # Payment methods breakdown
        if sales_data:
            payment_methods = {}
            for sale in sales_data:
                if sale['payment_method'] not in payment_methods:
                    payment_methods[sale['payment_method']] = 0
                payment_methods[sale['payment_method']] += sale['total_amount']
            
            message += f"\n💳 <b>По способам оплаты:</b>\n"
            for method, amount in payment_methods.items():
                percentage = (amount / total_sales * 100) if total_sales > 0 else 0
                method_emoji = {
                    'наличные': '💵',
                    'карта': '💳',
                    'перевод': '📱'
                }.get(method, '💳')
                message += f"• {method_emoji} {method}: {format_currency(amount)} ({percentage:.1f}%)\n"
        
        # Discounts summary
        if sales_data:
            total_discount = sum(sale['discount_amount'] for sale in sales_data)
            sales_with_discount = len([s for s in sales_data if s['discount_amount'] > 0])
            if total_discount > 0:
                message += f"\n🎯 <b>Скидки за месяц:</b>\n"
                message += f"• Продаж со скидкой: {sales_with_discount} из {len(sales_data)}\n"
                message += f"• Общая сумма скидок: {format_currency(total_discount)}\n"
                message += f"• Средняя скидка: {format_currency(total_discount / sales_with_discount) if sales_with_discount > 0 else '0'}\n"
        
        await update.message.reply_text(
            message,
            reply_markup=self.main_keyboard,
            parse_mode='HTML'
        )
    
    async def get_financial_report(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Generate comprehensive financial report"""
        today = datetime.now().date()
        
        with get_session() as session:
            # Get all-time data
            all_sales = session.query(Sale).all()
            all_expenses = session.query(Expense).all()
            
            # Extract all-time data to simple structures
            all_sales_data = [
                {
                    'product_name': sale.product_name,
                    'quantity': int(sale.quantity),
                    'total_amount': float(sale.total_amount)
                }
                for sale in all_sales
            ]
            
            all_expenses_data = [
                {
                    'amount': float(expense.amount)
                }
                for expense in all_expenses
            ]
            
            # Calculate totals
            total_sales = sum(sale['total_amount'] for sale in all_sales_data)
            total_expenses = sum(expense['amount'] for expense in all_expenses_data)
            total_profit = total_sales - total_expenses
            
            # Get current month data
            month_start = today.replace(day=1)
            month_sales = session.query(Sale).filter(
                Sale.created_at >= month_start
            ).all()
            month_expenses = session.query(Expense).filter(
                Expense.created_at >= month_start
            ).all()
            
            # Extract month data
            month_sales_data = [
                {'total_amount': float(sale.total_amount)}
                for sale in month_sales
            ]
            month_expenses_data = [
                {'amount': float(expense.amount)}
                for expense in month_expenses
            ]
            
            month_sales_amount = sum(sale['total_amount'] for sale in month_sales_data)
            month_expenses_amount = sum(expense['amount'] for expense in month_expenses_data)
            month_profit = month_sales_amount - month_expenses_amount
            
            # Get today's data
            today_sales = session.query(Sale).filter(
                Sale.created_at >= today
            ).all()
            today_expenses = session.query(Expense).filter(
                Expense.created_at >= today
            ).all()
            
            # Extract today data
            today_sales_data = [
                {'total_amount': float(sale.total_amount)}
                for sale in today_sales
            ]
            today_expenses_data = [
                {'amount': float(expense.amount)}
                for expense in today_expenses
            ]
            
            today_sales_amount = sum(sale['total_amount'] for sale in today_sales_data)
            today_expenses_amount = sum(expense['amount'] for expense in today_expenses_data)
            today_profit = today_sales_amount - today_expenses_amount
        
        # Build message outside session context
        message = f"💰 <b>Финансовый отчет</b>\n\n"
        
        # All time
        message += f"📊 <b>За все время:</b>\n"
        message += f"• Продажи: {format_currency(total_sales)}\n"
        message += f"• Расходы: {format_currency(total_expenses)}\n"
        message += f"• Прибыль: {format_currency(total_profit)}\n\n"
        
        # Current month
        message += f"📅 <b>За текущий месяц:</b>\n"
        message += f"• Продажи: {format_currency(month_sales_amount)}\n"
        message += f"• Расходы: {format_currency(month_expenses_amount)}\n"
        message += f"• Прибыль: {format_currency(month_profit)}\n\n"
        
        # Today
        message += f"📆 <b>За сегодня:</b>\n"
        message += f"• Продажи: {format_currency(today_sales_amount)}\n"
        message += f"• Расходы: {format_currency(today_expenses_amount)}\n"
        message += f"• Прибыль: {format_currency(today_profit)}\n\n"
        
        # Top products all time
        if all_sales_data:
            product_sales = {}
            for sale in all_sales_data:
                if sale['product_name'] not in product_sales:
                    product_sales[sale['product_name']] = {'quantity': 0, 'amount': 0}
                product_sales[sale['product_name']]['quantity'] += sale['quantity']
                product_sales[sale['product_name']]['amount'] += sale['total_amount']
            
            top_products = sorted(product_sales.items(), key=lambda x: x[1]['amount'], reverse=True)[:5]
            message += f"🏆 <b>Топ товаров (все время):</b>\n"
            for product, stats in top_products:
                message += f"• {product}: {stats['quantity']} шт. = {format_currency(stats['amount'])}\n"
        
        await update.message.reply_text(
            message,
            reply_markup=self.main_keyboard,
            parse_mode='HTML'
        )
    
    async def show_csv_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Show CSV download menu"""
        await update.message.reply_text(
            "📥 <b>Скачать отчеты в CSV</b>\n\n"
            "Выберите период для скачивания:",
            reply_markup=self.csv_keyboard,
            parse_mode='HTML'
        )
    
    async def download_daily_csv(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Download daily report as CSV"""
        today = datetime.now().date()
        
        with get_session() as session:
            # Get sales
            sales = session.query(Sale).filter(
                Sale.created_at >= today
            ).all()
            
            # Get expenses
            expenses = session.query(Expense).filter(
                Expense.created_at >= today
            ).all()
            
            # Extract data to simple structures before session closes
            sales_data = [
                {
                    'created_at': sale.created_at,
                    'product_name': sale.product_name,
                    'quantity': int(sale.quantity),
                    'unit_price': float(sale.unit_price),
                    'discount_percent': float(sale.discount_percent or 0),
                    'discount_amount': float(sale.discount_amount or 0),
                    'subtotal': float(sale.subtotal),
                    'total_amount': float(sale.total_amount),
                    'payment_method': sale.payment_method,
                    'notes': sale.notes or ''
                }
                for sale in sales
            ]
            
            expenses_data = [
                {
                    'created_at': expense.created_at,
                    'category': expense.category,
                    'description': expense.description,
                    'amount': float(expense.amount),
                    'employee_name': expense.employee_name or '',
                    'comment': expense.comment or ''
                }
                for expense in expenses
            ]
            
            # Create CSV data
            csv_data = self._create_csv_data(sales_data, expenses_data, f"Отчет за {today.strftime('%d.%m.%Y')}")
            
            # Generate and send CSV
            await self._send_csv_file(update, context, csv_data, f"daily_report_{today.strftime('%Y%m%d')}.csv")
    
    async def download_weekly_csv(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Download weekly report as CSV"""
        end_date = datetime.now().date()
        start_date = end_date - timedelta(days=7)
        
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
                    'created_at': sale.created_at,
                    'product_name': sale.product_name,
                    'quantity': int(sale.quantity),
                    'unit_price': float(sale.unit_price),
                    'discount_percent': float(sale.discount_percent or 0),
                    'discount_amount': float(sale.discount_amount or 0),
                    'subtotal': float(sale.subtotal),
                    'total_amount': float(sale.total_amount),
                    'payment_method': sale.payment_method,
                    'notes': sale.notes or ''
                }
                for sale in sales
            ]
            
            expenses_data = [
                {
                    'created_at': expense.created_at,
                    'category': expense.category,
                    'description': expense.description,
                    'amount': float(expense.amount),
                    'employee_name': expense.employee_name or '',
                    'comment': expense.comment or ''
                }
                for expense in expenses
            ]
            
            # Create CSV data
            csv_data = self._create_csv_data(sales_data, expenses_data, f"Отчет за неделю {start_date.strftime('%d.%m')} - {end_date.strftime('%d.%m.%Y')}")
            
            # Generate and send CSV
            await self._send_csv_file(update, context, csv_data, f"weekly_report_{end_date.strftime('%Y%m%d')}.csv")
    
    async def download_monthly_csv(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Download monthly report as CSV"""
        today = datetime.now().date()
        month_start = today.replace(day=1)
        
        with get_session() as session:
            # Get sales
            sales = session.query(Sale).filter(
                Sale.created_at >= month_start,
                Sale.created_at <= today
            ).all()
            
            # Get expenses
            expenses = session.query(Expense).filter(
                Expense.created_at >= month_start,
                Expense.created_at <= today
            ).all()
            
            # Extract data to simple structures before session closes
            sales_data = [
                {
                    'created_at': sale.created_at,
                    'product_name': sale.product_name,
                    'quantity': int(sale.quantity),
                    'unit_price': float(sale.unit_price),
                    'discount_percent': float(sale.discount_percent or 0),
                    'discount_amount': float(sale.discount_amount or 0),
                    'subtotal': float(sale.subtotal),
                    'total_amount': float(sale.total_amount),
                    'payment_method': sale.payment_method,
                    'notes': sale.notes or ''
                }
                for sale in sales
            ]
            
            expenses_data = [
                {
                    'created_at': expense.created_at,
                    'category': expense.category,
                    'description': expense.description,
                    'amount': float(expense.amount),
                    'employee_name': expense.employee_name or '',
                    'comment': expense.comment or ''
                }
                for expense in expenses
            ]
            
            # Create CSV data
            csv_data = self._create_csv_data(sales_data, expenses_data, f"Отчет за месяц {month_start.strftime('%B %Y')}")
            
            # Generate and send CSV
            await self._send_csv_file(update, context, csv_data, f"monthly_report_{month_start.strftime('%Y%m')}.csv")
    
    def _create_csv_data(self, sales_data: List[Dict], expenses_data: List[Dict], title: str) -> Dict:
        """Create CSV data structure"""
        # Sales data
        csv_sales = []
        for sale in sales_data:
            csv_sales.append({
                'Тип': 'Продажа',
                'Дата': sale['created_at'].strftime('%d.%m.%Y'),
                'Время': sale['created_at'].strftime('%H:%M'),
                'Продукт': sale['product_name'],
                'Количество': sale['quantity'],
                'Цена за единицу': sale['unit_price'],
                'Скидка %': sale['discount_percent'],
                'Сумма скидки': sale['discount_amount'],
                'Сумма без скидки': sale['subtotal'],
                'Итоговая сумма': sale['total_amount'],
                'Способ оплаты': sale['payment_method'],
                'Комментарий': sale['notes']
            })
        
        # Expenses data
        csv_expenses = []
        for expense in expenses_data:
            csv_expenses.append({
                'Тип': 'Расход',
                'Дата': expense['created_at'].strftime('%d.%m.%Y'),
                'Время': expense['created_at'].strftime('%H:%M'),
                'Категория': expense['category'],
                'Описание': expense['description'],
                'Сумма': expense['amount'],
                'Сотрудник': expense['employee_name'],
                'Комментарий': expense['comment']
            })
        
        # Combine data
        all_data = csv_sales + csv_expenses
        
        # Sort by date and time
        all_data.sort(key=lambda x: (x['Дата'], x['Время']))
        
        # Calculate summary
        total_sales = sum(sale['total_amount'] for sale in sales_data)
        total_expenses = sum(expense['amount'] for expense in expenses_data)
        
        return {
            'title': title,
            'data': all_data,
            'summary': {
                'total_sales': total_sales,
                'total_expenses': total_expenses,
                'profit': total_sales - total_expenses
            }
        }
    
    async def _send_csv_file(self, update: Update, context: ContextTypes.DEFAULT_TYPE, csv_data: Dict, filename: str) -> None:
        """Generate and send CSV file"""
        try:
            # Create DataFrame
            df = pd.DataFrame(csv_data['data'])
            
            # Create temporary file
            with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False, encoding='utf-8') as temp_file:
                # Write summary at the top
                summary = csv_data['summary']
                temp_file.write(f"# {csv_data['title']}\n")
                temp_file.write(f"# Общая сумма продаж: {format_currency(summary['total_sales'])}\n")
                temp_file.write(f"# Общая сумма расходов: {format_currency(summary['total_expenses'])}\n")
                temp_file.write(f"# Прибыль: {format_currency(summary['profit'])}\n")
                temp_file.write("#\n")
                
                # Write data
                df.to_csv(temp_file, index=False, encoding='utf-8')
                temp_file_path = temp_file.name
            
            # Send file
            with open(temp_file_path, 'rb') as file:
                await update.message.reply_document(
                    document=InputFile(file, filename=filename),
                    caption=f"📊 {csv_data['title']}\n\n"
                           f"💰 Продажи: {format_currency(csv_data['summary']['total_sales'])}\n"
                           f"💸 Расходы: {format_currency(csv_data['summary']['total_expenses'])}\n"
                           f"📈 Прибыль: {format_currency(csv_data['summary']['profit'])}",
                    reply_markup=self.main_keyboard
                )
            
            # Clean up
            os.unlink(temp_file_path)
            
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
            
            # Determine period type and name from filename
            period = 'day'
            period_name = csv_data['title']
            if 'weekly' in filename or 'неделю' in csv_data['title'].lower():
                period = 'week'
            elif 'monthly' in filename or 'месяц' in csv_data['title'].lower():
                period = 'month'
            
            # Send notification to group
            notification_message = format_report_notification(
                username=username,
                period=period,
                period_name=period_name
            )
            await notify_group(context, notification_message)
            
        except Exception as e:
            await update.message.reply_text(
                f"❌ Ошибка при создании CSV файла: {str(e)}\n\n"
                "Попробуйте еще раз.",
                reply_markup=self.main_keyboard
            )