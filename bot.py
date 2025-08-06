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
import uuid
import time
from datetime import datetime
import requests
import base64
from http.server import BaseHTTPRequestHandler, HTTPServer
import threading
import webbrowser

# Конфигурация
BOT_TOKEN = "8433598747:AAFMZ8a2smfkUCfZYsotseUXJkdJqBqyunc"
ADMIN_IDS = [5080498010]
SUPPORT_LINK = "@savsis"
YOOMONEY_WALLET = "4100118808385925"
YOOMONEY_CLIENT_ID = "096257E21E2151ABB89C4D4EEE151189774A14E3F40AE665D9E033FB410BE83E"
YOOMONEY_CLIENT_SECRET = "your_client_secret"
YOOMONEY_REDIRECT_URI = "http://localhost:8080/callback"
YOOMONEY_ACCESS_TOKEN = None
LOCAL_SERVER_PORT = 8080

# Состояния
(
    MAIN_MENU, PROFILE, BALANCE, SUPPORT, 
    ADMIN_PANEL, SHOP, PRODUCT_SELECTION, 
    PAYMENT_METHOD, CUSTOM_TOPUP, ADMIN_STATS,
    ADMIN_PRODUCTS, ADMIN_KEYS
) = range(12)

# Настройка логов
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)

class YooMoneyCallbackHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path.startswith('/callback'):
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            self.wfile.write(b"<html><body><h1>Authorization successful! You can close this page.</h1></body></html>")
            code = self.path.split('code=')[1].split('&')[0]
            get_access_token(code)
            threading.Thread(target=self.server.shutdown, daemon=True).start()

def run_local_server():
    server = HTTPServer(('localhost', LOCAL_SERVER_PORT), YooMoneyCallbackHandler)
    server.serve_forever()

def yoomoney_auth():
    auth_url = (
        f"https://yoomoney.ru/oauth/authorize?"
        f"client_id={YOOMONEY_CLIENT_ID}&"
        f"response_type=code&"
        f"redirect_uri={YOOMONEY_REDIRECT_URI}&"
        f"scope=operation-history"
    )
    
    print(f"Откройте эту ссылку для авторизации: {auth_url}")
    webbrowser.open(auth_url)
    
    # Запускаем локальный сервер для получения callback
    server_thread = threading.Thread(target=run_local_server, daemon=True)
    server_thread.start()

def get_access_token(auth_code):
    global YOOMONEY_ACCESS_TOKEN
    auth = base64.b64encode(f"{YOOMONEY_CLIENT_ID}:{YOOMONEY_CLIENT_SECRET}".encode()).decode()
    headers = {
        "Authorization": f"Basic {auth}",
        "Content-Type": "application/x-www-form-urlencoded"
    }
    data = {
        "code": auth_code,
        "client_id": YOOMONEY_CLIENT_ID,
        "grant_type": "authorization_code",
        "redirect_uri": YOOMONEY_REDIRECT_URI
    }
    
    response = requests.post(
        "https://yoomoney.ru/oauth/token",
        headers=headers,
        data=data
    )
    
    if response.status_code == 200:
        YOOMONEY_ACCESS_TOKEN = response.json().get("access_token")
        logging.info("Успешная авторизация в API ЮMoney!")
    else:
        logging.error(f"Ошибка авторизации: {response.text}")

def check_yoomoney_payment(label):
    if not YOOMONEY_ACCESS_TOKEN:
        logging.error("Не установлен access token для API ЮMoney")
        return False
    
    headers = {
        "Authorization": f"Bearer {YOOMONEY_ACCESS_TOKEN}",
        "Content-Type": "application/x-www-form-urlencoded"
    }
    
    try:
        response = requests.get(
            f"https://yoomoney.ru/api/operation-history",
            headers=headers,
            params={
                "type": "deposition",
                "label": label,
                "records": 1
            },
            timeout=10
        )
        
        if response.status_code == 200:
            operations = response.json().get("operations", [])
            if operations:
                operation = operations[0]
                return (
                    operation.get("status") == "success" and 
                    float(operation.get("amount")) > 0 and
                    operation.get("label") == label
                )
    except Exception as e:
        logging.error(f"Ошибка проверки платежа: {e}")
    
    return False

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
                 yoomoney_label TEXT)''')
    
    # Добавляем тестовые данные
    products = [
        (1, "WarChill 1 день", 1, 350, "Доступ на 1 день"),
        (2, "WarChill 7 дней", 7, 1200, "Доступ на 7 дней")
    ]
    
    for p in products:
        c.execute("INSERT OR IGNORE INTO products VALUES (?, ?, ?, ?, ?)", p)
    
    keys_1day = [
        "KTP4-MWG8-R3N6-XIUO", "PITQ-AZQP-Q5D4-PQQL",
        "JLYG-57H4-V5U1-C483", "RCXL-BWD2-BZHI-XLT1",
        "UCEX-F5X9-KM5A-ZNV1"
    ]
    
    keys_7days = [
        "JU0P-XXJ1-ZWJ8-CEP4", "QK7X-IXS6-9G29-QU0S",
        "RJ6E-ZZLU-2V6R-Q8LT"
    ]
    
    for key in keys_1day:
        c.execute("INSERT OR IGNORE INTO keys (product_id, key_text) VALUES (?, ?)", (1, key))
    
    for key in keys_7days:
        c.execute("INSERT OR IGNORE INTO keys (product_id, key_text) VALUES (?, ?)", (2, key))
    
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
        payment_id = f"wc_{user.id}_{int(time.time())}"
        payment_url = generate_yoomoney_link(product['price'], payment_id)
        
        conn = sqlite3.connect('shop.db')
        conn.execute(
            "INSERT INTO transactions (user_id, amount, type, date, status, yoomoney_label) VALUES (?, ?, ?, ?, ?, ?)",
            (user.id, product['price'], "product_purchase", datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "pending", payment_id)
        )
        conn.commit()
        conn.close()
        
        context.user_data['payment_id'] = payment_id
        
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(
            f"💳 Оплата {product['name']}\n\n"
            f"Сумма: {product['price']} RUB\n\n"
            f"🔗 Ссылка для оплаты: {payment_url}\n\n"
            "После оплаты нажмите кнопку ниже:",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("✅ Я оплатил", callback_data="check_payment")]
            ])
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
                    f"Ваш ключ: {key[0]}\n\n"
                    "Инструкция по активации:\n"
                    "1. Запустите WarChill\n"
                    "2. Введите ключ\n"
                    "3. Перезапустите игру\n\n"
                    f"Поддержка: {SUPPORT_LINK}"
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

async def check_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    payment_id = context.user_data.get('payment_id')
    product = context.user_data['selected_product']
    
    is_paid = check_yoomoney_payment(payment_id)
    
    if is_paid:
        conn = sqlite3.connect('shop.db')
        key = conn.execute(
            "SELECT key_text FROM keys WHERE product_id=? AND used=0 LIMIT 1",
            (product['id'],)
        ).fetchone()
        
        if key:
            conn.execute(
                "UPDATE transactions SET status='completed' WHERE yoomoney_label=?",
                (payment_id,)
            )
            
            conn.execute(
                "UPDATE keys SET used=1 WHERE key_text=?",
                (key[0],)
            )
            
            conn.commit()
            conn.close()
            
            await update.callback_query.answer()
            await update.callback_query.edit_message_text(
                f"✅ Платеж подтвержден!\n\n"
                f"Ваш ключ: {key[0]}\n\n"
                "Инструкция по активации:\n"
                "1. Запустите WarChill\n"
                "2. Введите ключ\n"
                "3. Перезапустите игру\n\n"
                f"Поддержка: {SUPPORT_LINK}"
            )
            
            for admin_id in ADMIN_IDS:
                try:
                    await context.bot.send_message(
                        chat_id=admin_id,
                        text=f"🛒 Новая покупка:\n"
                             f"Пользователь: @{user.username}\n"
                             f"Товар: {product['name']}\n"
                             f"Ключ: {key[0]}\n"
                             f"Способ оплаты: ЮMoney"
                    )
                except Exception as e:
                    logging.error(f"Error sending to admin {admin_id}: {e}")
        else:
            conn.rollback()
            conn.close()
            await update.callback_query.answer("⚠️ Ключи закончились!", show_alert=True)
            await show_shop(update, context)
    else:
        await update.callback_query.answer("⚠️ Платеж не найден!", show_alert=True)
    
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
    payment_id = f"topup_{user.id}_{int(time.time())}"
    
    payment_url = generate_yoomoney_link(amount, payment_id)
    
    conn = sqlite3.connect('shop.db')
    conn.execute(
        "INSERT INTO transactions (user_id, amount, type, date, status, yoomoney_label) VALUES (?, ?, ?, ?, ?, ?)",
        (user.id, amount, "balance_topup", datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "pending", payment_id)
    )
    conn.commit()
    conn.close()
    
    context.user_data['payment_id'] = payment_id
    
    if hasattr(update, 'callback_query'):
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(
            f"💳 Пополнение баланса на {amount} RUB\n\n"
            f"🔗 Ссылка для оплаты: {payment_url}\n\n"
            "После оплаты нажмите кнопку ниже:",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("✅ Я оплатил", callback_data="check_topup")]
            ])
        )
    else:
        await update.message.reply_text(
            f"💳 Пополнение баланса на {amount} RUB\n\n"
            f"🔗 Ссылка для оплаты: {payment_url}\n\n"
            "После оплаты нажмите кнопку ниже:",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("✅ Я оплатил", callback_data="check_topup")]
            ])
        )

async def check_topup(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    payment_id = context.user_data.get('payment_id')
    
    is_paid = check_yoomoney_payment(payment_id)
    
    if is_paid:
        conn = sqlite3.connect('shop.db')
        
        amount = conn.execute(
            "SELECT amount FROM transactions WHERE yoomoney_label=?",
            (payment_id,)
        ).fetchone()[0]
        
        conn.execute(
            "UPDATE users SET balance = balance + ? WHERE user_id=?",
            (amount, user.id)
        )
        
        conn.execute(
            "UPDATE transactions SET status='completed' WHERE yoomoney_label=?",
            (payment_id,)
        )
        
        conn.commit()
        balance = conn.execute("SELECT balance FROM users WHERE user_id=?", (user.id,)).fetchone()[0]
        conn.close()
        
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(
            f"✅ Баланс успешно пополнен на {amount} RUB!\n\n"
            f"💳 Текущий баланс: {balance} RUB"
        )
        
        for admin_id in ADMIN_IDS:
            try:
                await context.bot.send_message(
                    chat_id=admin_id,
                    text=f"💰 Пополнение баланса:\n"
                         f"Пользователь: @{user.username}\n"
                         f"Сумма: {amount} RUB\n"
                         f"Новый баланс: {balance} RUB"
                )
            except Exception as e:
                logging.error(f"Error sending to admin {admin_id}: {e}")
    else:
        await update.callback_query.answer("⚠️ Платеж не найден!", show_alert=True)
    
    return MAIN_MENU

async def show_history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    conn = sqlite3.connect('shop.db')
    transactions = conn.execute(
        "SELECT amount, type, date FROM transactions WHERE user_id=? ORDER BY date DESC LIMIT 10",
        (user.id,)
    ).fetchall()
    conn.close()
    
    history_text = "📊 История операций:\n\n"
    for t in transactions:
        history_text += f"{t[2]} | {t[1]} | {t[0]} RUB\n"
    
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
        [InlineKeyboardButton("✏️ Изменить данные", callback_data="edit_profile")],
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
        [InlineKeyboardButton("👥 Пользователи", callback_data="admin_users")],
        [InlineKeyboardButton("💸 Транзакции", callback_data="admin_transactions")],
        [InlineKeyboardButton("🔙 В меню", callback_data="back_to_menu")]
    ]
    
    await update.callback_query.answer()
    await update.callback_query.edit_message_text(
        "👑 Админ-панель",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return ADMIN_PANEL

async def show_admin_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    conn = sqlite3.connect('shop.db')
    
    users_count = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    active_users = conn.execute("SELECT COUNT(*) FROM users WHERE last_active > datetime('now', '-7 day')").fetchone()[0]
    transactions_count = conn.execute("SELECT COUNT(*) FROM transactions").fetchone()[0]
    total_income = conn.execute("SELECT SUM(amount) FROM transactions WHERE amount > 0").fetchone()[0] or 0
    
    keys_available = conn.execute("SELECT p.name, COUNT(k.id) FROM keys k JOIN products p ON k.product_id = p.id WHERE k.used=0 GROUP BY p.id").fetchall()
    
    conn.close()
    
    stats_text = (
        "📊 Статистика магазина:\n\n"
        f"👥 Всего пользователей: {users_count}\n"
        f"👤 Активных (7 дней): {active_users}\n"
        f"💸 Всего транзакций: {transactions_count}\n"
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

async def manage_product_keys(update: Update, context: ContextTypes.DEFAULT_TYPE):
    product_id = int(update.callback_query.data.split('_')[2])
    
    conn = sqlite3.connect('shop.db')
    product = conn.execute("SELECT name FROM products WHERE id=?", (product_id,)).fetchone()
    keys = conn.execute(
        "SELECT key_text, used FROM keys WHERE product_id=? ORDER BY used",
        (product_id,)
    ).fetchall()
    conn.close()
    
    keyboard = [
        [InlineKeyboardButton("➕ Добавить ключи", callback_data=f"add_keys_{product_id}")],
        [InlineKeyboardButton("🔙 Назад", callback_data="back_to_keys")]
    ]
    
    keys_text = f"🔑 Ключи для {product[0]}:\n\n"
    for key in keys:
        keys_text += f"{'✅' if not key[1] else '❌'} {key[0]}\n"
    
    await update.callback_query.answer()
    await update.callback_query.edit_message_text(
        keys_text,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

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
    # Авторизация в ЮMoney при старте
    yoomoney_auth()
    
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
                CallbackQueryHandler(check_payment, pattern="^check_payment$"),
                CallbackQueryHandler(handle_back, pattern="^back_to_shop$")
            ],
            BALANCE: [
                CallbackQueryHandler(process_topup, pattern="^topup_"),
                CallbackQueryHandler(check_topup, pattern="^check_topup$"),
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
                CallbackQueryHandler(manage_product_keys, pattern="^manage_keys_"),
                CallbackQueryHandler(handle_back, pattern="^back_to_admin$"),
                CallbackQueryHandler(handle_back, pattern="^back_to_keys$")
            ]
        },
        fallbacks=[CommandHandler("start", start)],
        per_message=False
    )
    
    application.add_handler(conv_handler)
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_support_message))
    application.run_polling()

if __name__ == "__main__":
    main()
