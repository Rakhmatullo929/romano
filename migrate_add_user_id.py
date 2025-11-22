#!/usr/bin/env python3
"""
Скрипт миграции для добавления поля user_id в таблицы sales и expenses.

Этот скрипт добавляет колонки user_id в существующие таблицы для поддержки
системы переключения бариста. Существующие записи получат NULL в поле user_id,
что допустимо для обратной совместимости.

Использование:
    python migrate_add_user_id.py
"""
import sys
from sqlalchemy import text
from romano_bot.services.database import db_service
from romano_bot.config import DATABASE_URL


def migrate_database() -> bool:
    """
    Выполнить миграцию базы данных.
    
    Добавляет колонки user_id в таблицы sales и expenses.
    
    Returns:
        bool: True если миграция успешна, False в случае ошибки
    """
    try:
        print("🔄 Начало миграции базы данных...")
        print(f"📊 База данных: {DATABASE_URL}")
        
        # Проверить тип базы данных
        is_sqlite = DATABASE_URL.startswith('sqlite')
        
        with db_service.engine.connect() as connection:
            # Начать транзакцию
            trans = connection.begin()
            
            try:
                # Проверить существование колонок
                if is_sqlite:
                    # Для SQLite проверяем через PRAGMA table_info
                    sales_info = connection.execute(
                        text("PRAGMA table_info(sales)")
                    ).fetchall()
                    expenses_info = connection.execute(
                        text("PRAGMA table_info(expenses)")
                    ).fetchall()
                    
                    sales_columns = [col[1] for col in sales_info]
                    expenses_columns = [col[1] for col in expenses_info]
                else:
                    # Для других БД используем INFORMATION_SCHEMA
                    # Это упрощенная версия, может потребоваться адаптация
                    print("⚠️  Для не-SQLite БД может потребоваться ручная миграция")
                    sales_columns = []
                    expenses_columns = []
                
                # Добавить user_id в таблицу sales, если его нет
                if 'user_id' not in sales_columns:
                    print("➕ Добавление колонки user_id в таблицу sales...")
                    if is_sqlite:
                        connection.execute(
                            text("ALTER TABLE sales ADD COLUMN user_id INTEGER")
                        )
                        # Добавить внешний ключ (SQLite поддерживает это ограниченно)
                        try:
                            connection.execute(
                                text("""
                                    CREATE TRIGGER IF NOT EXISTS sales_user_id_fk
                                    BEFORE INSERT ON sales
                                    FOR EACH ROW
                                    WHEN NEW.user_id IS NOT NULL
                                    BEGIN
                                        SELECT CASE
                                            WHEN NOT EXISTS (
                                                SELECT 1 FROM users WHERE id = NEW.user_id
                                            ) THEN
                                                RAISE(ABORT, 'Foreign key constraint failed')
                                        END;
                                    END;
                                """)
                            )
                        except Exception as e:
                            print(f"⚠️  Не удалось создать триггер для внешнего ключа: {e}")
                            print("   Это не критично, внешний ключ будет проверяться на уровне приложения")
                    else:
                        connection.execute(
                            text("ALTER TABLE sales ADD COLUMN user_id INTEGER REFERENCES users(id)")
                        )
                    print("✅ Колонка user_id добавлена в таблицу sales")
                else:
                    print("ℹ️  Колонка user_id уже существует в таблице sales")
                
                # Добавить user_id в таблицу expenses, если его нет
                if 'user_id' not in expenses_columns:
                    print("➕ Добавление колонки user_id в таблицу expenses...")
                    if is_sqlite:
                        connection.execute(
                            text("ALTER TABLE expenses ADD COLUMN user_id INTEGER")
                        )
                        # Добавить внешний ключ через триггер
                        try:
                            connection.execute(
                                text("""
                                    CREATE TRIGGER IF NOT EXISTS expenses_user_id_fk
                                    BEFORE INSERT ON expenses
                                    FOR EACH ROW
                                    WHEN NEW.user_id IS NOT NULL
                                    BEGIN
                                        SELECT CASE
                                            WHEN NOT EXISTS (
                                                SELECT 1 FROM users WHERE id = NEW.user_id
                                            ) THEN
                                                RAISE(ABORT, 'Foreign key constraint failed')
                                        END;
                                    END;
                                """)
                            )
                        except Exception as e:
                            print(f"⚠️  Не удалось создать триггер для внешнего ключа: {e}")
                            print("   Это не критично, внешний ключ будет проверяться на уровне приложения")
                    else:
                        connection.execute(
                            text("ALTER TABLE expenses ADD COLUMN user_id INTEGER REFERENCES users(id)")
                        )
                    print("✅ Колонка user_id добавлена в таблицу expenses")
                else:
                    print("ℹ️  Колонка user_id уже существует в таблице expenses")
                
                # Закоммитить транзакцию
                trans.commit()
                print("\n✅ Миграция успешно завершена!")
                print("📝 Существующие записи имеют user_id = NULL (это нормально)")
                print("📝 Новые операции будут автоматически привязываться к активному бариста")
                return True
                
            except Exception as e:
                trans.rollback()
                print(f"\n❌ Ошибка при миграции: {e}")
                print("🔄 Изменения отменены (rollback)")
                return False
                
    except Exception as e:
        print(f"\n❌ Критическая ошибка миграции: {e}")
        return False


if __name__ == "__main__":
    print("=" * 60)
    print("Миграция базы данных: добавление user_id")
    print("=" * 60)
    print()
    
    success = migrate_database()
    
    if success:
        print("\n" + "=" * 60)
        print("✅ Миграция завершена успешно!")
        print("=" * 60)
        sys.exit(0)
    else:
        print("\n" + "=" * 60)
        print("❌ Миграция завершилась с ошибками")
        print("=" * 60)
        sys.exit(1)

