#!/usr/bin/env python3
"""
Script to add админ user to Romano Bot database.

Usage:
    python add_admin.py <telegram_id> <first_name>
    
Example:
    python add_admin.py 279498964 "Админ"
"""
import sys
from romano_bot.services.database import get_session
from romano_bot.models.schema import User


def add_admin(telegram_id: int, first_name: str = "Админ"):
    """Add admin user to database"""
    with get_session() as session:
        # Check if user already exists
        existing_user = session.query(User).filter_by(telegram_id=telegram_id).first()
        
        if existing_user:
            # Update existing user to admin
            existing_user.role = User.ROLE_ADMIN
            existing_user.status = User.STATUS_ACTIVE
            existing_user.first_name = first_name
            existing_user.is_active = True
            print(f"✓ Пользователь {telegram_id} обновлён до роли админ")
        else:
            # Create new admin user
            admin_user = User(
                telegram_id=telegram_id,
                first_name=first_name,
                role=User.ROLE_ADMIN,
                status=User.STATUS_ACTIVE,
                is_active=True
            )
            session.add(admin_user)
            print(f"✓ Создан новый админ {telegram_id}")
        
        session.commit()
        print(f"\n✓ Админ {telegram_id} ({first_name}) активирован в базе данных")
        print(f"✓ Добавьте этот ID в список ADMIN_IDS в config.py: {telegram_id}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Использование: python add_admin.py <telegram_id> [first_name]")
        print("\nПример:")
        print("  python add_admin.py 279498964 Админ")
        sys.exit(1)
    
    try:
        telegram_id = int(sys.argv[1])
        first_name = sys.argv[2] if len(sys.argv) > 2 else "Админ"
        add_admin(telegram_id, first_name)
    except ValueError:
        print("❌ Error: Telegram ID must be a number")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)

