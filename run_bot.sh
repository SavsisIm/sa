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

# Запускаем бота
echo "🤖 Запуск бота..."
echo "Для остановки нажмите Ctrl+C"
echo ""

python3 bot.py