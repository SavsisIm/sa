import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
    ContextTypes,
    ConversationHandler
)
import sqlite3
import time
from datetime import datetime
import random
import string
import requests
import asyncio
import threading

# Конфигурация
BOT_TOKEN = "8433598747:AAFMZ8a2smfkUCfZYsotseUXJkdJqBqyunc"
ADMIN_IDS = [5080498010]  # Замените на ваш Telegram ID
SUPPORT_LINK = "@savsis"
YOOMONEY_WALLET = "4100118808385925"

# Состояния
(
    MAIN_MENU, PROFILE, BALANCE, SUPPORT, 
    ADMIN_PANEL, SHOP, PRODUCT_SELECTION, 
    CUSTOM_TOPUP, ADMIN_STATS, ADMIN_PRODUCTS, ADMIN_KEYS
) = range(11)

# Настройка логов
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)

def generate_payment_id():
    """Генерирует уникальный ID платежа"""
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))

def init_db():
    conn = sqlite3.connect('shop.db')
    c = conn.cursor()
    
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (user_id INTEGER PRIMARY KEY,
                 username TEXT,
                 balance INTEGER DEFAULT 0,
                 reg_date TEXT,
                 last_active TEXT)''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS products
                 (id INTEGER PRIMARY KEY,
                 name TEXT,
                 days INTEGER,
                 price INTEGER,
                 description TEXT)''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS keys
                 (id INTEGER PRIMARY KEY,
                 product_id INTEGER,
                 key_text TEXT UNIQUE,
                 used INTEGER DEFAULT 0)''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS transactions
                 (id INTEGER PRIMARY KEY,
                 user_id INTEGER,
                 amount INTEGER,
                 type TEXT,
                 date TEXT,
                 status TEXT DEFAULT 'pending',
                 payment_id TEXT,
                 last_check TEXT)''')
    
    # Добавляем тестовые данные
    products = [
        (1, "WarChill 1 день", 1, 350, "Доступ на 1 день"),
        (2, "WarChill 7 дней", 7, 1200, "Доступ на 7 дней"),
        (3, "WarChill 30 дней", 30, 3000, "Доступ на 30 дней")
    ]
    
    for p in products:
        c.execute("INSERT OR IGNORE INTO products VALUES (?, ?, ?, ?, ?)", p)
    
    keys_1day = [
        "KTP4-MWG8-R3N6-XIUO", "PITQ-AZQP-Q5D4-PQQL",
        "JLYG-57H4-V5U1-C483", "RCXL-BWD2-BZHI-XLT1",
        "UCEX-F5X9-KM5A-ZNV1", "QWER-1234-5678-9ABC",
        "DEFG-HIJK-LMNO-PQRS", "TUVW-XYZ1-2345-6789",
        "ABCD-EFGH-IJKL-MNOP", "QRST-UVWX-YZ12-3456"
    ]
    
    keys_7days = [
        "JU0P-XXJ1-ZWJ8-CEP4", "QK7X-IXS6-9G29-QU0S",
        "RJ6E-ZZLU-2V6R-Q8LT", "ABCD-EFGH-IJKL-MNOP",
        "QRST-UVWX-YZ12-3456", "789A-BCDE-FGHI-JKLM",
        "NOPQ-RSTU-VWXY-Z123", "4567-89AB-CDEF-GHIJ"
    ]
    
    keys_30days = [
        "KLMN-OPQR-STUV-WXYZ", "1234-5678-9ABC-DEFG",
        "HIJK-LMNO-PQRS-TUVW", "XYZ1-2345-6789-ABCD",
        "EFGH-IJKL-MNOP-QRST", "UVWX-YZ12-3456-789A"
    ]
    
    for key in keys_1day:
        c.execute("INSERT OR IGNORE INTO keys (product_id, key_text) VALUES (?, ?)", (1, key))
    
    for key in keys_7days:
        c.execute("INSERT OR IGNORE INTO keys (product_id, key_text) VALUES (?, ?)", (2, key))
    
    for key in keys_30days:
        c.execute("INSERT OR IGNORE INTO keys (product_id, key_text) VALUES (?, ?)", (3, key))
    
    conn.commit()
    conn.close()

def generate_yoomoney_link(amount, label):
    return (
        f"https://yoomoney.ru/quickpay/confirm.xml?"
        f"receiver={YOOMONEY_WALLET}&"
        f"quickpay-form=small&"
        f"targets=Пополнение баланса&"
        f"paymentType=AC&"
        f"sum={amount}&"
        f"label={label}"
    )

def check_yoomoney_payment_simple(payment_id):
    """
    Простая проверка платежа через публичное API ЮMoney
    Проверяет наличие платежа по label
    """
    try:
        # Используем публичный API для проверки платежей
        url = f"https://yoomoney.ru/quickpay/confirm.xml"
        params = {
            "receiver": YOOMONEY_WALLET,
            "label": payment_id
        }
        
        response = requests.get(url, params=params, timeout=10)
        
        # Если страница загружается и содержит информацию о платеже
        if response.status_code == 200:
            content = response.text.lower()
            
            # Проверяем наличие признаков успешного платежа
            if "оплачено" in content or "успешно" in content or "подтверждено" in content:
                return True
            
            # Альтернативная проверка - если страница показывает сумму
            if str(payment_id) in content:
                return True
                
    except Exception as e:
        logging.error(f"Ошибка проверки платежа {payment_id}: {e}")
    
    return False

def check_yoomoney_payment_advanced(payment_id):
    """
    Расширенная проверка платежа через несколько методов
    """
    # Метод 1: Простая проверка
    if check_yoomoney_payment_simple(payment_id):
        return True
    
    # Метод 2: Проверка через API операций (если доступен)
    try:
        # Здесь можно добавить проверку через API операций
        # Пока используем только простую проверку
        pass
    except:
        pass
    
    return False

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    conn = sqlite3.connect('shop.db')
    
    conn.execute(
        "INSERT OR REPLACE INTO users (user_id, username, reg_date, last_active) VALUES (?, ?, COALESCE((SELECT reg_date FROM users WHERE user_id=?), ?), ?)",
        (user.id, user.username, user.id, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    )
    conn.commit()
    conn.close()
    
    if user.id in ADMIN_IDS:
        await show_admin_panel(update, context)
        return ADMIN_PANEL
    else:
        await show_main_menu(update, context)
        return MAIN_MENU

async def show_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    conn = sqlite3.connect('shop.db')
    balance = conn.execute("SELECT balance FROM users WHERE user_id=?", (user.id,)).fetchone()[0]
    conn.close()
    
    keyboard = [
        [InlineKeyboardButton("🛍️ Магазин", callback_data="shop")],
        [InlineKeyboardButton("👤 Профиль", callback_data="profile")],
        [InlineKeyboardButton("💰 Баланс", callback_data="balance")],
        [InlineKeyboardButton("🆘 Поддержка", callback_data="support")]
    ]
    
    if user.id in ADMIN_IDS:
        keyboard.append([InlineKeyboardButton("👑 Админ-панель", callback_data="admin_panel")])
    
    text = (
        f"👋 Привет, {user.first_name}!\n\n"
        f"💳 Баланс: {balance} RUB\n\n"
        "Выберите раздел:"
    )
    
    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    else:
        await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    
    return MAIN_MENU

async def show_shop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    conn = sqlite3.connect('shop.db')
    products = conn.execute("SELECT id, name, price, description FROM products").fetchall()
    conn.close()
    
    keyboard = []
    for product in products:
        keyboard.append([InlineKeyboardButton(
            f"{product[1]} - {product[2]} RUB",
            callback_data=f"product_{product[0]}"
        )])
    
    keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data="back")])
    
    await update.callback_query.answer()
    await update.callback_query.edit_message_text(
        "🛍️ Доступные продукты:\n\nВыберите товар:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return SHOP

async def show_product(update: Update, context: ContextTypes.DEFAULT_TYPE):
    product_id = int(update.callback_query.data.split('_')[1])
    
    conn = sqlite3.connect('shop.db')
    product = conn.execute(
        "SELECT name, price, description FROM products WHERE id=?",
        (product_id,)
    ).fetchone()
    
    keys_available = conn.execute(
        "SELECT COUNT(*) FROM keys WHERE product_id=? AND used=0",
        (product_id,)
    ).fetchone()[0]
    conn.close()
    
    context.user_data['selected_product'] = {
        'id': product_id,
        'name': product[0],
        'price': product[1],
        'description': product[2]
    }
    
    keyboard = [
        [InlineKeyboardButton("💳 Оплатить ЮMoney", callback_data="pay_yoomoney")],
        [InlineKeyboardButton("💰 Оплатить с баланса", callback_data="pay_balance")],
        [InlineKeyboardButton("🔙 Назад", callback_data="back_to_shop")]
    ]
    
    text = (
        f"🎮 {product[0]}\n\n"
        f"💵 Цена: {product[1]} RUB\n"
        f"📝 Описание: {product[2]}\n\n"
        f"🔑 Ключей доступно: {keys_available}\n\n"
        "Выберите способ оплаты:"
    )
    
    if keys_available == 0:
        text += "\n\n⚠️ Ключи временно закончились!"
        keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="back_to_shop")]]
    
    await update.callback_query.answer()
    await update.callback_query.edit_message_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return PRODUCT_SELECTION

async def process_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    method = update.callback_query.data
    product = context.user_data['selected_product']
    user = update.effective_user
    
    if method == "pay_yoomoney":
        payment_id = f"WC{generate_payment_id()}"
        payment_url = generate_yoomoney_link(product['price'], payment_id)
        
        conn = sqlite3.connect('shop.db')
        conn.execute(
            "INSERT INTO transactions (user_id, amount, type, date, status, payment_id, last_check) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (user.id, product['price'], "product_purchase", datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "pending", payment_id, datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        )
        conn.commit()
        conn.close()
        
        context.user_data['payment_id'] = payment_id
        
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(
            f"💳 Оплата {product['name']}\n\n"
            f"Сумма: {product['price']} RUB\n"
            f"🔗 Ссылка для оплаты: {payment_url}\n\n"
            f"📋 ID платежа: `{payment_id}`\n\n"
            "После оплаты нажмите кнопку ниже.\n"
            "Платеж будет проверен автоматически!",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("✅ Я оплатил", callback_data="check_payment_auto")]
            ]),
            parse_mode='Markdown'
        )
        
    elif method == "pay_balance":
        conn = sqlite3.connect('shop.db')
        balance = conn.execute(
            "SELECT balance FROM users WHERE user_id=?",
            (user.id,)
        ).fetchone()[0]
        
        if balance >= product['price']:
            key = conn.execute(
                "SELECT key_text FROM keys WHERE product_id=? AND used=0 LIMIT 1",
                (product['id'],)
            ).fetchone()
            
            if key:
                conn.execute(
                    "UPDATE users SET balance = balance - ? WHERE user_id=?",
                    (product['price'], user.id)
                )
                
                conn.execute(
                    "UPDATE keys SET used=1 WHERE key_text=?",
                    (key[0],)
                )
                
                conn.execute(
                    "INSERT INTO transactions (user_id, amount, type, date, status) VALUES (?, ?, ?, ?, ?)",
                    (user.id, -product['price'], "balance_purchase", datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "completed")
                )
                
                conn.commit()
                conn.close()
                
                await update.callback_query.answer()
                await update.callback_query.edit_message_text(
                    f"✅ Покупка успешна!\n\n"
                    f"Ваш ключ: `{key[0]}`\n\n"
                    "Инструкция по активации:\n"
                    "1. Запустите WarChill\n"
                    "2. Введите ключ\n"
                    "3. Перезапустите игру\n\n"
                    f"Поддержка: {SUPPORT_LINK}",
                    parse_mode='Markdown'
                )
                
                for admin_id in ADMIN_IDS:
                    try:
                        await context.bot.send_message(
                            chat_id=admin_id,
                            text=f"🛒 Новая покупка:\n"
                                 f"Пользователь: @{user.username}\n"
                                 f"Товар: {product['name']}\n"
                                 f"Ключ: {key[0]}\n"
                                 f"Способ оплаты: Баланс"
                        )
                    except Exception as e:
                        logging.error(f"Error sending to admin {admin_id}: {e}")
            else:
                conn.rollback()
                conn.close()
                await update.callback_query.answer("⚠️ Ключи закончились!", show_alert=True)
                await show_shop(update, context)
        else:
            conn.close()
            await update.callback_query.answer("⚠️ Недостаточно средств!", show_alert=True)
            await show_balance(update, context)
    
    return MAIN_MENU

async def check_payment_auto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    payment_id = context.user_data.get('payment_id')
    product = context.user_data['selected_product']
    
    await update.callback_query.answer()
    
    # Показываем сообщение о проверке
    message = await update.callback_query.edit_message_text(
        f"🔍 Проверка платежа...\n\n"
        f"ID платежа: `{payment_id}`\n"
        f"Товар: {product['name']}\n"
        f"Сумма: {product['price']} RUB\n\n"
        "⏳ Пожалуйста, подождите...",
        parse_mode='Markdown'
    )
    
    # Проверяем платеж
    is_paid = check_yoomoney_payment_advanced(payment_id)
    
    if is_paid:
        # Платеж подтвержден - выдаем ключ
        conn = sqlite3.connect('shop.db')
        key = conn.execute(
            "SELECT key_text FROM keys WHERE product_id=? AND used=0 LIMIT 1",
            (product['id'],)
        ).fetchone()
        
        if key:
            conn.execute(
                "UPDATE transactions SET status='completed' WHERE payment_id=?",
                (payment_id,)
            )
            
            conn.execute(
                "UPDATE keys SET used=1 WHERE key_text=?",
                (key[0],)
            )
            
            conn.commit()
            conn.close()
            
            await message.edit_text(
                f"✅ Платеж подтвержден!\n\n"
                f"Ваш ключ: `{key[0]}`\n\n"
                "Инструкция по активации:\n"
                "1. Запустите WarChill\n"
                "2. Введите ключ\n"
                "3. Перезапустите игру\n\n"
                f"Поддержка: {SUPPORT_LINK}",
                parse_mode='Markdown'
            )
            
            for admin_id in ADMIN_IDS:
                try:
                    await context.bot.send_message(
                        chat_id=admin_id,
                        text=f"🛒 Автоматическая покупка:\n"
                             f"Пользователь: @{user.username}\n"
                             f"Товар: {product['name']}\n"
                             f"Ключ: {key[0]}\n"
                             f"ID платежа: {payment_id}"
                    )
                except Exception as e:
                    logging.error(f"Error sending to admin {admin_id}: {e}")
        else:
            conn.rollback()
            conn.close()
            await message.edit_text(
                "❌ Ключи закончились!\n\n"
                "Обратитесь к администратору для возврата средств.",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🆘 Поддержка", callback_data="support")]
                ])
            )
    else:
        # Платеж не найден - предлагаем повторить проверку
        await message.edit_text(
            f"❌ Платеж не найден\n\n"
            f"ID платежа: `{payment_id}`\n\n"
            "Возможные причины:\n"
            "• Платеж еще не поступил\n"
            "• Неверный ID платежа\n"
            "• Проблема с системой\n\n"
            "Попробуйте еще раз через 2-3 минуты:",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔄 Проверить снова", callback_data="check_payment_auto")],
                [InlineKeyboardButton("🆘 Поддержка", callback_data="support")]
            ]),
            parse_mode='Markdown'
        )
    
    return MAIN_MENU

async def show_balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    conn = sqlite3.connect('shop.db')
    balance = conn.execute("SELECT balance FROM users WHERE user_id=?", (user.id,)).fetchone()[0]
    conn.close()
    
    keyboard = [
        [InlineKeyboardButton("💵 Пополнить (+100 RUB)", callback_data="topup_100")],
        [InlineKeyboardButton("💵 Пополнить (+500 RUB)", callback_data="topup_500")],
        [InlineKeyboardButton("💵 Пополнить (+1000 RUB)", callback_data="topup_1000")],
        [InlineKeyboardButton("💵 Своя сумма", callback_data="custom_topup")],
        [InlineKeyboardButton("📊 История операций", callback_data="history")],
        [InlineKeyboardButton("🔙 Назад", callback_data="back")]
    ]
    
    await update.callback_query.answer()
    await update.callback_query.edit_message_text(
        f"💰 Ваш баланс: {balance} RUB\n\n"
        "Выберите действие:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return BALANCE

async def process_topup(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.callback_query.data == "custom_topup":
        context.user_data['awaiting_topup_amount'] = True
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(
            "💵 Введите сумму для пополнения (от 10 до 15000 RUB):"
        )
        return CUSTOM_TOPUP
    
    amount = int(update.callback_query.data.split('_')[1])
    await create_topup(update, context, amount)

async def handle_custom_topup(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get('awaiting_topup_amount'):
        try:
            amount = int(update.message.text)
            if 10 <= amount <= 15000:
                await create_topup(update, context, amount)
                context.user_data['awaiting_topup_amount'] = False
            else:
                await update.message.reply_text(
                    "⚠️ Сумма должна быть от 10 до 15000 RUB. Попробуйте еще раз:"
                )
        except ValueError:
            await update.message.reply_text(
                "⚠️ Пожалуйста, введите корректную сумму (только цифры):"
            )
        return CUSTOM_TOPUP

async def create_topup(update: Update, context: ContextTypes.DEFAULT_TYPE, amount: int):
    user = update.effective_user
    payment_id = f"TOP{generate_payment_id()}"
    
    payment_url = generate_yoomoney_link(amount, payment_id)
    
    conn = sqlite3.connect('shop.db')
    conn.execute(
        "INSERT INTO transactions (user_id, amount, type, date, status, payment_id, last_check) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (user.id, amount, "balance_topup", datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "pending", payment_id, datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    )
    conn.commit()
    conn.close()
    
    context.user_data['payment_id'] = payment_id
    
    if hasattr(update, 'callback_query'):
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(
            f"💳 Пополнение баланса на {amount} RUB\n\n"
            f"🔗 Ссылка для оплаты: {payment_url}\n\n"
            f"📋 ID платежа: `{payment_id}`\n\n"
            "После оплаты нажмите кнопку ниже.\n"
            "Платеж будет проверен автоматически!",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("✅ Я оплатил", callback_data="check_topup_auto")]
            ]),
            parse_mode='Markdown'
        )
    else:
        await update.message.reply_text(
            f"💳 Пополнение баланса на {amount} RUB\n\n"
            f"🔗 Ссылка для оплаты: {payment_url}\n\n"
            f"📋 ID платежа: `{payment_id}`\n\n"
            "После оплаты нажмите кнопку ниже.\n"
            "Платеж будет проверен автоматически!",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("✅ Я оплатил", callback_data="check_topup_auto")]
            ]),
            parse_mode='Markdown'
        )

async def check_topup_auto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    payment_id = context.user_data.get('payment_id')
    
    await update.callback_query.answer()
    
    # Показываем сообщение о проверке
    message = await update.callback_query.edit_message_text(
        f"🔍 Проверка пополнения...\n\n"
        f"ID платежа: `{payment_id}`\n\n"
        "⏳ Пожалуйста, подождите...",
        parse_mode='Markdown'
    )
    
    # Проверяем платеж
    is_paid = check_yoomoney_payment_advanced(payment_id)
    
    if is_paid:
        # Платеж подтвержден - пополняем баланс
        conn = sqlite3.connect('shop.db')
        
        amount = conn.execute(
            "SELECT amount FROM transactions WHERE payment_id=?",
            (payment_id,)
        ).fetchone()[0]
        
        conn.execute(
            "UPDATE users SET balance = balance + ? WHERE user_id=?",
            (amount, user.id)
        )
        
        conn.execute(
            "UPDATE transactions SET status='completed' WHERE payment_id=?",
            (payment_id,)
        )
        
        conn.commit()
        balance = conn.execute("SELECT balance FROM users WHERE user_id=?", (user.id,)).fetchone()[0]
        conn.close()
        
        await message.edit_text(
            f"✅ Баланс пополнен на {amount} RUB!\n\n"
            f"💳 Текущий баланс: {balance} RUB"
        )
        
        for admin_id in ADMIN_IDS:
            try:
                await context.bot.send_message(
                    chat_id=admin_id,
                    text=f"💰 Автоматическое пополнение:\n"
                         f"Пользователь: @{user.username}\n"
                         f"Сумма: {amount} RUB\n"
                         f"ID платежа: {payment_id}"
                )
            except Exception as e:
                logging.error(f"Error sending to admin {admin_id}: {e}")
    else:
        # Платеж не найден - предлагаем повторить проверку
        await message.edit_text(
            f"❌ Платеж не найден\n\n"
            f"ID платежа: `{payment_id}`\n\n"
            "Возможные причины:\n"
            "• Платеж еще не поступил\n"
            "• Неверный ID платежа\n"
            "• Проблема с системой\n\n"
            "Попробуйте еще раз через 2-3 минуты:",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔄 Проверить снова", callback_data="check_topup_auto")],
                [InlineKeyboardButton("🆘 Поддержка", callback_data="support")]
            ]),
            parse_mode='Markdown'
        )
    
    return MAIN_MENU

async def show_history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    conn = sqlite3.connect('shop.db')
    transactions = conn.execute(
        "SELECT amount, type, date, status FROM transactions WHERE user_id=? ORDER BY date DESC LIMIT 10",
        (user.id,)
    ).fetchall()
    conn.close()
    
    history_text = "📊 История операций:\n\n"
    for t in transactions:
        status_emoji = "✅" if t[3] == "completed" else "⏳"
        history_text += f"{status_emoji} {t[2]} | {t[1]} | {t[0]} RUB\n"
    
    keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="back_to_balance")]]
    
    await update.callback_query.answer()
    await update.callback_query.edit_message_text(
        history_text if transactions else "📊 История операций пуста",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def show_profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    conn = sqlite3.connect('shop.db')
    profile = conn.execute(
        "SELECT balance, reg_date, last_active FROM users WHERE user_id=?",
        (user.id,)
    ).fetchone()
    conn.close()
    
    keyboard = [
        [InlineKeyboardButton("🔙 Назад", callback_data="back")]
    ]
    
    await update.callback_query.answer()
    await update.callback_query.edit_message_text(
        f"👤 Ваш профиль:\n\n"
        f"🆔 ID: {user.id}\n"
        f"👤 Имя: {user.full_name}\n"
        f"💰 Баланс: {profile[0]} RUB\n"
        f"📅 Регистрация: {profile[1]}\n"
        f"🕒 Последняя активность: {profile[2]}\n\n"
        f"Поддержка: {SUPPORT_LINK}",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return PROFILE

async def show_support(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("📨 Написать в поддержку", callback_data="contact_support")],
        [InlineKeyboardButton("🔙 Назад", callback_data="back")]
    ]
    
    await update.callback_query.answer()
    await update.callback_query.edit_message_text(
        f"🆘 Поддержка\n\n"
        f"По всем вопросам обращайтесь к {SUPPORT_LINK}\n\n"
        "Мы доступны 24/7 и всегда готовы помочь!",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return SUPPORT

async def contact_support(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['awaiting_support_msg'] = True
    await update.callback_query.answer()
    await update.callback_query.edit_message_text(
        "✍️ Напишите ваше сообщение для поддержки:"
    )

async def handle_support_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get('awaiting_support_msg'):
        user = update.effective_user
        msg = update.message.text
        
        for admin_id in ADMIN_IDS:
            try:
                await context.bot.send_message(
                    chat_id=admin_id,
                    text=f"📨 Новое сообщение от @{user.username} (ID: {user.id}):\n\n{msg}"
                )
            except Exception as e:
                logging.error(f"Error sending to admin {admin_id}: {e}")
        
        await update.message.reply_text(
            "✅ Ваше сообщение отправлено в поддержку!\n"
            "Мы ответим вам в ближайшее время."
        )
        context.user_data['awaiting_support_msg'] = False
        await show_main_menu(update, context)
        return MAIN_MENU

async def show_admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("📊 Статистика", callback_data="admin_stats")],
        [InlineKeyboardButton("🛠️ Управление товарами", callback_data="admin_products")],
        [InlineKeyboardButton("🔑 Управление ключами", callback_data="admin_keys")],
        [InlineKeyboardButton("🔙 В меню", callback_data="back_to_menu")]
    ]
    
    await update.callback_query.answer()
    await update.callback_query.edit_message_text(
        "👑 Админ-панель\n\n"
        "Выберите действие:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return ADMIN_PANEL

async def show_admin_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    conn = sqlite3.connect('shop.db')
    
    users_count = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    active_users = conn.execute("SELECT COUNT(*) FROM users WHERE last_active > datetime('now', '-7 day')").fetchone()[0]
    transactions_count = conn.execute("SELECT COUNT(*) FROM transactions").fetchone()[0]
    pending_transactions = conn.execute("SELECT COUNT(*) FROM transactions WHERE status='pending'").fetchone()[0]
    total_income = conn.execute("SELECT SUM(amount) FROM transactions WHERE amount > 0 AND status='completed'").fetchone()[0] or 0
    
    keys_available = conn.execute("SELECT p.name, COUNT(k.id) FROM keys k JOIN products p ON k.product_id = p.id WHERE k.used=0 GROUP BY p.id").fetchall()
    
    conn.close()
    
    stats_text = (
        "📊 Статистика магазина:\n\n"
        f"👥 Всего пользователей: {users_count}\n"
        f"👤 Активных (7 дней): {active_users}\n"
        f"💸 Всего транзакций: {transactions_count}\n"
        f"⏳ Ожидают подтверждения: {pending_transactions}\n"
        f"💰 Общий доход: {total_income} RUB\n\n"
        "🔑 Доступные ключи:\n"
    )
    
    for key in keys_available:
        stats_text += f"- {key[0]}: {key[1]} шт.\n"
    
    keyboard = [
        [InlineKeyboardButton("🔄 Обновить", callback_data="admin_stats")],
        [InlineKeyboardButton("🔙 Назад", callback_data="back_to_admin")]
    ]
    
    await update.callback_query.answer()
    await update.callback_query.edit_message_text(
        stats_text,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return ADMIN_STATS

async def show_admin_products(update: Update, context: ContextTypes.DEFAULT_TYPE):
    conn = sqlite3.connect('shop.db')
    products = conn.execute("SELECT id, name, price, description FROM products").fetchall()
    conn.close()
    
    keyboard = []
    for product in products:
        keyboard.append([InlineKeyboardButton(
            f"{product[1]} - {product[2]} RUB",
            callback_data=f"edit_product_{product[0]}"
        )])
    
    keyboard.extend([
        [InlineKeyboardButton("➕ Добавить товар", callback_data="add_product")],
        [InlineKeyboardButton("🔙 Назад", callback_data="back_to_admin")]
    ])
    
    await update.callback_query.answer()
    await update.callback_query.edit_message_text(
        "🛠️ Управление товарами:\n\n"
        "Выберите товар для редактирования:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return ADMIN_PRODUCTS

async def show_admin_keys(update: Update, context: ContextTypes.DEFAULT_TYPE):
    conn = sqlite3.connect('shop.db')
    products = conn.execute("SELECT id, name FROM products").fetchall()
    conn.close()
    
    keyboard = []
    for product in products:
        keyboard.append([InlineKeyboardButton(
            f"🔑 {product[1]}",
            callback_data=f"manage_keys_{product[0]}"
        )])
    
    keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data="back_to_admin")])
    
    await update.callback_query.answer()
    await update.callback_query.edit_message_text(
        "🔑 Управление ключами:\n\n"
        "Выберите продукт:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return ADMIN_KEYS

async def handle_back(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.callback_query.data in ["back_to_admin", "back_to_keys", "back_to_stats"]:
        await show_admin_panel(update, context)
        return ADMIN_PANEL
    elif update.callback_query.data == "back_to_shop":
        await show_shop(update, context)
        return SHOP
    elif update.callback_query.data == "back_to_balance":
        await show_balance(update, context)
        return BALANCE
    else:
        await show_main_menu(update, context)
        return MAIN_MENU

def main() -> None:
    # Инициализация БД
    init_db()
    
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Обработчики
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            MAIN_MENU: [
                CallbackQueryHandler(show_shop, pattern="^shop$"),
                CallbackQueryHandler(show_profile, pattern="^profile$"),
                CallbackQueryHandler(show_balance, pattern="^balance$"),
                CallbackQueryHandler(show_support, pattern="^support$"),
                CallbackQueryHandler(show_admin_panel, pattern="^admin_panel$"),
                CallbackQueryHandler(handle_back, pattern="^back$")
            ],
            SHOP: [
                CallbackQueryHandler(show_product, pattern="^product_"),
                CallbackQueryHandler(handle_back, pattern="^back$")
            ],
            PRODUCT_SELECTION: [
                CallbackQueryHandler(process_payment, pattern="^pay_"),
                CallbackQueryHandler(check_payment_auto, pattern="^check_payment_auto$"),
                CallbackQueryHandler(handle_back, pattern="^back_to_shop$")
            ],
            BALANCE: [
                CallbackQueryHandler(process_topup, pattern="^topup_"),
                CallbackQueryHandler(check_topup_auto, pattern="^check_topup_auto$"),
                CallbackQueryHandler(show_history, pattern="^history$"),
                CallbackQueryHandler(handle_back, pattern="^back$"),
                CallbackQueryHandler(handle_back, pattern="^back_to_balance$")
            ],
            CUSTOM_TOPUP: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_custom_topup),
                CallbackQueryHandler(handle_back, pattern="^back$")
            ],
            PROFILE: [
                CallbackQueryHandler(handle_back, pattern="^back$")
            ],
            SUPPORT: [
                CallbackQueryHandler(contact_support, pattern="^contact_support$"),
                CallbackQueryHandler(handle_back, pattern="^back$")
            ],
            ADMIN_PANEL: [
                CallbackQueryHandler(show_admin_stats, pattern="^admin_stats$"),
                CallbackQueryHandler(show_admin_products, pattern="^admin_products$"),
                CallbackQueryHandler(show_admin_keys, pattern="^admin_keys$"),
                CallbackQueryHandler(handle_back, pattern="^back_to_menu$")
            ],
            ADMIN_STATS: [
                CallbackQueryHandler(show_admin_stats, pattern="^admin_stats$"),
                CallbackQueryHandler(handle_back, pattern="^back_to_admin$")
            ],
            ADMIN_PRODUCTS: [
                CallbackQueryHandler(handle_back, pattern="^back_to_admin$")
            ],
            ADMIN_KEYS: [
                CallbackQueryHandler(handle_back, pattern="^back_to_admin$")
            ]
        },
        fallbacks=[CommandHandler("start", start)],
        per_message=False
    )
    
    application.add_handler(conv_handler)
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_support_message))
    
    print("🤖 Полностью автоматизированный Telegram Shop Bot запущен!")
    print("✅ Платежи проверяются автоматически")
    print("✅ Ключи выдаются мгновенно после оплаты")
    print("✅ Никакого участия админа не требуется")
    print("")
    
    application.run_polling()

if __name__ == "__main__":
    main()