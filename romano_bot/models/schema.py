"""
Database models for Romano Bot

This module contains SQLAlchemy models for the Romano Coffee Shop bot database.
Defines tables for sales, expenses, balance tracking, and user management.

Author: Romano Bot Team
Version: 1.0.0
"""
from datetime import datetime
from decimal import Decimal
from sqlalchemy import Column, Integer, String, DateTime, Numeric, Text, Boolean, ForeignKey
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()


class Sale(Base):
    """
    Sales transactions model.
    
    Stores information about coffee shop sales including product details,
    quantities, prices, discounts, and payment methods.
    """
    __tablename__ = 'sales'
    
    id = Column(Integer, primary_key=True)
    product_name = Column(String(255), nullable=False)
    quantity = Column(Integer, nullable=False, default=1)
    unit_price = Column(Numeric(10, 2), nullable=False)
    discount_percent = Column(Numeric(5, 2), nullable=True, default=0)  # Скидка в процентах
    discount_amount = Column(Numeric(10, 2), nullable=True, default=0)  # Сумма скидки
    subtotal = Column(Numeric(10, 2), nullable=False)  # Сумма без скидки
    total_amount = Column(Numeric(10, 2), nullable=False)  # Итоговая сумма
    payment_method = Column(String(50), nullable=False)  # cash, card, transfer
    notes = Column(Text, nullable=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=True)  # ID бариста, выполнившего продажу
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Expense(Base):
    """
    Expenses model.
    
    Stores information about coffee shop expenses including categories,
    descriptions, amounts, and employee information for salary payments.
    """
    __tablename__ = 'expenses'
    
    id = Column(Integer, primary_key=True)
    category = Column(String(100), nullable=False)  # Закуп, Зарплата, Списание
    description = Column(String(255), nullable=False)
    amount = Column(Numeric(10, 2), nullable=False)
    comment = Column(Text, nullable=True)  # Дополнительные заметки
    employee_name = Column(String(100), nullable=True)  # Для зарплаты
    payment_method = Column(String(50), nullable=True)  # Опционально
    user_id = Column(Integer, ForeignKey('users.id'), nullable=True)  # ID бариста, выполнившего расход
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)


class Balance(Base):
    """
    Balance tracking model.
    
    Stores financial transactions for balance tracking including
    income, expenses, and reference information.
    """
    __tablename__ = 'balance'
    
    id = Column(Integer, primary_key=True)
    amount = Column(Numeric(10, 2), nullable=False)
    transaction_type = Column(String(20), nullable=False)  # income, expense
    description = Column(String(255), nullable=False)
    reference_id = Column(Integer, nullable=True)  # ID of sale or expense
    reference_type = Column(String(20), nullable=True)  # 'sale' or 'expense'
    created_at = Column(DateTime, default=datetime.utcnow)


class User(Base):
    """
    Users model for role-based access control.
    
    Stores user information with roles (админ, бариста) and activity tracking.
    """
    __tablename__ = 'users'
    
    # User roles (stored in Russian for clarity)
    ROLE_ADMIN = 'админ'
    ROLE_BARISTA = 'бариста'
    ROLE_ADMIN_LEGACY = 'admin'
    ROLE_BARISTA_LEGACY = 'barista'
    
    # User statuses
    STATUS_ACTIVE = 'active'
    STATUS_INACTIVE = 'inactive'
    STATUS_PENDING = 'pending'
    
    id = Column(Integer, primary_key=True)
    telegram_id = Column(Integer, unique=True, nullable=False)
    username = Column(String(100), nullable=True)
    first_name = Column(String(100), nullable=True)
    last_name = Column(String(100), nullable=True)
    role = Column(
        String(20),
        nullable=False,
        default=ROLE_BARISTA
    )  # админ, бариста
    status = Column(String(20), nullable=False, default=STATUS_PENDING)  # active, inactive, pending
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_activity = Column(DateTime, default=datetime.utcnow)
    created_by = Column(Integer, nullable=True)  # ID of user who created this user
    
    def is_admin(self) -> bool:
        """Check if user is admin"""
        return (
            self.role in {self.ROLE_ADMIN, self.ROLE_ADMIN_LEGACY}
            and self.status == self.STATUS_ACTIVE
        )
    
    def is_barista(self) -> bool:
        """Check if user is barista"""
        return (
            self.role in {self.ROLE_BARISTA, self.ROLE_BARISTA_LEGACY}
            and self.status == self.STATUS_ACTIVE
        )
    
    def can_manage_users(self) -> bool:
        """Check if user can manage other users"""
        return self.is_admin()
    
    def can_view_reports(self) -> bool:
        """Check if user can view reports"""
        return self.is_admin()
    
    def can_add_sales(self) -> bool:
        """Check if user can add sales"""
        return self.is_active and self.status == self.STATUS_ACTIVE
    
    def can_add_expenses(self) -> bool:
        """Check if user can add expenses"""
        return self.is_active and self.status == self.STATUS_ACTIVE
