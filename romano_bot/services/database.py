"""
Database service for Romano Bot

This module provides database connection management and session handling
for the Romano Coffee Shop bot using SQLAlchemy ORM.

Author: Romano Bot Team
Version: 1.0.0
"""
from contextlib import contextmanager
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import SQLAlchemyError

from ..config import DATABASE_URL
from ..models.schema import Base


class DatabaseService:
    """
    Database service for managing connections and sessions.
    
    Provides database connection management, session handling, and table creation
    functionality for the Romano Coffee Shop bot.
    """
    
    def __init__(self):
        """Initialize database service with engine and session factory."""
        self.engine = create_engine(DATABASE_URL, echo=False)
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
    
    def create_tables(self) -> bool:
        """
        Create all database tables.
        
        Returns:
            bool: True if tables created successfully, False otherwise
        """
        try:
            Base.metadata.create_all(bind=self.engine)
            return True
        except SQLAlchemyError as e:
            print(f"Error creating tables: {e}")
            return False
    
    @contextmanager
    def get_session(self):
        """
        Get database session with automatic cleanup.
        
        Yields:
            Session: SQLAlchemy session object
        """
        session = self.SessionLocal()
        try:
            yield session
            session.commit()
        except Exception as e:
            session.rollback()
            raise e
        finally:
            session.close()


# Global database service instance
db_service = DatabaseService()

def get_session():
    """
    Get database session context manager.
    
    Returns:
        contextmanager: Database session context manager
    """
    return db_service.get_session()


def init_database() -> bool:
    """
    Initialize database with tables.
    
    Returns:
        bool: True if database initialized successfully, False otherwise
    """
    return db_service.create_tables()
