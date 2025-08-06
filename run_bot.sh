#!/bin/bash

echo "🚀 Запуск Telegram Shop Bot..."
echo ""

# Проверяем наличие Python
if ! command -v python3 &> /dev/null; then
    echo "❌ Python3 не найден. Установите Python3."
    exit 1
fi

# Проверяем наличие файла бота
if [ ! -f "bot.py" ]; then
    echo "❌ Файл bot.py не найден."
    exit 1
fi

# Проверяем зависимости
echo "📦 Проверка зависимостей..."
python3 -c "import telegram, requests" 2>/dev/null
if [ $? -ne 0 ]; then
    echo "⚠️ Устанавливаем зависимости..."
    pip3 install --break-system-packages python-telegram-bot requests
fi

echo "✅ Зависимости установлены"
echo ""

# Выбираем версию бота
echo "🤖 Выберите версию бота:"
echo "1) Полная версия с API ЮMoney (bot.py)"
echo "2) Упрощенная версия без API (bot_simple.py)"
echo ""
read -p "Введите номер (1 или 2): " choice

case $choice in
    1)
        echo "🚀 Запуск полной версии бота..."
        python3 bot.py
        ;;
    2)
        echo "🚀 Запуск упрощенной версии бота..."
        python3 bot_simple.py
        ;;
    *)
        echo "❌ Неверный выбор. Запускаем полную версию..."
        python3 bot.py
        ;;
esac