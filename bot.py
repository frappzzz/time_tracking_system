from aiogram import Bot, Dispatcher, F, types, Router
from aiogram.filters.command import Command
from aiogram.fsm.context import FSMContext
from aiogram.filters import StateFilter
from aiogram.fsm.state import State, StatesGroup
from aiogram.enums.parse_mode import ParseMode
import asyncio
from aiogram.types import FSInputFile, BufferedInputFile
from aiogram.utils.media_group import MediaGroupBuilder
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, Message, ReplyKeyboardRemove
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder
import requests
from datetime import datetime, timedelta
import config
import json
from typing import Optional

# Инициализация бота и диспетчера
bot = Bot(token=config.TG_BOT_TOKEN)
Disp = Dispatcher()
router = Router()
Disp.include_router(router)

# Настройки API
url = "http://127.0.0.1:5000"
headers = {config.FASTAPI_KEY_NAME: config.FASTAPI_TOKEN}

def seconds_to_hours_minutes(seconds):
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    return f"{hours} ч. {minutes} мин."
# Состояния бота
class States(StatesGroup):
    auth = State()
    mainmenu = State()
    in_task = State()
    create_category = State()


# Команда /start
@Disp.message(StateFilter(None), Command('start'))
async def starting(sms: types.Message, state: FSMContext):
    try:
        # Проверяем, авторизован ли пользователь
        req = requests.get(f"{url}/check_id_user_tg/{sms.from_user.id}", headers=headers)
        if req.status_code == 404:
            await bot.send_message(sms.from_user.id, "Привет!\nДля авторизации введите: /auth {code}.")
        elif req.status_code == 200:
            await bot.send_message(sms.from_user.id, "Успешная авторизация. Добро пожаловать в главное меню!")
            id_user = \
            json.loads(requests.get(f"{url}/get_id_user_by_id_user_tg/{sms.from_user.id}", headers=headers).text)[
                'id_user']
            await state.update_data(id_user=id_user)
            await show_guide(sms.from_user.id)
            await show_main_menu(sms.from_user.id)
            await state.set_state(States.mainmenu)
        else:
            await bot.send_message(sms.from_user.id, "Произошла ошибка.")
    except Exception as e:
        await bot.send_message(sms.from_user.id, "Произошла ошибка.")


# Команда /auth
@Disp.message(StateFilter(None), Command('auth'))
async def auth_with_code(sms: types.Message, state: FSMContext):
    try:
        code = sms.text.split()[1]
        check_code = requests.get(f"{url}/check_auth_key/{code}", headers=headers)
        if check_code.status_code == 200:
            auth_user = requests.post(f"{url}/auth_user/?auth_key={code}&id_user_tg={sms.from_user.id}",
                                      headers=headers)
            if auth_user.status_code == 200:
                id_user = \
                json.loads(requests.get(f"{url}/get_id_user_by_id_user_tg/{sms.from_user.id}", headers=headers).text)[
                    'id_user']
                await state.update_data(id_user=id_user)
                await state.set_state(States.mainmenu)
                await bot.send_message(sms.from_user.id, "Авторизация успешна! Добро пожаловать в главное меню.")
                await show_guide(sms.from_user.id)
                await show_main_menu(sms.from_user.id)
            else:
                await bot.send_message(sms.from_user.id, "Произошла ошибка авторизации. Попробуйте снова.")
        else:
            await bot.send_message(sms.from_user.id, "Неверный код. Попробуйте снова.")
    except IndexError:
        await bot.send_message(sms.from_user.id, "Используйте команду в формате: /auth {code}.")
    except Exception as e:
        await bot.send_message(sms.from_user.id, "Произошла ошибка. Попробуйте позже.")


# Показ руководства
async def show_guide(user_id: int):
    guide_text = (
        "📚 Руководство по командам:\n\n"
        "/start - Начать работу с ботом\n"
        "/auth {code} - Авторизация\n"
        "/start_task {category} - Начать задачу с категорией. Если ее нет, то добавится новая категория\n"
        "/start_task - Начать задачу, далее выведет список категорий. Если их нет, то предложит создать новую категорию\n"
        "/help - Руководство по командам\n"
        "/stop_task - Остановить задачу\n\n"
        "Используйте кнопки ниже для создания задач и категорий."
    )
    await bot.send_message(user_id, guide_text)


# Показ главного меню
async def show_main_menu(user_id: int):
    builder = ReplyKeyboardBuilder()
    builder.button(text="Создать задачу")
    builder.button(text="Создать категорию")
    builder.adjust(2)
    await bot.send_message(user_id, "Выберите действие:", reply_markup=builder.as_markup(resize_keyboard=True))

@Disp.message(StateFilter(States.mainmenu), Command('help'))
async def helper(sms: types.Message, state: FSMContext):
    await show_guide(sms.from_user.id)
# Обработка создания задачи
@Disp.message(States.mainmenu, F.text == "Создать задачу")
@Disp.message(States.mainmenu, Command('start_task'))
async def start_task_handler(sms: types.Message, state: FSMContext):
    try:
        user_data = await state.get_data()
        id_user = user_data.get("id_user")

        if len(sms.text.split()) == 1 or sms.text == "Создать задачу":
            categories = requests.get(f"{url}/get_categories_by_id_user/{id_user}", headers=headers)
            if categories.status_code == 200:
                categories_list = categories.json()
                if 'detail' not in categories_list:
                    await state.update_data(categories=categories_list, current_page=0)
                    await show_categories_page(sms.from_user.id, state)
                else:
                    await bot.send_message(sms.from_user.id, "У вас пока нет категорий. Создайте новую. Введите название категории.")
                    await state.set_state(States.create_category)
            else:
                await bot.send_message(sms.from_user.id, "Произошла ошибка при получении категорий.")
        else:
            name_category = sms.text.split(maxsplit=1)[1]
            await start_task_flow(sms.from_user.id, name_category, state)
    except Exception as e:
        await bot.send_message(sms.from_user.id, f"Произошла ошибка: {e}")


# Обработка создания категории
@Disp.message(States.mainmenu, F.text == "Создать категорию")
async def create_category_handler(message: types.Message, state: FSMContext):
    await message.answer("Введите название новой категории:")
    await state.set_state(States.create_category)


# Обработка ввода названия категории
@Disp.message(States.create_category)
async def process_category_creation_handler(message: types.Message, state: FSMContext):
    try:
        user_data = await state.get_data()
        id_user = user_data.get("id_user")
        name_category = message.text.strip()

        # Проверяем существование категории
        check = requests.get(
            f"{url}/check_category/",
            json={"id_user": id_user, "name_category": name_category},
            headers=headers
        )

        if check.status_code != 200:
            await message.answer("Ошибка при проверке категории ❌")
            return

        if check.json()['exists']:
            await message.answer("⚠️ Эта категория уже существует")
            return

        # Создаем категорию
        response = requests.post(
            f"{url}/add_category/",
            json={"id_user": id_user, "name_category": name_category},
            headers=headers
        )

        if response.status_code == 200:
            await message.answer(f"✅ Категория '{name_category}' успешно создана!")
            await state.set_state(States.mainmenu)
            await show_main_menu(message.from_user.id)
        else:
            await message.answer("Не удалось создать категорию ❌")

    except Exception as e:
        await message.answer(f"🚫 Произошла ошибка: {e}")


# Запуск задачи
async def start_task_flow(user_id: int, name_category: str, state: FSMContext):
    user_data = await state.get_data()
    id_user = user_data.get("id_user")

    # Запускаем задачу через API
    response = requests.post(
        f"{url}/start_task/",
        json={"id_user": id_user, "name_category": name_category},
        headers=headers
    )

    if response.status_code == 200:
        id_task = response.json().get("id_task")
        await state.update_data(current_task_id=id_task)
        await state.set_state(States.in_task)
        await bot.send_message(
            user_id,
            f"⏳ Задача '{name_category}' начата!\n"
            f"Для остановки используйте /stop_task"
        )
    else:
        await bot.send_message(user_id, "🚫 Не удалось начать задачу")


# Показ страницы с категориями
async def show_categories_page(user_id: int, state: FSMContext, message: Optional[types.Message] = None):
    user_data = await state.get_data()
    categories_list = user_data.get("categories", [])
    current_page = user_data.get("current_page", 0)

    start_index = current_page * config.TG_CATEGORIES_PER_PAGE
    end_index = start_index + config.TG_CATEGORIES_PER_PAGE
    categories_page = categories_list[start_index:end_index]

    builder = InlineKeyboardBuilder()
    for category in categories_page:
        builder.button(
            text=category["name_category"],
            callback_data=f"start_task_{category['name_category']}"
        )

    if current_page > 0:
        builder.button(text="⬅️ Назад", callback_data="prev_page")
    if end_index < len(categories_list):
        builder.button(text="Вперед ➡️", callback_data="next_page")

    builder.adjust(2)

    text = "Выберите категорию:"
    if message:
        await message.edit_text(text=text, reply_markup=builder.as_markup())
    else:
        sent_message = await bot.send_message(user_id, text, reply_markup=builder.as_markup())
        await state.update_data(message_id=sent_message.message_id)


# Обработка перехода на предыдущую страницу
@Disp.callback_query(F.data == "prev_page")
async def prev_page(callback: types.CallbackQuery, state: FSMContext):
    user_data = await state.get_data()
    current_page = user_data.get("current_page", 0)
    if current_page > 0:
        await state.update_data(current_page=current_page - 1)
        await show_categories_page(callback.from_user.id, state, message=callback.message)
    await callback.answer()


# Обработка перехода на следующую страницу
@Disp.callback_query(F.data == "next_page")
async def next_page(callback: types.CallbackQuery, state: FSMContext):
    user_data = await state.get_data()
    current_page = user_data.get("current_page", 0)
    categories_list = user_data.get("categories", [])
    if (current_page + 1) * config.TG_CATEGORIES_PER_PAGE < len(categories_list):
        await state.update_data(current_page=current_page + 1)
        await show_categories_page(callback.from_user.id, state, message=callback.message)
    await callback.answer()


@Disp.callback_query(F.data.startswith("start_task_"))
async def start_task_from_button(callback: types.CallbackQuery, state: FSMContext):
    name_category = callback.data.split("_")[2]
    user_data = await state.get_data()
    id_user = user_data.get("id_user")

    # Запускаем задачу через API
    response = requests.post(
        f"{url}/start_task/",
        json={"id_user": id_user, "name_category": name_category},
        headers=headers
    )

    if response.status_code == 200:
        id_task = response.json().get("id_task")
        await state.update_data(current_task_id=id_task)
        await state.set_state(States.in_task)

        # Редактируем сообщение с кнопками, добавляя информацию о начале задачи
        await callback.message.edit_text(
            text=f"⏳ Задача '{name_category}' начата!\nДля остановки используйте /stop_task",
            reply_markup=None  # Убираем кнопки, так как задача уже начата
        )
    else:
        await callback.message.edit_text(
            text="🚫 Не удалось начать задачу",
            reply_markup=None
        )
    await callback.answer()


# Остановка задачи
@Disp.message(States.in_task, Command('stop_task'))
async def stop_task_handler(message: types.Message, state: FSMContext):
    user_data = await state.get_data()
    task_id = user_data.get("current_task_id")

    if not task_id:
        await message.answer("⚠️ Нет активной задачи для остановки")
        return

    # Останавливаем задачу через API
    response = requests.post(
        f"{url}/stop_task/{task_id}",
        headers=headers
    )

    if response.status_code == 200:
        await message.answer("🛑 Задача остановлена!")
        await state.set_state(States.mainmenu)
        await state.update_data(current_task_id=None)
        await show_main_menu(message.from_user.id)
    else:
        await message.answer("🚫 Не удалось остановить задачу")


# Обработка других команд во время выполнения задачи
@Disp.message(States.in_task)
async def handle_other_commands_in_task(message: types.Message):
    await message.answer("Доступна только команда /stop_task")

@Disp.message(States.mainmenu, Command('today_stats'))
async def today_stats_handler(message: types.Message, state: FSMContext):
    try:
        user_data = await state.get_data()
        id_user = user_data.get("id_user")

        # Получаем статистику за день в секундах
        stats_seconds = requests.get(f"{url}/today_stats_seconds/{id_user}", headers=headers)
        if stats_seconds.status_code != 200:
            await message.answer("Ошибка при получении статистики за день.")
            return

        # Получаем хронологический порядок задач
        chronological_stats = requests.get(f"{url}/today_stats_chronological/{id_user}", headers=headers)
        if chronological_stats.status_code != 200:
            await message.answer("Ошибка при получении хронологического порядка задач.")
            return

        # Преобразуем секунды в часы и минуты
        stats_dict = stats_seconds.json()
        stats_text = "📊 Статистика за день:\n\n"
        for category, seconds in stats_dict.items():
            hours = seconds // 3600
            minutes = (seconds % 3600) // 60
            stats_text += f"📌 {category}: {hours} ч. {minutes} мин.\n"

        # Добавляем хронологический порядок задач
        chronological_list = chronological_stats.json()
        stats_text += "\n⏳ Хронологический порядок задач:\n\n"
        for task in chronological_list:
            start_time = datetime.fromisoformat(task['start_time'])
            end_time = datetime.fromisoformat(task['end_time']) if task['end_time'] else None

            # Форматируем дату и время
            start_date_str = start_time.strftime('%d.%m %H:%M')
            if end_time:
                if start_time.date() == end_time.date():
                    # Задача началась и закончилась в один день
                    end_date_str = end_time.strftime('%H:%M')
                    stats_text += f"⏰ {task['name_category']}: {start_date_str} - {end_date_str}\n"
                else:
                    # Задача началась вчера, а закончилась сегодня
                    end_date_str = end_time.strftime('%d.%m %H:%M')
                    stats_text += f"⏰ {task['name_category']}: {start_date_str} - {end_date_str}\n"
            else:
                # Задача еще не завершена
                stats_text += f"⏰ {task['name_category']}: {start_date_str} - не завершено\n"

        await message.answer(stats_text)

    except Exception as e:
        await message.answer(f"Произошла ошибка: {e}")


@Disp.message(States.mainmenu, Command('stats'))
async def stats_handler(message: types.Message, state: FSMContext):
    try:
        # Парсим дату из сообщения
        date_str = message.text.split(maxsplit=1)[1].strip()

        # Валидация даты
        try:
            datetime.strptime(date_str, "%d.%m.%Y")
        except ValueError:
            await message.answer("❌ Используйте формат ДД.ММ.ГГГГ (например: 21.02.2024)")
            return

        user_data = await state.get_data()
        id_user = user_data.get("id_user")

        # Получаем статистику
        stats = await get_stats(id_user, date_str)

        # Формируем сообщение
        response = await format_stats_response(stats, date_str)

        await message.answer(response)

    except IndexError:
        await message.answer("📌 Используйте: /stats ДД.ММ.ГГГГ")
    except Exception as e:
        await message.answer(f"⚠️ Ошибка: {str(e)}")


async def get_stats(id_user: int, date_str: str) -> dict:
    """Получает данные статистики из API"""
    stats = {}

    # Запрос статистики по времени
    stats_response = requests.get(
        f"{url}/date_stats_seconds/{id_user}",
        params={"date_user": date_str,
                "id_user": id_user},
        headers=headers
    )
    stats['seconds'] = stats_response.json() if stats_response.status_code == 200 else {}

    # Запрос хронологии задач
    chrono_response = requests.get(
        f"{url}/date_stats_chronological/",
        params={"date_user": date_str,
                "id_user":id_user},
        headers=headers
    )
    stats['chrono'] = chrono_response.json() if chrono_response.status_code == 200 else []

    return stats


async def format_stats_response(stats: dict, date_str: str) -> str:
    """Форматирует данные статистики в читаемое сообщение"""
    # Заголовок
    response = f"📊 Статистика за {date_str}\n\n"

    # Секция с категориями
    if stats['seconds']:
        response += "🕒 Суммарное время по категориям:\n"
        for category, seconds in stats['seconds'].items():
            mins, secs = divmod(seconds, 60)
            hours, mins = divmod(mins, 60)
            response += f"▫️ {category}: {hours:02d}:{mins:02d}\n"
    else:
        response += "ℹ️ Нет данных о времени\n"

    # Секция с хронологией
    response += "\n📅 Хронология задач:\n"
    if stats['chrono']:
        for i, task in enumerate(stats['chrono'], 1):
            end_time = task['end_time'] or "не завершена"
            response += (
                f"{i}. {task['name_category']}\n"
                f"   🕑 {task['start_time']} — {end_time}\n"
            )
    else:
        response += "ℹ️ Нет данных о задачах\n"

    return response
# Запуск бота
if __name__ == "__main__":
    Disp.run_polling(bot)