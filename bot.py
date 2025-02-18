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
from aiogram.utils.keyboard import InlineKeyboardBuilder
import requests
import config
import json
from typing import Optional

bot = Bot(token=config.TG_BOT_TOKEN)
Disp = Dispatcher()
router = Router()
Disp.include_router(router)
url = "http://127.0.0.1:5000"
headers = {config.FASTAPI_KEY_NAME: config.FASTAPI_TOKEN}

class States(StatesGroup):
    auth = State()
    mainmenu = State()
    in_task = State()

@Disp.message(StateFilter(None), Command('start'))
async def starting(sms, state: FSMContext):
    try:
        req = requests.get(f"{url}/check_id_user_tg/{sms.from_user.id}", headers=headers)
        if req.status_code == 404:
            await bot.send_message(sms.from_user.id, "Привет!\nДля авторизации введите: /auth {code}.")
        elif req.status_code == 200:
            await bot.send_message(sms.from_user.id, "Успешная авторизация. Добро пожаловать в главное меню!")
            id_user = json.loads(requests.get(f"{url}/get_id_user_by_id_user_tg/{sms.from_user.id}", headers=headers).text)['id_user']
            await state.update_data(id_user=id_user)
            await state.set_state(States.mainmenu)
        else:
            await bot.send_message(sms.from_user.id, "Произошла ошибка.")
    except Exception as e:
        await bot.send_message(sms.from_user.id, "Произошла ошибка.")

@Disp.message(StateFilter(None), Command('auth'))
async def auth_with_code(sms: types.Message, state: FSMContext):
    try:
        code = sms.text.split()[1]
        check_code = requests.get(f"{url}/check_auth_key/{code}", headers=headers)
        if check_code.status_code == 200:
            auth_user = requests.post(f"{url}/auth_user/?auth_key={code}&id_user_tg={sms.from_user.id}", headers=headers)
            if auth_user.status_code == 200:
                id_user = json.loads(requests.get(f"{url}/get_id_user_by_id_user_tg/{sms.from_user.id}", headers=headers).text)['id_user']
                await state.update_data(id_user=id_user)
                await state.set_state(States.mainmenu)
                await bot.send_message(sms.from_user.id, "Авторизация успешна! Добро пожаловать в главное меню.")
            else:
                await bot.send_message(sms.from_user.id, "Произошла ошибка авторизации. Попробуйте снова.")
        else:
            await bot.send_message(sms.from_user.id, "Неверный код. Попробуйте снова.")
    except IndexError:
        await bot.send_message(sms.from_user.id, "Используйте команду в формате: /auth {code}.")
    except Exception as e:
        await bot.send_message(sms.from_user.id, "Произошла ошибка. Попробуйте позже.")

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

@Disp.message(States.mainmenu, Command('start_task'))
async def start_task_handler(sms: types.Message, state: FSMContext):
    try:
        user_data = await state.get_data()
        id_user = user_data.get("id_user")

        if len(sms.text.split()) == 1:
            categories = requests.get(f"{url}/get_categories_by_id_user/{id_user}", headers=headers)
            if categories.status_code == 200:
                categories_list = categories.json()
                if categories_list:
                    await state.update_data(categories=categories_list, current_page=0)
                    await show_categories_page(sms.from_user.id, state)
                else:
                    await bot.send_message(sms.from_user.id, "У вас пока нет категорий. Создайте новую.")
            else:
                await bot.send_message(sms.from_user.id, "Произошла ошибка при получении категорий.")
        else:
            name_category = sms.text.split(maxsplit=1)[1]
            check_category = requests.get(
                f"{url}/check_category/",
                json={"id_user": id_user, "name_category": name_category},
                headers=headers
            )
            exists_category = check_category.json().get('exists', False)
            if check_category.status_code == 200:
                if not exists_category:
                    add_category = requests.post(
                        f"{url}/add_category/",
                        json={"id_user": id_user, "name_category": name_category},
                        headers=headers
                    )
                    if add_category.status_code != 200:
                        await bot.send_message(sms.from_user.id, "Не удалось добавить категорию.")
                        return

                start_task_response = requests.post(
                    f"{url}/start_task/",
                    json={"id_user": id_user, "name_category": name_category},
                    headers=headers
                )
                if start_task_response.status_code == 200:
                    await state.set_state(States.in_task)
                    await bot.send_message(sms.from_user.id, f"Задача '{name_category}' начата. Для остановки используйте /stop_task")
                else:
                    await bot.send_message(sms.from_user.id, "Не удалось начать задачу.")
            else:
                await bot.send_message(sms.from_user.id, "Произошла ошибка при проверке категории.")
    except Exception as e:
        await bot.send_message(sms.from_user.id, f"Произошла ошибка: {e}")

@Disp.callback_query(F.data == "prev_page")
async def prev_page(callback: types.CallbackQuery, state: FSMContext):
    user_data = await state.get_data()
    current_page = user_data.get("current_page", 0)
    if current_page > 0:
        await state.update_data(current_page=current_page - 1)
        await show_categories_page(callback.from_user.id, state, message=callback.message)
    await callback.answer()

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
    try:
        user_data = await state.get_data()
        id_user = user_data.get("id_user")
        name_category = callback.data.split("_", 2)[2]

        start_task_response = requests.post(
            f"{url}/start_task/",
            json={"id_user": id_user, "name_category": name_category},
            headers=headers
        )
        if start_task_response.status_code == 200:
            await state.set_state(States.in_task)
            await callback.message.delete()
            await bot.send_message(callback.from_user.id, f"Задача '{name_category}' начата. Для остановки используйте /stop_task")
        else:
            await bot.send_message(callback.from_user.id, "Не удалось начать задачу.")
        await callback.answer()
    except Exception as e:
        await bot.send_message(callback.from_user.id, f"Произошла ошибка: {e}")

@Disp.message(States.in_task, Command('stop_task'))
async def stop_task_handler(message: types.Message, state: FSMContext):
    await state.set_state(States.mainmenu)
    await message.answer("Задача остановлена. Возврат в главное меню.")

@Disp.message(States.in_task)
async def handle_other_commands_in_task(message: types.Message):
    await message.answer("Доступна только команда /stop_task")

if __name__ == "__main__":
    Disp.run_polling(bot)