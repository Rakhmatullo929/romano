"""
Report generation service for Romano Bot
"""
from datetime import datetime, timedelta
from typing import Dict, List, Tuple
from decimal import Decimal

from ..models.schema import Sale, Expense, Balance
from ..services.database import get_session
from ..utils.helpers import format_currency


class ReportGenerator:
    """Service for generating various reports"""
    
    def __init__(self):
        pass
    
    def generate_daily_report(self, date: datetime = None) -> Dict:
        """Generate daily report"""
        if date is None:
            date = datetime.now()
        
        target_date = date.date()
        
        with get_session() as session:
            # Get sales for the day
            sales = session.query(Sale).filter(
                Sale.created_at >= target_date,
                Sale.created_at < target_date + timedelta(days=1)
            ).all()
            
            # Get expenses for the day
            expenses = session.query(Expense).filter(
                Expense.created_at >= target_date,
                Expense.created_at < target_date + timedelta(days=1)
            ).all()
            
            # Calculate totals
            total_sales = sum(sale.total_amount for sale in sales)
            total_expenses = sum(expense.amount for expense in expenses)
            profit = total_sales - total_expenses
            
            # Group sales by product
            product_sales = {}
            for sale in sales:
                if sale.product_name not in product_sales:
                    product_sales[sale.product_name] = {
                        'quantity': 0,
                        'amount': Decimal('0')
                    }
                product_sales[sale.product_name]['quantity'] += sale.quantity
                product_sales[sale.product_name]['amount'] += sale.total_amount
            
            # Group expenses by category
            category_expenses = {}
            for expense in expenses:
                if expense.category not in category_expenses:
                    category_expenses[expense.category] = Decimal('0')
                category_expenses[expense.category] += expense.amount
            
            return {
                'date': target_date,
                'sales': {
                    'count': len(sales),
                    'total_amount': total_sales,
                    'by_product': product_sales
                },
                'expenses': {
                    'count': len(expenses),
                    'total_amount': total_expenses,
                    'by_category': category_expenses
                },
                'profit': profit
            }
    
    def generate_weekly_report(self, end_date: datetime = None) -> Dict:
        """Generate weekly report"""
        if end_date is None:
            end_date = datetime.now()
        
        start_date = end_date - timedelta(days=7)
        
        with get_session() as session:
            # Get sales for the week
            sales = session.query(Sale).filter(
                Sale.created_at >= start_date,
                Sale.created_at <= end_date
            ).all()
            
            # Get expenses for the week
            expenses = session.query(Expense).filter(
                Expense.created_at >= start_date,
                Expense.created_at <= end_date
            ).all()
            
            # Calculate totals
            total_sales = sum(sale.total_amount for sale in sales)
            total_expenses = sum(expense.amount for expense in expenses)
            profit = total_sales - total_expenses
            
            # Daily breakdown
            daily_data = {}
            for i in range(7):
                day = end_date.date() - timedelta(days=i)
                daily_data[day] = {
                    'sales': Decimal('0'),
                    'expenses': Decimal('0'),
                    'profit': Decimal('0')
                }
            
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
            
            return {
                'start_date': start_date.date(),
                'end_date': end_date.date(),
                'total_sales': total_sales,
                'total_expenses': total_expenses,
                'total_profit': profit,
                'daily_breakdown': daily_data
            }
    
    def generate_monthly_report(self, year: int = None, month: int = None) -> Dict:
        """Generate monthly report"""
        if year is None or month is None:
            now = datetime.now()
            year = now.year
            month = now.month
        
        start_date = datetime(year, month, 1)
        if month == 12:
            end_date = datetime(year + 1, 1, 1)
        else:
            end_date = datetime(year, month + 1, 1)
        
        with get_session() as session:
            # Get sales for the month
            sales = session.query(Sale).filter(
                Sale.created_at >= start_date,
                Sale.created_at < end_date
            ).all()
            
            # Get expenses for the month
            expenses = session.query(Expense).filter(
                Expense.created_at >= start_date,
                Expense.created_at < end_date
            ).all()
            
            # Calculate totals
            total_sales = sum(sale.total_amount for sale in sales)
            total_expenses = sum(expense.amount for expense in expenses)
            profit = total_sales - total_expenses
            
            # Top products
            product_sales = {}
            for sale in sales:
                if sale.product_name not in product_sales:
                    product_sales[sale.product_name] = {
                        'quantity': 0,
                        'amount': Decimal('0')
                    }
                product_sales[sale.product_name]['quantity'] += sale.quantity
                product_sales[sale.product_name]['amount'] += sale.total_amount
            
            top_products = sorted(
                product_sales.items(),
                key=lambda x: x[1]['amount'],
                reverse=True
            )[:10]
            
            # Top expense categories
            category_expenses = {}
            for expense in expenses:
                if expense.category not in category_expenses:
                    category_expenses[expense.category] = Decimal('0')
                category_expenses[expense.category] += expense.amount
            
            top_categories = sorted(
                category_expenses.items(),
                key=lambda x: x[1],
                reverse=True
            )[:10]
            
            return {
                'year': year,
                'month': month,
                'total_sales': total_sales,
                'total_expenses': total_expenses,
                'total_profit': profit,
                'top_products': top_products,
                'top_expense_categories': top_categories
            }
    
    def generate_financial_summary(self) -> Dict:
        """Generate comprehensive financial summary"""
        with get_session() as session:
            # Get all-time data
            all_sales = session.query(Sale).all()
            all_expenses = session.query(Expense).all()
            
            # Calculate totals
            total_sales = sum(sale.total_amount for sale in all_sales)
            total_expenses = sum(expense.amount for expense in all_expenses)
            total_profit = total_sales - total_expenses
            
            # Get current month data
            now = datetime.now()
            month_start = datetime(now.year, now.month, 1)
            
            month_sales = session.query(Sale).filter(
                Sale.created_at >= month_start
            ).all()
            month_expenses = session.query(Expense).filter(
                Expense.created_at >= month_start
            ).all()
            
            month_sales_amount = sum(sale.total_amount for sale in month_sales)
            month_expenses_amount = sum(expense.amount for expense in month_expenses)
            month_profit = month_sales_amount - month_expenses_amount
            
            # Get today's data
            today = now.date()
            today_sales = session.query(Sale).filter(
                Sale.created_at >= today
            ).all()
            today_expenses = session.query(Expense).filter(
                Expense.created_at >= today
            ).all()
            
            today_sales_amount = sum(sale.total_amount for sale in today_sales)
            today_expenses_amount = sum(expense.amount for expense in today_expenses)
            today_profit = today_sales_amount - today_expenses_amount
            
            return {
                'all_time': {
                    'sales': total_sales,
                    'expenses': total_expenses,
                    'profit': total_profit
                },
                'current_month': {
                    'sales': month_sales_amount,
                    'expenses': month_expenses_amount,
                    'profit': month_profit
                },
                'today': {
                    'sales': today_sales_amount,
                    'expenses': today_expenses_amount,
                    'profit': today_profit
                }
            }
