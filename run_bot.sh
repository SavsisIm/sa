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
echo "1) ПОЛНОСТЬЮ АВТОМАТИЗИРОВАННАЯ (рекомендуется) - bot_full_auto.py"
echo "2) Автоматизированная версия - bot_auto.py"
echo "3) Полная версия с API ЮMoney - bot.py"
echo "4) Упрощенная версия без API - bot_simple.py"
echo ""
read -p "Введите номер (1, 2, 3 или 4): " choice

case $choice in
    1)
        echo "🚀 Запуск ПОЛНОСТЬЮ автоматизированной версии бота..."
        echo "✅ Платежи проверяются автоматически"
        echo "✅ Ключи выдаются мгновенно"
        echo "✅ Никакого участия админа не требуется"
        echo ""
        python3 bot_full_auto.py
        ;;
    2)
        echo "🚀 Запуск автоматизированной версии бота..."
        python3 bot_auto.py
        ;;
    3)
        echo "🚀 Запуск полной версии бота..."
        python3 bot.py
        ;;
    4)
        echo "🚀 Запуск упрощенной версии бота..."
        python3 bot_simple.py
        ;;
    *)
        echo "❌ Неверный выбор. Запускаем ПОЛНОСТЬЮ автоматизированную версию..."
        python3 bot_full_auto.py
        ;;
esac