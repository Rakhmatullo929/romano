#!/usr/bin/env python3
"""
Script to stop all running instances of Romano Bot
"""
import os
import sys
import subprocess
import signal

def find_bot_processes():
    """Find all running bot processes"""
    try:
        result = subprocess.run(
            ['ps', 'aux'],
            capture_output=True,
            text=True
        )
        
        processes = []
        for line in result.stdout.split('\n'):
            if 'run_bot.py' in line and 'grep' not in line:
                # Parse the line to get PID
                parts = line.split()
                if len(parts) > 1:
                    pid = int(parts[1])
                    processes.append(pid)
        
        return processes
    except Exception as e:
        print(f"❌ Ошибка при поиске процессов: {e}")
        return []

def kill_processes(processes):
    """Kill all bot processes"""
    if not processes:
        print("✅ Нет запущенных экземпляров бота")
        return
    
    print(f"🔍 Найдено {len(processes)} экземпляр(ов) бота")
    
    killed = 0
    for pid in processes:
        try:
            # Try graceful shutdown first
            os.kill(pid, signal.SIGTERM)
            print(f"⏳ Отправлен сигнал завершения процессу {pid}")
            killed += 1
        except ProcessLookupError:
            print(f"⚠️  Процесс {pid} уже завершен")
        except Exception as e:
            print(f"❌ Ошибка при завершении процесса {pid}: {e}")
    
    if killed > 0:
        print(f"\n✅ Завершено {killed} процесс(ов)")
        print("⏳ Ожидание завершения...")
        
        # Wait a bit
        import time
        time.sleep(2)
        
        # Check if any are still running and force kill
        remaining = find_bot_processes()
        if remaining:
            print(f"⚠️  Принудительное завершение {len(remaining)} процесс(ов)...")
            for pid in remaining:
                try:
                    os.kill(pid, signal.SIGKILL)
                    print(f"🔪 Принудительно завершен процесс {pid}")
                except:
                    pass
        
        # Clean up lock file
        lock_file = '.bot.lock'
        if os.path.exists(lock_file):
            try:
                os.remove(lock_file)
                print("🧹 Файл блокировки удален")
            except:
                pass
        
        print("\n✅ Все экземпляры бота остановлены!")
    else:
        print("❌ Не удалось завершить процессы")

def main():
    """Main function"""
    print("=" * 50)
    print("Romano Bot - Остановка бота")
    print("=" * 50)
    
    # Check for confirmation
    processes = find_bot_processes()
    
    if not processes:
        print("✅ Нет запущенных экземпляров бота")
        sys.exit(0)
    
    print(f"\nНайдено {len(processes)} экземпляр(ов) бота:")
    for pid in processes:
        print(f"  - PID: {pid}")
    
    response = input("\nОстановить все экземпляры? (y/n): ").strip().lower()
    if response not in ['y', 'yes', 'да', '']:
        print("❌ Отменено")
        sys.exit(0)
    
    kill_processes(processes)

if __name__ == "__main__":
    main()


