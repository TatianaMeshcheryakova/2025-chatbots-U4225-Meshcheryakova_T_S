#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Telegram-бот "koshka_vse_uspevaet_bot" - ассистент для управления задачами
Автор: AI Assistant
Версия: 1.0 (Тест перезапуска)
"""

import logging
import sqlite3
import asyncio
from datetime import datetime, timedelta
from typing import List, Tuple, Optional
import os
from dotenv import load_dotenv

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

# Настройка логирования (должна быть до первого использования logger)
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Загружаем переменные окружения из .env файла
load_dotenv()

# Проверяем, что переменные окружения загружены (для локальной разработки)
if os.path.exists('.env'):
    logger.info("Файл .env найден, переменные окружения загружены")
else:
    logger.warning("Файл .env не найден, используются переменные окружения системы")

# Константы для приоритетов
PRIORITY_LEVELS = {
    'Высокий': 3,
    'Средний': 2,
    'Низкий': 1
}

PRIORITY_NAMES = {v: k for k, v in PRIORITY_LEVELS.items()}

class TaskManager:
    """Класс для управления задачами в базе данных SQLite"""
    
    def __init__(self, db_path: str = "tasks.db"):
        self.db_path = db_path
        self.init_database()
    
    def init_database(self):
        """Инициализация базы данных и создание таблицы задач"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS tasks (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id INTEGER NOT NULL,
                        task_text TEXT NOT NULL,
                        priority INTEGER NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        is_completed BOOLEAN DEFAULT FALSE
                    )
                ''')
                conn.commit()
                logger.info("База данных инициализирована успешно")
        except sqlite3.Error as e:
            logger.error(f"Ошибка при инициализации базы данных: {e}")
    
    def add_task(self, user_id: int, task_text: str, priority: int) -> int:
        """Добавление новой задачи в базу данных"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO tasks (user_id, task_text, priority)
                    VALUES (?, ?, ?)
                ''', (user_id, task_text, priority))
                conn.commit()
                task_id = cursor.lastrowid
                logger.info(f"Задача добавлена: ID={task_id}, User={user_id}, Task='{task_text}', Priority={priority}")
                return task_id
        except sqlite3.Error as e:
            logger.error(f"Ошибка при добавлении задачи: {e}")
            return None
    
    def get_active_tasks(self, user_id: int) -> List[Tuple[int, str, int]]:
        """Получение всех активных задач пользователя, отсортированных по приоритету"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT id, task_text, priority 
                    FROM tasks 
                    WHERE user_id = ? AND is_completed = FALSE
                    ORDER BY priority DESC, created_at ASC
                ''', (user_id,))
                return cursor.fetchall()
        except sqlite3.Error as e:
            logger.error(f"Ошибка при получении задач: {e}")
            return []
    
    def complete_task(self, user_id: int, task_id: int) -> bool:
        """Отметка задачи как выполненной"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    UPDATE tasks 
                    SET is_completed = TRUE 
                    WHERE id = ? AND user_id = ? AND is_completed = FALSE
                ''', (task_id, user_id))
                conn.commit()
                if cursor.rowcount > 0:
                    logger.info(f"Задача {task_id} отмечена как выполненная для пользователя {user_id}")
                    return True
                else:
                    logger.warning(f"Задача {task_id} не найдена или уже выполнена для пользователя {user_id}")
                    return False
        except sqlite3.Error as e:
            logger.error(f"Ошибка при выполнении задачи: {e}")
            return False
    
    def get_task_by_id(self, user_id: int, task_id: int) -> Optional[Tuple[int, str, int]]:
        """Получение задачи по ID для пользователя"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT id, task_text, priority 
                    FROM tasks 
                    WHERE id = ? AND user_id = ? AND is_completed = FALSE
                ''', (task_id, user_id))
                return cursor.fetchone()
        except sqlite3.Error as e:
            logger.error(f"Ошибка при получении задачи по ID: {e}")
            return None

    def get_history_tasks(self, user_id: int, days: int) -> List[Tuple[int, str, int, str]]:
        """
        Получить задачи пользователя за последние days дней по полю created_at.
        Возвращает список кортежей (id, task_text, priority, created_at).
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                # Получаем дату N дней назад
                cursor.execute(
                    '''SELECT id, task_text, priority, created_at 
                       FROM tasks 
                       WHERE user_id = ? AND created_at >= datetime('now', ?)''',
                    (user_id, f'-{days} days'))
                return cursor.fetchall()
        except sqlite3.Error as e:
            logger.error(f"Ошибка при получении истории задач: {e}")
            return []

# Создаем экземпляр менеджера задач
task_manager = TaskManager()

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /start"""
    welcome_message = """
🐱 Привет! Я бот "koshka_vse_uspevaet_bot" - твой ассистент для управления задачами!

Доступные команды:
/add [задача] [приоритет] - добавить задачу
/list - показать список задач
/done [номер] - отметить задачу как выполненную
/remind [номер] [минуты] - установить напоминание
/help - показать справку

Примеры:
/add Купить молоко Низкий
/add Подготовить презентацию Высокий
/done 1
/remind 2 30

Приоритеты: Высокий, Средний, Низкий
    """
    await update.message.reply_text(welcome_message)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /help"""
    help_message = """
📋 Справка по командам:

/add [задача] [приоритет]
• Добавляет новую задачу
• Приоритет: Высокий, Средний, Низкий (по умолчанию: Средний)
• Пример: /add Купить молоко Низкий

/list
• Показывает все активные задачи
• Задачи отсортированы по приоритету

/done [номер]
• Отмечает задачу как выполненную
• Пример: /done 1

/remind [номер] [минуты]
• Устанавливает напоминание
• Пример: /remind 2 30 (напоминание через 30 минут)

/help
• Показывает эту справку
    """
    await update.message.reply_text(help_message)

async def add_task_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /add для добавления задачи"""
    user_id = update.effective_user.id
    
    # Проверяем аргументы команды
    if not context.args:
        await update.message.reply_text(
            "❌ Ошибка: Не указана задача!\n"
            "Использование: /add [задача] [приоритет]\n"
            "Пример: /add Купить молоко Низкий"
        )
        return
    
    # Определяем приоритет
    priority_text = "Средний"  # По умолчанию
    task_text = " ".join(context.args)
    
    # Проверяем, указан ли приоритет в конце
    if len(context.args) >= 2:
        last_arg = context.args[-1]
        if last_arg in PRIORITY_LEVELS:
            priority_text = last_arg
            task_text = " ".join(context.args[:-1])
    
    # Проверяем, что задача не пустая
    if not task_text.strip():
        await update.message.reply_text(
            "❌ Ошибка: Задача не может быть пустой!\n"
            "Использование: /add [задача] [приоритет]"
        )
        return
    
    priority_level = PRIORITY_LEVELS[priority_text]
    
    # Добавляем задачу в базу данных
    task_id = task_manager.add_task(user_id, task_text, priority_level)
    
    if task_id:
        await update.message.reply_text(
            f"✅ Задача добавлена!\n"
            f"📝 Задача: {task_text}\n"
            f"⭐ Приоритет: {priority_text}\n"
            f"🔢 Номер: {task_id}"
        )
    else:
        await update.message.reply_text(
            "❌ Ошибка при добавлении задачи. Попробуйте еще раз."
        )

async def list_tasks_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /list для показа списка задач"""
    user_id = update.effective_user.id
    
    tasks = task_manager.get_active_tasks(user_id)
    
    if not tasks:
        await update.message.reply_text("📋 У вас пока нет активных задач!")
        return
    
    # Формируем сообщение со списком задач
    message_lines = ["📋 Ваши активные задачи:\n"]
    
    for task_id, task_text, priority_level in tasks:
        priority_name = PRIORITY_NAMES[priority_level]
        priority_emoji = "🔴" if priority_level == 3 else "🟡" if priority_level == 2 else "🟢"
        
        message_lines.append(
            f"{priority_emoji} {task_id}. {task_text} ({priority_name})"
        )
    
    message = "\n".join(message_lines)
    
    # Разбиваем сообщение на части, если оно слишком длинное
    if len(message) > 4000:
        # Отправляем по частям
        for i in range(0, len(message), 4000):
            part = message[i:i+4000]
            await update.message.reply_text(part)
    else:
        await update.message.reply_text(message)

async def done_task_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /done для отметки задачи как выполненной"""
    user_id = update.effective_user.id
    
    # Проверяем аргументы команды
    if not context.args or len(context.args) != 1:
        await update.message.reply_text(
            "❌ Ошибка: Укажите номер задачи!\n"
            "Использование: /done [номер]\n"
            "Пример: /done 1"
        )
        return
    
    try:
        task_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text(
            "❌ Ошибка: Номер задачи должен быть числом!\n"
            "Пример: /done 1"
        )
        return
    
    # Получаем информацию о задаче перед удалением
    task_info = task_manager.get_task_by_id(user_id, task_id)
    
    if not task_info:
        await update.message.reply_text(
            f"❌ Ошибка: Задача с номером {task_id} не найдена или уже выполнена!"
        )
        return
    
    # Отмечаем задачу как выполненную
    success = task_manager.complete_task(user_id, task_id)
    
    if success:
        task_text, priority_level = task_info[1], task_info[2]
        priority_name = PRIORITY_NAMES[priority_level]
        
        await update.message.reply_text(
            f"✅ Задача выполнена!\n"
            f"📝 {task_text} ({priority_name})\n"
            f"🎉 Отличная работа!"
        )
    else:
        await update.message.reply_text(
            f"❌ Ошибка при выполнении задачи {task_id}!"
        )

async def remind_task_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /remind для установки напоминания"""
    user_id = update.effective_user.id
    
    # Проверяем аргументы команды
    if not context.args or len(context.args) != 2:
        await update.message.reply_text(
            "❌ Ошибка: Укажите номер задачи и время!\n"
            "Использование: /remind [номер] [минуты]\n"
            "Пример: /remind 1 30"
        )
        return
    
    try:
        task_id = int(context.args[0])
        minutes = int(context.args[1])
    except ValueError:
        await update.message.reply_text(
            "❌ Ошибка: Номер задачи и время должны быть числами!\n"
            "Пример: /remind 1 30"
        )
        return
    
    # Проверяем корректность времени
    if minutes <= 0 or minutes > 1440:  # Максимум 24 часа
        await update.message.reply_text(
            "❌ Ошибка: Время должно быть от 1 до 1440 минут (24 часа)!\n"
            "Пример: /remind 1 30"
        )
        return
    
    # Проверяем существование задачи
    task_info = task_manager.get_task_by_id(user_id, task_id)
    
    if not task_info:
        await update.message.reply_text(
            f"❌ Ошибка: Задача с номером {task_id} не найдена или уже выполнена!"
        )
        return
    
    task_text, priority_level = task_info[1], task_info[2]
    priority_name = PRIORITY_NAMES[priority_level]
    
    # Планируем напоминание
    reminder_time = datetime.now() + timedelta(minutes=minutes)
    
    # Сохраняем информацию о напоминании в контексте
    if 'reminders' not in context.bot_data:
        context.bot_data['reminders'] = {}
    
    reminder_id = f"{user_id}_{task_id}_{int(reminder_time.timestamp())}"
    context.bot_data['reminders'][reminder_id] = {
        'user_id': user_id,
        'task_id': task_id,
        'task_text': task_text,
        'priority': priority_name,
        'reminder_time': reminder_time
    }
    
    # Запускаем асинхронное напоминание
    asyncio.create_task(send_reminder(context, reminder_id, minutes))
    
    await update.message.reply_text(
        f"⏰ Напоминание установлено!\n"
        f"📝 Задача: {task_text} ({priority_name})\n"
        f"⏱️ Время: через {minutes} минут\n"
        f"📅 {reminder_time.strftime('%H:%M, %d.%m.%Y')}"
    )

async def history_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Обработчик команды /history [число_дней].
    Показывает задачи, добавленные за последние N дней.
    """
    user_id = update.effective_user.id
    if not context.args or len(context.args) != 1:
        await update.message.reply_text(
            "❌ Укажите количество дней. Пример: /history 3"
        )
        return
    try:
        days = int(context.args[0])
        if days <= 0:
            raise ValueError
    except ValueError:
        await update.message.reply_text(
            "❌ Ошибка: количество дней должно быть положительным числом. Пример: /history 5"
        )
        return

    tasks = task_manager.get_history_tasks(user_id, days)
    if not tasks:
        await update.message.reply_text(
            f"📋 За последние {days} дней задачи не найдены."
        )
        return

    message_lines = [f"📋 Ваши задачи за последние {days} дней:"]
    for tid, ttext, tprio, tdate in tasks:
        priority = PRIORITY_NAMES.get(tprio, tprio)
        message_lines.append(f"{tid}. {ttext} ({priority}) | {tdate}")
    message = "\n".join(message_lines)
    await update.message.reply_text(message)

async def send_reminder(context: ContextTypes.DEFAULT_TYPE, reminder_id: str, delay_minutes: int):
    """Асинхронная функция для отправки напоминания"""
    try:
        # Ждем указанное время
        await asyncio.sleep(delay_minutes * 60)
        
        # Проверяем, что напоминание еще актуально
        if reminder_id not in context.bot_data.get('reminders', {}):
            return
        
        reminder_info = context.bot_data['reminders'][reminder_id]
        user_id = reminder_info['user_id']
        task_id = reminder_info['task_id']
        task_text = reminder_info['task_text']
        priority_name = reminder_info['priority']
        
        # Проверяем, что задача еще активна
        task_info = task_manager.get_task_by_id(user_id, task_id)
        
        if task_info:
            # Отправляем напоминание
            priority_emoji = "🔴" if priority_name == "Высокий" else "🟡" if priority_name == "Средний" else "🟢"
            
            reminder_message = (
                f"⏰ Напоминание!\n"
                f"{priority_emoji} Задача: {task_text} ({priority_name})\n"
                f"🔢 Номер: {task_id}\n"
                f"💡 Не забудьте выполнить задачу!"
            )
            
            await context.bot.send_message(chat_id=user_id, text=reminder_message)
            logger.info(f"Напоминание отправлено пользователю {user_id} для задачи {task_id}")
        else:
            logger.info(f"Задача {task_id} уже выполнена, напоминание отменено")
        
        # Удаляем напоминание из списка
        if 'reminders' in context.bot_data and reminder_id in context.bot_data['reminders']:
            del context.bot_data['reminders'][reminder_id]
            
    except Exception as e:
        logger.error(f"Ошибка при отправке напоминания {reminder_id}: {e}")

def main():
    """Основная функция для запуска бота"""
    # Получаем конфигурацию из переменных окружения
    bot_token = os.environ.get('BOT_TOKEN')
    url_webhook = os.environ.get('URL_WEBHOOK')  # публичный URL вашего сервера
    PORT = int(os.environ.get('PORT', '8080'))   # порт по умолчанию 8080
    WEBHOOK_PATH = '/webhook/'                  # фиксированный путь вебхука

    if not bot_token:
        logger.error("BOT_TOKEN не найден в переменных окружения. Проверьте .env или настройки окружения.")
        return

    if not url_webhook:
        logger.error("URL_WEBHOOK не задан. Укажите публичный адрес сервера в переменной окружения URL_WEBHOOK.")
        return
    
    # Создаем приложение
    application = Application.builder().token(bot_token).build()
    
    # Добавляем обработчики команд
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("add", add_task_command))
    application.add_handler(CommandHandler("list", list_tasks_command))
    application.add_handler(CommandHandler("done", done_task_command))
    application.add_handler(CommandHandler("remind", remind_task_command))
    application.add_handler(CommandHandler("history", history_command))
    
    # Запускаем бота в режиме webhook
    webhook_url = f"{url_webhook.rstrip('/')}{WEBHOOK_PATH}"
    logger.info(
        f"Запуск бота koshka_vse_uspevaet_bot через webhook на порту {PORT}, "
        f"путь {WEBHOOK_PATH}, полный URL: {webhook_url}"
    )
    application.run_webhook(
        listen="0.0.0.0",
        port=PORT,
        url_path=WEBHOOK_PATH.lstrip('/'),  # внутренний путь сервера без начального '/'
        webhook_url=webhook_url,            # внешний публичный URL, по которому Telegram обращается
        allowed_updates=Update.ALL_TYPES,
    )

if __name__ == '__main__':
    main()
