# Telegram Bot

## Функциональность

- Получение сообщений от пользователей
- Ответы администратора на сообщения
- Рассылка сообщений всем пользователям
- Статистика рассылок
- Управление сообщениями (удаление, просмотр)

## Установка

1. Клонируйте репозиторий:
```bash
git clone https://github.com/quasar96/tgbotswip.git
cd tgbotcursor
```

2. Создайте виртуальное окружение и активируйте его:
```bash
python -m venv venv
source venv/bin/activate  # для Linux/Mac
venv\Scripts\activate     # для Windows
```

3. Установите зависимости:
```bash
pip install -r requirements.txt
```

4. Создайте файл `.env` и добавьте в него:
```
BOT_TOKEN=your_bot_token
ADMIN_ID=your_admin_id
```

## Использование

1. Запустите бота:
```bash
python bot.py
```

2. Команды для администратора:
- `/start` - Начать работу с ботом
- `/broadcast` - Начать рассылку
- `/stats` - Статистика рассылок
- `/messages` - Просмотр сообщений от пользователей
- `/clear_stats` - Очистить статистику
- `/help` - Помощь

3. Для обычных пользователей доступны команды:
- `/start` - Начать работу с ботом
- `/help` - Помощь

## Требования

- Python 3.8+
- aiogram
- python-dotenv
- SQLAlchemy

## Структура проекта

- `bot.py` - Основной файл бота
- `database.py` - Работа с базой данных
- `utils.py` - Вспомогательные функции
- `requirements.txt` - Зависимости проекта
- `.env` - Конфигурационный файл

## Безопасность

- Только пользователь с ID, указанным в `ADMIN_ID`, может делать рассылки
- Токен бота хранится в файле `.env`
- База данных создается автоматически при первом запуске
