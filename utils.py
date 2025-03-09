from aiogram import Bot
from aiogram.types import Message
from database import Session, User, Broadcast, UserMessage
from datetime import datetime
import asyncio
from typing import Union, List

async def send_message_with_retry(
    bot: Bot,
    chat_id: int,
    message: Message,
    max_retries: int = 3
) -> bool:
    """Отправка сообщения с повторными попытками"""
    for attempt in range(max_retries):
        try:
            if message.text:
                await bot.send_message(chat_id, message.text)
            elif message.photo:
                await bot.send_photo(chat_id, message.photo[-1].file_id, caption=message.caption)
            elif message.video:
                await bot.send_video(chat_id, message.video.file_id)
            elif message.document:
                await bot.send_document(chat_id, message.document.file_id)
            return True
        except Exception as e:
            if attempt == max_retries - 1:
                return False
            await asyncio.sleep(1)
    return False

async def broadcast_message(
    bot: Bot,
    message: Message,
    session: Session
) -> dict:
    """Выполнение массовой рассылки"""
    users = session.query(User).filter(User.is_active == True).all()
    total = len(users)
    sent = 0
    failed = 0
    
    # Создаем запись о рассылке
    broadcast = Broadcast(message_text=message.text or "Медиа-сообщение")
    session.add(broadcast)
    session.commit()
    
    for user in users:
        success = await send_message_with_retry(bot, user.user_id, message)
        if success:
            sent += 1
        else:
            failed += 1
        await asyncio.sleep(0.05)  # Задержка между отправками
    
    # Обновляем статистику
    broadcast.sent_count = sent
    broadcast.failed_count = failed
    broadcast.completed_at = datetime.utcnow()
    session.commit()
    
    return {
        "total": total,
        "sent": sent,
        "failed": failed
    }

def get_broadcast_stats(session: Session) -> List[dict]:
    """Получение статистики рассылок"""
    broadcasts = session.query(Broadcast).order_by(Broadcast.created_at.desc()).all()
    return [
        {
            "id": b.id,
            "message": b.message_text[:50] + "..." if len(b.message_text) > 50 else b.message_text,
            "sent": b.sent_count,
            "failed": b.failed_count,
            "created_at": b.created_at.strftime("%Y-%m-%d %H:%M:%S"),
            "completed_at": b.completed_at.strftime("%Y-%m-%d %H:%M:%S") if b.completed_at else None
        }
        for b in broadcasts
    ]

def save_user_message(session: Session, user_id: int, message_text: str) -> UserMessage:
    """Сохранение сообщения пользователя"""
    user = session.query(User).filter(User.user_id == user_id).first()
    if user:
        message = UserMessage(
            user_id=user.id,
            message_text=message_text
        )
        session.add(message)
        session.commit()
        return message
    return None

def get_unread_messages(session: Session) -> List[dict]:
    """Получение непрочитанных сообщений"""
    messages = session.query(UserMessage).filter(UserMessage.is_read == False).all()
    return [
        {
            "id": m.id,
            "user_id": m.user.user_id,
            "username": m.user.username or "Без username",
            "message": m.message_text,
            "created_at": m.created_at.strftime("%Y-%m-%d %H:%M:%S")
        }
        for m in messages
    ]

def get_dialog(session: Session, message_id: int) -> List[dict]:
    """Получение диалога по ID сообщения"""
    message = session.query(UserMessage).filter(UserMessage.id == message_id).first()
    if not message:
        return []
    
    # Получаем корневое сообщение
    root = message
    while root.parent_id:
        root = session.query(UserMessage).filter(UserMessage.id == root.parent_id).first()
    
    # Получаем все сообщения диалога
    messages = session.query(UserMessage).filter(
        (UserMessage.id == root.id) | 
        (UserMessage.parent_id == root.id)
    ).order_by(UserMessage.created_at).all()
    
    return [
        {
            "id": m.id,
            "user_id": m.user.user_id,
            "username": m.user.username or "Без username",
            "message": m.message_text,
            "created_at": m.created_at.strftime("%Y-%m-%d %H:%M:%S"),
            "is_admin": m.is_admin
        }
        for m in messages
    ]

def delete_dialog(session: Session, message_id: int) -> bool:
    """Удаление диалога по ID сообщения"""
    message = session.query(UserMessage).filter(UserMessage.id == message_id).first()
    if not message:
        return False
    
    # Получаем корневое сообщение
    root = message
    while root.parent_id:
        root = session.query(UserMessage).filter(UserMessage.id == root.parent_id).first()
    
    # Удаляем все сообщения диалога
    session.query(UserMessage).filter(
        (UserMessage.id == root.id) | 
        (UserMessage.parent_id == root.id)
    ).delete()
    session.commit()
    return True

def mark_message_as_read(session: Session, message_id: int) -> None:
    """Отметить сообщение как прочитанное"""
    message = session.query(UserMessage).filter(UserMessage.id == message_id).first()
    if message:
        message.is_read = True
        session.commit()

def get_user_by_id(session: Session, user_id: int) -> User:
    """Получение пользователя по ID"""
    return session.query(User).filter(User.user_id == user_id).first()

def clear_broadcast_stats(session: Session) -> bool:
    """Очистка статистики рассылок"""
    try:
        session.query(Broadcast).delete()
        session.commit()
        return True
    except:
        return False 