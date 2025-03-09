import asyncio
import logging
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import Message, BotCommand, BotCommandScopeChat, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.enums import ParseMode
from dotenv import load_dotenv
import os
from database import Session, User, UserMessage
from utils import (
    broadcast_message, 
    get_broadcast_stats,
    save_user_message,
    get_unread_messages,
    mark_message_as_read,
    get_user_by_id,
    get_dialog,
    delete_dialog,
    clear_broadcast_stats,
    send_message_with_retry
)

# Загрузка переменных окружения
load_dotenv()

# Настройка логирования
logging.basicConfig(level=logging.INFO)

# Инициализация бота и диспетчера
bot = Bot(token=os.getenv("BOT_TOKEN"))
dp = Dispatcher()

# Словарь для хранения состояний пользователей
user_states = {}

# Команды для обычных пользователей
user_commands = [
    BotCommand(command="start", description="Начать работу с ботом"),
    BotCommand(command="help", description="Показать справку")
]

# Команды для администратора
admin_commands = [
    BotCommand(command="start", description="Начать работу с ботом"),
    BotCommand(command="help", description="Показать справку"),
    BotCommand(command="broadcast", description="Начать рассылку"),
    BotCommand(command="stats", description="Статистика рассылок"),
    BotCommand(command="messages", description="Сообщения от пользователей"),
    BotCommand(command="clear_stats", description="Очистить статистику")
]

def get_reply_keyboard(message_id: int) -> InlineKeyboardMarkup:
    """Создание клавиатуры для ответа на сообщение"""
    keyboard = [
        [InlineKeyboardButton(text="✍️ Ответить", callback_data=f"reply_{message_id}")],
        [InlineKeyboardButton(text="🗑 Удалить", callback_data=f"delete_{message_id}")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def get_stats_keyboard() -> InlineKeyboardMarkup:
    """Создание клавиатуры для статистики"""
    keyboard = [
        [InlineKeyboardButton(text="🗑 Очистить статистику", callback_data="clear_stats")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

async def setup_commands():
    """Настройка команд бота"""
    admin_id = int(os.getenv("ADMIN_ID"))
    
    # Устанавливаем команды для всех пользователей
    await bot.set_my_commands(user_commands)
    
    # Устанавливаем команды для администратора
    await bot.set_my_commands(
        admin_commands,
        scope=BotCommandScopeChat(chat_id=admin_id)
    )

# Обработчик команды /start
@dp.message(Command("start"))
async def cmd_start(message: Message):
    # Сохраняем пользователя в базу данных
    session = Session()
    user = session.query(User).filter(User.user_id == message.from_user.id).first()
    if not user:
        user = User(
            user_id=message.from_user.id,
            username=message.from_user.username,
            first_name=message.from_user.first_name,
            last_name=message.from_user.last_name
        )
        session.add(user)
        session.commit()
    session.close()
    
    # Разные приветствия для админа и обычных пользователей
    if message.from_user.id == int(os.getenv("ADMIN_ID")):
        await message.answer(
            "👋 Привет, администратор!\n\n"
            "Доступные команды:\n"
            "/broadcast - Начать рассылку\n"
            "/stats - Статистика рассылок\n"
            "/messages - Просмотр сообщений от пользователей\n"
            "/clear_stats - Очистить статистику\n"
            "/help - Помощь"
        )
    else:
        await message.answer(
            "👋 Привет! Я бот для связи с администрацией.\n\n"
            "Отправьте мне сообщение, и администратор ответит вам в ближайшее время."
        )

# Обработчик команды /broadcast
@dp.message(Command("broadcast"))
async def cmd_broadcast(message: Message):
    if message.from_user.id != int(os.getenv("ADMIN_ID")):
        return
    
    user_states[message.from_user.id] = "waiting_for_broadcast"
    await message.answer(
        "Отправьте сообщение для рассылки.\n"
        "Поддерживаются все типы сообщений (текст, фото, видео и т.д.)"
    )

# Обработчик команды /stats
@dp.message(Command("stats"))
async def cmd_stats(message: Message):
    if message.from_user.id != int(os.getenv("ADMIN_ID")):
        return
    
    session = Session()
    stats = get_broadcast_stats(session)
    session.close()
    
    if not stats:
        await message.answer("Пока нет статистики рассылок.")
        return
    
    response = "📊 Статистика рассылок:\n\n"
    for stat in stats:
        response += f"ID: {stat['id']}\n"
        response += f"Сообщение: {stat['message']}\n"
        response += f"Отправлено: {stat['sent']}\n"
        response += f"Ошибок: {stat['failed']}\n"
        response += f"Создано: {stat['created_at']}\n"
        if stat['completed_at']:
            response += f"Завершено: {stat['completed_at']}\n"
        response += "\n"
    
    await message.answer(response, reply_markup=get_stats_keyboard())

# Обработчик команды /messages
@dp.message(Command("messages"))
async def cmd_messages(message: Message):
    if message.from_user.id != int(os.getenv("ADMIN_ID")):
        return
    
    session = Session()
    messages = get_unread_messages(session)
    session.close()
    
    if not messages:
        await message.answer("Нет новых сообщений от пользователей.")
        return
    
    for msg in messages:
        response = "📬 Сообщение от пользователя:\n\n"
        response += f"👤 @{msg['username']} ({msg['created_at']}):\n"
        response += f"{msg['message']}\n\n"
        
        await message.answer(
            response,
            reply_markup=get_reply_keyboard(msg['id'])
        )

# Обработчик команды /help
@dp.message(Command("help"))
async def cmd_help(message: Message):
    if message.from_user.id == int(os.getenv("ADMIN_ID")):
        help_text = (
            "📚 Справка по использованию бота:\n\n"
            "/broadcast - Начать рассылку\n"
            "/stats - Просмотр статистики рассылок\n"
            "/messages - Просмотр сообщений от пользователей\n"
            "/clear_stats - Очистить статистику\n"
            "/help - Показать это сообщение\n\n"
            "Для ответа на сообщение используйте кнопку 'Ответить' под сообщением"
        )
    else:
        help_text = (
            "📚 Справка по использованию бота:\n\n"
            "Просто отправьте мне сообщение, и администратор ответит вам в ближайшее время."
        )
    await message.answer(help_text)

# Обработчик callback-запросов
@dp.callback_query()
async def process_callback(callback: types.CallbackQuery):
    if callback.from_user.id != int(os.getenv("ADMIN_ID")):
        await callback.answer("У вас нет прав для этого действия.")
        return
    
    if callback.data.startswith("reply_"):
        try:
            message_id = int(callback.data.split("_")[1])
            session = Session()
            user_message = session.query(UserMessage).filter(UserMessage.id == message_id).first()
            
            if not user_message:
                await callback.message.edit_text("Сообщение не найдено.")
                session.close()
                return
            
            user = user_message.user
            await callback.message.edit_text(
                f"Отправьте ответ пользователю @{user.username or 'Без username'}"
            )
            # Формируем состояние в формате: waiting_for_reply_user_id_message_id
            user_states[callback.from_user.id] = f"waiting_for_reply_{user.user_id}_{message_id}"
            session.close()
            return
        except (ValueError, IndexError) as e:
            logging.error(f"Ошибка при обработке callback: {e}")
            await callback.message.edit_text("Ошибка при обработке запроса.")
            return
            
    elif callback.data.startswith("delete_"):
        try:
            message_id = int(callback.data.split("_")[1])
            session = Session()
            message = session.query(UserMessage).filter(UserMessage.id == message_id).first()
            
            if not message:
                await callback.message.edit_text("Сообщение не найдено.")
                session.close()
                return
            
            session.delete(message)
            session.commit()
            await callback.message.edit_text("✅ Сообщение успешно удалено!")
            session.close()
            return
        except Exception as e:
            logging.error(f"Ошибка при удалении сообщения: {e}")
            await callback.message.edit_text("❌ Ошибка при удалении сообщения.")
            return
            
    elif callback.data == "clear_stats":
        session = Session()
        if clear_broadcast_stats(session):
            await callback.message.edit_text("✅ Статистика успешно очищена!")
        else:
            await callback.message.edit_text("❌ Ошибка при очистке статистики.")
        session.close()
        return

# Обработчик всех сообщений
@dp.message()
async def handle_message(message: Message):
    # Проверяем, является ли сообщение ответом на рассылку
    if message.from_user.id in user_states and user_states[message.from_user.id] == "waiting_for_broadcast":
        if message.from_user.id != int(os.getenv("ADMIN_ID")):
            return
        
        await message.answer("Начинаю рассылку...")
        session = Session()
        stats = await broadcast_message(bot, message, session)
        session.close()
        
        await message.answer(
            f"✅ Рассылка завершена!\n\n"
            f"Всего получателей: {stats['total']}\n"
            f"Успешно отправлено: {stats['sent']}\n"
            f"Ошибок: {stats['failed']}"
        )
        
        del user_states[message.from_user.id]
        return

    # Проверяем, ожидается ли ответ на сообщение пользователя
    if message.from_user.id in user_states and user_states[message.from_user.id].startswith("waiting_for_reply_"):
        if message.from_user.id != int(os.getenv("ADMIN_ID")):
            return
        
        try:
            # Разбираем строку состояния
            state = user_states[message.from_user.id]
            # Пропускаем первые 3 части (waiting_for_reply) и берем последние две
            parts = state.split("_")
            if len(parts) < 5:  # waiting_for_reply_user_id_message_id
                raise ValueError(f"Неверный формат состояния: {state}")
            
            user_id = int(parts[3])  # Берем предпоследнюю часть
            message_id = int(parts[4])  # Берем последнюю часть
            
            session = Session()
            user = get_user_by_id(session, user_id)
            
            if not user:
                await message.answer("Пользователь не найден.")
                del user_states[message.from_user.id]
                session.close()
                return
            
            # Сохраняем ответ в базу данных
            admin_message = save_user_message(
                session,
                message.from_user.id,
                message.text or "Медиа-сообщение"
            )
            
            if not admin_message:
                await message.answer("❌ Ошибка при сохранении ответа.")
                del user_states[message.from_user.id]
                session.close()
                return
            
            # Отправляем ответ пользователю
            try:
                success = await send_message_with_retry(bot, user.user_id, message)
                if success:
                    # Отмечаем исходное сообщение как прочитанное
                    mark_message_as_read(session, message_id)
                    await message.answer("✅ Ответ успешно отправлен!")
                else:
                    await message.answer("❌ Ошибка при отправке ответа. Попробуйте еще раз.")
            except Exception as e:
                logging.error(f"Ошибка при отправке ответа: {e}")
                await message.answer("❌ Произошла ошибка при отправке ответа. Попробуйте еще раз.")
            finally:
                del user_states[message.from_user.id]
                session.close()
                return
        except Exception as e:
            logging.error(f"Ошибка при обработке ответа: {e}")
            await message.answer("❌ Произошла ошибка при обработке ответа. Попробуйте еще раз.")
            if message.from_user.id in user_states:
                del user_states[message.from_user.id]
            return

    # Сохраняем сообщение от пользователя
    if message.from_user.id != int(os.getenv("ADMIN_ID")):
        session = Session()
        save_user_message(session, message.from_user.id, message.text or "Медиа-сообщение")
        session.close()
        await message.answer("✅ Ваше сообщение получено! Администратор ответит вам в ближайшее время.")

# Функция запуска бота
async def main():
    await setup_commands()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main()) 