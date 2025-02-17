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
import requests
import config
import json

bot = Bot(token=config.TG_BOT_TOKEN)
Disp = Dispatcher()
router = Router()
Disp.include_router(router)
url = "http://127.0.0.1:5000"
headers = {config.FASTAPI_KEY_NAME: config.FASTAPI_TOKEN}
class States(StatesGroup):
    auth = State()
    confirm_auth=State()
    mainmenu=State()
    selectorcreate=State()
    create1=State()
    create2=State()
    create3=State()
    selectproject=State()
    workinprojectlead=State()
    workinprojectnotlead=State()
    setreminder=State()
@Disp.message(StateFilter(None), Command('start'))
async def starting(sms, state: FSMContext):
    try:
        req = requests.get(f"{url}/check_id_user_tg/{sms.from_user.id}",
                                      headers=headers)
        if req.status_code==404:
            await bot.send_message(sms.from_user.id, "Привет!\nДля авторизации введите: /auth {code}.")
        elif req.status_code==200:
            await bot.send_message(sms.from_user.id, "Успешная авторизация. Добро пожаловать в главное меню!")
        else:
            await bot.send_message(sms.from_user.id, "Произошла ошибка.")

    except:
        await bot.send_message(sms.from_user.id, "Произошла ошибка.")


@Disp.message(StateFilter(None), Command('auth'))
async def auth_with_code(sms: types.Message, state: FSMContext):
    try:
        # Извлекаем код из сообщения
        code = sms.text.split()[1]  # /code 123123 -> 123123
        print(code)
        check_code=requests.get(f"{url}/check_auth_key/{code}",
                     headers=headers)
        # Проверяем код (например, сравниваем с кодом из конфигурации)
        if check_code.status_code==200:  # Замените на вашу логику проверки кода
            # Если код верный, авторизуем пользователя
            auth_user=requests.post(f"{url}/auth_user/?auth_key={code}&id_user_tg={sms.from_user.id}",
                                      headers=headers)
            if auth_user.status_code==200:
                await state.set_state(States.mainmenu)
                await bot.send_message(sms.from_user.id, "Авторизация успешна! Добро пожаловать в главное меню.")
            else:
                await bot.send_message(sms.from_user.id, "Произошла ошибка авторизации. Попробуйте снова.")
        else:
            # Если код неверный, сообщаем об ошибке
            await bot.send_message(sms.from_user.id, "Неверный код. Попробуйте снова.")

    except IndexError:
        # Если код не был передан
        await bot.send_message(sms.from_user.id, "Используйте команду в формате: /auth {code}.")
    except Exception as e:
        await bot.send_message(sms.from_user.id, "Произошла ошибка. Попробуйте позже.")


Disp.run_polling(bot)