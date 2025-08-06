#!/usr/bin/env python3
"""
Тестовый скрипт для проверки функций Telegram бота
"""

import sqlite3
from datetime import datetime

def test_database():
    """Тестируем создание базы данных"""
    print("🔧 Тестирование базы данных...")
    
    # Импортируем функцию из основного файла
    from bot import init_db
    
    try:
        init_db()
        print("✅ База данных создана успешно")
        
        # Проверяем таблицы
        conn = sqlite3.connect('shop.db')
        cursor = conn.cursor()
        
        # Проверяем таблицу пользователей
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users'")
        if cursor.fetchone():
            print("✅ Таблица users создана")
        
        # Проверяем таблицу товаров
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='products'")
        if cursor.fetchone():
            print("✅ Таблица products создана")
        
        # Проверяем таблицу ключей
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='keys'")
        if cursor.fetchone():
            print("✅ Таблица keys создана")
        
        # Проверяем таблицу транзакций
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='transactions'")
        if cursor.fetchone():
            print("✅ Таблица transactions создана")
        
        # Проверяем данные
        products = cursor.execute("SELECT COUNT(*) FROM products").fetchone()[0]
        keys = cursor.execute("SELECT COUNT(*) FROM keys").fetchone()[0]
        
        print(f"📦 Товаров в базе: {products}")
        print(f"🔑 Ключей в базе: {keys}")
        
        conn.close()
        
    except Exception as e:
        print(f"❌ Ошибка при создании базы данных: {e}")

def test_yoomoney_functions():
    """Тестируем функции ЮMoney"""
    print("\n💰 Тестирование функций ЮMoney...")
    
    from bot import generate_yoomoney_link
    
    try:
        # Тестируем генерацию ссылки
        link = generate_yoomoney_link(100, "test_label")
        if "yoomoney.ru" in link:
            print("✅ Генерация ссылки ЮMoney работает")
        else:
            print("❌ Ошибка в генерации ссылки")
            
    except Exception as e:
        print(f"❌ Ошибка в функциях ЮMoney: {e}")

def test_imports():
    """Тестируем импорты"""
    print("📦 Тестирование импортов...")
    
    try:
        import telegram
        print("✅ telegram импортирован")
        
        import requests
        print("✅ requests импортирован")
        
        import sqlite3
        print("✅ sqlite3 импортирован")
        
        from bot import init_db, generate_yoomoney_link
        print("✅ Все функции из bot импортированы")
        
    except Exception as e:
        print(f"❌ Ошибка импорта: {e}")

if __name__ == "__main__":
    print("🚀 Запуск тестов Telegram бота\n")
    
    test_imports()
    test_database()
    test_yoomoney_functions()
    
    print("\n✅ Все тесты завершены!")
    print("\n📋 Для запуска бота выполните:")
    print("python3 bot.py")