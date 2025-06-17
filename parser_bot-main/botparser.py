import sqlite3
import asyncio
import re
from KUR_playwright import parse_component
from aiogram import types
from aiogram.fsm.context import FSMContext
from concurrent.futures import ThreadPoolExecutor
from aiogram import Bot, Dispatcher
from aiogram.fsm.state import State, StatesGroup
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram import Router, F
import random
import time

MAX_ATTEMPTS = 8  # Максимальное количество попыток до блокировки
BLOCK_TIME = 60  # Время блокировки в секундах

API_TOKEN = ''

ADMIN_USERNAMES = []  # Имена пользователей администраторов

bot = Bot(token=API_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)
router = Router()

MAX_WINNERS = 1

# Подключение к базе данных SQLite для хранения пользователей
conn = sqlite3.connect('bot_users.db')
cursor = conn.cursor()

# Создаем таблицу пользователей с добавленным столбцом для хранения языка
cursor.execute('''
             CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_id TEXT UNIQUE,
                username TEXT,
                referral_code TEXT UNIQUE,
                invites_count INTEGER DEFAULT 0,
                inviter TEXT,
                particip INTEGER DEFAULT 0,
                language TEXT  -- Столбец для хранения языка
    );
''')

cursor.execute('''
    UPDATE users
    SET username = NULL
    WHERE username = 'unknown';
''')
conn.commit()


def update_user_language(telegram_id, new_language):
    with sqlite3.connect('bot_users.db') as db_conn:
        db_cursor = db_conn.cursor()
        db_cursor.execute("UPDATE users SET language = ? WHERE telegram_id = ?", (new_language, telegram_id))
        db_conn.commit()


# Функция для добавления пользователей в базу данных
def add_user(telegram_id, username, language):
    cursor.execute("INSERT OR IGNORE INTO users (telegram_id, username, language) VALUES (?, ?, ?)",
                   (telegram_id, username, language))
    conn.commit()


# Функция для получения всех пользователей
def get_all_users():
    cursor.execute("SELECT telegram_id, language FROM users")
    return cursor.fetchall()


# Функция для проверки администраторов через username
def is_admin(username):
    return username in ADMIN_USERNAMES


###########################################PIZDA BEDA
def execute_query(query, parameters=()):
    with sqlite3.connect('bot_users.db') as conn:
        cursor = conn.cursor()
        cursor.execute(query, parameters)
        conn.commit()
        return cursor


def get_user_language(user_id):
    conn = sqlite3.connect('bot_users.db')
    cursor = conn.cursor()

    cursor.execute("SELECT language FROM users WHERE telegram_id = ?", (user_id,))
    result = cursor.fetchone()

    conn.close()

    if result:
        return result[0]  # Возвращаем язык пользователя
    else:
        return 'rus'

class CaptchaState(StatesGroup):
    waiting_for_captcha = State()

# FSM для выбора языка и ввода токена
class LanguageState(StatesGroup):
    choosing_language = State()


class TokenInfoState(StatesGroup):
    waiting_for_contract_address = State()
    waiting_for_broadcast_ru = State()
    waiting_for_broadcast_en = State()


# FSM для управления рассылкой
class BroadcastState(StatesGroup):
    waiting_for_broadcast_ru = State()
    waiting_for_broadcast_en = State()

@router.message(Command('start'))
async def start(message: types.Message, state: FSMContext):
    telegram_id = message.from_user.id
    username = message.from_user.username if message.from_user.username else 'unknown'

    # Генерация реферального кода для нового пользователя
    referral_link = f'ref_{telegram_id}'

    # Проверка, существует ли пользователь
    does_exist = bool(execute_query("SELECT telegram_id FROM users WHERE telegram_id = ?", (telegram_id,)).fetchone())

    if not does_exist:
        # Проверка, был ли указан реферальный код
        args = message.text.split()
        if len(args) > 1:
            ref_code = args[1]
            inviter = execute_query("SELECT telegram_id FROM users WHERE referral_code = ?", (ref_code,)).fetchone()

            if inviter:
                inviter_id = inviter[0]
                # Добавляем пользователя с указанием пригласившего
                execute_query("INSERT INTO users (telegram_id, username, referral_code, inviter) VALUES (?, ?, ?, ?)",
                              (telegram_id, username, referral_link, inviter_id))

                # Обновляем invites_count у пригласившего
                execute_query("UPDATE users SET invites_count = invites_count + 1 WHERE telegram_id = ?", (inviter_id,))
                invites_count = execute_query(
                    "SELECT invites_count FROM users WHERE telegram_id = ?", (inviter_id,)).fetchone()[0]
                if invites_count > 0:
                    execute_query("UPDATE users SET particip = 1 WHERE telegram_id = ?", (inviter_id,))
            else:
                # Добавляем пользователя без указания пригласившего
                execute_query("INSERT INTO users (telegram_id, username, referral_code, inviter) VALUES (?, ?, ?, ?)",
                              (telegram_id, username, referral_link, None))
        else:
            # Добавляем пользователя без реферального кода
            execute_query("INSERT INTO users (telegram_id, username, referral_code, inviter) VALUES (?, ?, ?, ?)",
                          (telegram_id, username, referral_link, None))

    # Генерация случайных чисел для капчи
    num1 = random.randint(1, 10)
    num2 = random.randint(1, 10)
    answer = num1 + num2

    # Сохранение ответа капчи в FSM
    await state.update_data(captcha_answer=answer, attempts=0)
    # Отправка капчи пользователю
    await message.answer(f"Captcha: {num1} + {num2}?")
    await state.set_state(CaptchaState.waiting_for_captcha)

# Проверка ответа капчи
@router.message(CaptchaState.waiting_for_captcha)
async def handle_captcha(message: types.Message, state: FSMContext):
    user_data = await state.get_data()
    correct_answer = user_data.get("captcha_answer")
    attempts = user_data.get("attempts", 0)
    # Получаем количество попыток, по умолчанию 0

    if message.text.isdigit() and int(message.text) == correct_answer:
        # Если капча пройдена, сбрасываем попытки и переходим к выбору языка
        await state.update_data(attempts=0)  # Сброс счётчика
        await message.answer("Выберите язык рассылки / Select your mailing language:", reply_markup=ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text="🇷🇺 Русский"), KeyboardButton(text="🇬🇧 English")]
            ], resize_keyboard=True, one_time_keyboard=True
        ))
        await state.set_state(LanguageState.choosing_language)
    else:
        # Если капча не пройдена
        attempts += 1
        if attempts >= 2:
            # Если 3 попытки исчерпаны, генерируем новую капчу
            num1 = random.randint(1, 20)
            num2 = random.randint(1, 20)
            new_answer = num1 + num2
            await state.update_data(captcha_answer=new_answer, attempts=0)  # Сбрасываем попытки и обновляем капчу
            await message.answer(f"Try again: {num1} + {num2}?")
        else:
            # Обновляем количество попыток
            await state.update_data(attempts=attempts)
            await message.answer(f"Wrong! Try again.")

# Выбор языка
@router.message(LanguageState.choosing_language)
async def choose_language(message: types.Message, state: FSMContext):
    # Определяем язык на основе выбора пользователя
    if message.text == "🇷🇺 Русский":
        language = "ru"
        await message.answer("Язык установлен на Русский 🇷🇺", reply_markup=types.ReplyKeyboardRemove())
        await message.answer(
            "👋 Добро пожаловать в бота для проверки смарт-контрактов — специальную разработку от проекта мемкоина BOF, созданную для борьбы за справедливость в криптомире. Мы придумали этого бота, чтобы сделать мир криптовалют честнее и безопаснее, помогая вам распознавать потенциально опасные и мошеннические проекты.\n\n"
            "🔗 Узнайте больше о проекте BOF:\n\n"
            " • Наш сайт\nhttps://balls-of-fate.com\n"
            " • Telegram\nhttps://t.me/+DSPSmcwxe0IyZWEy\n"
            " • Twitter\nhttps://x.com/bofcommunyti?s=21\n\n"
            "Вместе мы стоим на стороне честности и прозрачности! 🚀\n\n"
            "🔎 Пожалуйста, выберите платформу для поиска токена:"
        )
    elif message.text == "🇬🇧 English":
        language = "en"
        await message.answer("Language set to English 🇬🇧", reply_markup=types.ReplyKeyboardRemove())
        await message.answer(
            "Welcome to the smart contract verification bot, a special development from the BOF memcoin project created to fight for justice in the crypto world. We came up with this bot to make the world of cryptocurrencies more honest and safer by helping you identify potentially dangerous and fraudulent projects.\n\n"
            "🔗 Learn more about the BOF project:\n\n"
            " • Our website\nhttps://balls-of-fate.tilda.ws/\n"
            " • Telegram\nhttps://t.me/+DSPSmcwxe0IyZWEy\n"
            " • Twitter\nhttps://x.com/bofcommunyti?s=21\n\n"
            "Together we stand on the side of honesty and transparency! 🚀\n\n"
            "🔎 Please select the platform to search for the token:"
        )
    else:
        await message.answer("Пожалуйста, выберите язык / Please select your language")
        return

    # Сохраняем или обновляем язык пользователя в базе данных
    telegram_id = message.from_user.id
    username = message.from_user.username if message.from_user.username else 'unknown'

    # Проверяем, существует ли пользователь
    does_exist = bool(execute_query("SELECT telegram_id FROM users WHERE telegram_id = ?", (telegram_id,)).fetchone())
    if not does_exist:
        execute_query(
            "INSERT INTO users (telegram_id, username, language) VALUES (?, ?, ?)",
            (telegram_id, username, language)
        )
    else:
        execute_query("UPDATE users SET language = ? WHERE telegram_id = ?", (language, telegram_id))

    # Логирование для отладки
    print(f"User {username} ({telegram_id}) selected language: {language}")

    # Сброс состояния и переход к следующему этапу
    await state.clear()
    await message.answer("Выберите платформу для проверки токена:", reply_markup=get_platform_menu())


# Функция для создания меню выбора платформы
def get_platform_menu():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="⚙️sol"), KeyboardButton(text="🔺tron")],
            [KeyboardButton(text="📊base"), KeyboardButton(text="💎eth")],
            [KeyboardButton(text="🚀blast")]
        ],
        resize_keyboard=True,
        one_time_keyboard=False
    )


# Команды для выбора платформы

@router.message(F.text == "💎eth")
async def eth_command(message: types.Message, state: FSMContext):
    await message.answer("Enter the contract address on the Ethereum platform:",
                         reply_markup=types.ReplyKeyboardRemove())
    await state.update_data(platform="ethereum")
    await state.set_state(TokenInfoState.waiting_for_contract_address)


@router.message(F.text == "🚀blast")
async def blast_command(message: types.Message, state: FSMContext):
    await message.answer("Enter the contract address on the Blast platform:", reply_markup=types.ReplyKeyboardRemove())
    await state.update_data(platform="blast")
    await state.set_state(TokenInfoState.waiting_for_contract_address)


@router.message(F.text == "⚙️sol")
async def sol_command(message: types.Message, state: FSMContext):
    await message.answer("Enter the contract address on the Solana platform:", reply_markup=types.ReplyKeyboardRemove())
    await state.update_data(platform="solana")
    await state.set_state(TokenInfoState.waiting_for_contract_address)


@router.message(F.text == "📊base")
async def base_command(message: types.Message, state: FSMContext):
    await message.answer("Enter the contract address on the Base platform:", reply_markup=types.ReplyKeyboardRemove())
    await state.update_data(platform="base")
    await state.set_state(TokenInfoState.waiting_for_contract_address)


@router.message(F.text == "🔺tron")
async def tron_command(message: types.Message, state: FSMContext):
    await message.answer("Enter the contract address on the Tron platform:", reply_markup=types.ReplyKeyboardRemove())
    await state.update_data(platform="tron")
    await state.set_state(TokenInfoState.waiting_for_contract_address)


# Пул потоков и семафор с лимитом в N потоков
executor = ThreadPoolExecutor()
semaphore = asyncio.Semaphore(40)


@router.message(TokenInfoState.waiting_for_contract_address)
async def fetch_coin_info(message: types.Message, state: FSMContext):
    # Отправляем сообщение о начале сбора данных
    gathering_message = await message.answer("Please wait...")

    # Получаем данные состояния
    data = await state.get_data()
    platform = data.get("platform")
    contract_address = message.text.strip()

    # Функция для ограничения количества параллельных потоков
    async with semaphore:
        # Запуск parse_elements в отдельном потоке
        info = await parse_component(platform, contract_address)
    # Словарь сокращений для платформ
    platform_shortcuts = {
        "solana": "SOL",
        "ethereum": "ETH",
        "base": "BASE",
        "tron": "TRON",
        "blast": "BLAST"
    }

    def process_data(input_data, mode):
        # Тело process_data осталось без изменений
        if mode == 'volume':
            return input_data.replace("\n/\n", " | ")
        elif mode == 'clean_text':
            return re.sub(r'[A-Za-z]', '', input_data).strip()
        elif mode == 'clean_brackets':
            return input_data.replace("(", "").replace(")", "")
        elif mode == 'remove_trailing_bracket':
            return input_data.rstrip("()")
        elif mode == 'platform':
            return platform_shortcuts.get(input_data.lower(), input_data)
        elif mode == 'numeric':
            return re.sub(r'[^0-9$K.]', '', input_data).strip()
        elif mode == 'remove_fire':
            return input_data.replace("🔥", "").strip()
        elif mode == 'short_address':
            return input_data.split('/')[-1]
        elif mode == 'rug_probability':
            # Оставляем только число и % (например, "55.3%")
            return re.search(r'\d+(\.\d+)?%', input_data).group() if re.search(r'\d+(\.\d+)?%',
                                                                               input_data) else input_data
        else:
            return input_data

    # Используем универсальную функцию для обработки данных
    volume_24h = process_data(info[15], 'volume')
    buy_24h = process_data(info[16], 'volume')
    hold_24h = process_data(info[17], 'volume')
    net_24h = process_data(info[18], 'volume')
    dev_burnt = process_data(info[1], 'clean_text')
    lp_ratio = process_data(info[10], 'clean_brackets')
    owner = process_data(info[27], 'short_address')
    short_platform = process_data(platform, 'platform')
    rug_probability = process_data(info[4], 'rug_probability')
    bof = process_data('$BOF', 'clean_brackets')

    # Используем process_data для удаления 🔥 в Additional Info
    info_20 = process_data(info[20], 'remove_fire')
    info_22 = process_data(info[22], 'remove_fire')
    info_24 = process_data(info[24], 'remove_fire')
    info_26 = process_data(info[26], 'remove_fire')
    info_6 = process_data(info[6], 'remove_fire')

    solscan = f"<a href=\"https://solscan.io/token/{contract_address}#metadata\">\U0001F40D Solscan \n</a>"
    tronscan = f"<a href=\"https://tronscan.org/#/token20/{contract_address}#code\">\U0001F53A Tronscan \n</a>"
    etherscan = f"<a href=\"https://etherscan.io/token/{contract_address}#code\">\U0001F48E Etherscan \n</a>"

    if info[7] != '':
        response = (
            f'\U0001FA99 <code>{info[7]}</code> \n\n\n'
            f'{solscan if platform == "solana" else ""}'
            f'{etherscan if platform == "ethereum" else ""}'
            f'{tronscan if platform == "tron" else ""}'

            f'\U0001F517 <b>{short_platform}:</b> <code>{contract_address}</code>\n'

            f'\U0001F464 <b>Owner:</b> <code>{owner}</code>\n\n'
            f'\U0001F4B9 <b>LP Ratio:</b> {lp_ratio}\n'
            f'\U0001F4C8 <b>Holders:</b> {info[11]}\n'
            f'\U0001F4B0 <b>Market Cap:</b> {info[12]}\n'
            f'\U0001F4A7 <b>Liquidity Supply:</b> {info_6}\n'
            f'\U0001F30D <b>Volume (24h):</b>\n'
            f'      \U0001F4C9 <b>Total:</b> {volume_24h}\n'
            f'      \U0001F6D2 <b>Buys:</b> {buy_24h}\n'
            f'      \U0001F9F2 <b>Hold:</b> {hold_24h}\n'
            f'      \U0001F9FE <b>Net:</b> {net_24h}\n\n'

            f'\U0001F512 <b>LP Lock:</b> {info[14]} of Total Supply\n'
            f'\U0001F6E0 <b>Run/Hold/Add Liquidity:</b> {info[0]}\n'
            f'\U0001F525 <b>Dev Burnt:</b> {dev_burnt}\n'
            f'\U0001F51D <b>Top 10:</b> {info[2]}\n'
            f'\U0001F91D <b>Community Takeover:</b> {info[9]}\n'
            f'\U0001F465 <b>Insiders:</b> {info[3]}\n'
            f'\U0001F6A8 <b>Rug Probability:</b> {rug_probability}\n'

            f'\U00002139 <b>Additional Info:</b>\n'
            f'      \U0001F4CC {info[19]}: {info_20}\n'
            f'      \U0001F4CC {info[21]}: {info_22}\n'
            f'      \U0001F4CC {info[23]}: {info_24}\n'
            f'      \U0001F4CC {info[25]}: {info_26}\n\n'

            f'\U0001F310 <b>Socials:</b> '
            f'<a href="{info[28]}">X</a> | <a href="{info[29]}">Telegram</a> | <a href="{info[30]}">Website</a>\n\n\n'

            f'\u26A1 Produced by {bof} \n'
            f'<a href="https://t.me/+BXyihKj_ECk2Njky">\U0001F4AD BOF Telegram</a> | <a href="https://balls-of-fate.com/">\U0001F5A5 BOF Site</a>\n'
            f' <a href="https://dexscreener.com/solana/2jz7fuuy1nyjgas755janh8dmbeuarhumaueurhb7cgw">\U0001F4C8 BOF DEXCREENER</a> | <a href="https://jup.ag/swap/SOL-4yCuUMPFvaqxK71CK6SZc3wmtC2PDpDN9mcBzUkepump">\u26A1 BOF Site</a>\n\n'
            f'<code>CA: 4yCuUMPFvaqxK71CK6SZc3wmtC2PDpDN9mcBzUkepump</code>'
        )
    else:
        response = (
            'Please check your contract address/platform or try a little bit later \U0001F97A\U0001F97A\U0001F97A')
    # Удаляем сообщение о сборе данных
    await gathering_message.delete()

    # Отправка основного сообщения с информацией о монете
    await message.answer(response, parse_mode="HTML", disable_web_page_preview=True)
    await state.clear()

    # Возвращаем панель выбора платформ
    await message.answer("Select a platform to search for a token:", reply_markup=get_platform_menu())

@router.message(Command('myref'))
async def myref_command(message: types.Message):
    # Получаем базовую информацию о пользователе
    telegram_id = message.from_user.id
    username = message.from_user.username if message.from_user.username else 'unknown'
    referral_link = f'ref_{telegram_id}'

    # Получаем общее количество приглашений в системе (сумма всех рефералов от всех пользователей)
    total_system_invites = execute_query("""
       SELECT SUM(invites_count) as total 
       FROM users
       WHERE invites_count > 0
   """).fetchone()[0] or 0

    # Получаем количество приглашений текущего пользователя
    user_invites = execute_query("""
       SELECT COALESCE(invites_count, 0) as invites 
       FROM users 
       WHERE telegram_id = ?
   """, (telegram_id,)).fetchone()[0] or 0

    # Вычисляем процент шанса на победу (делим рефералы пользователя на общее количество)
    # Если общее количество 0, то шанс тоже 0
    winning_chance = (user_invites / total_system_invites * 100) if total_system_invites > 0 else 0

    # Проверяем, существует ли пользователь в базе
    does_exist = bool(execute_query("""
       SELECT telegram_id 
       FROM users 
       WHERE telegram_id = ?
   """, (telegram_id,)).fetchone())

    # Если пользователя нет - создаём его
    if not does_exist:
        try:
            execute_query("""
               INSERT INTO users (telegram_id, username, referral_code, inviter) 
               VALUES (?, ?, ?, ?)
           """, (telegram_id, username, referral_link, None))
        except Exception as e:
            print(f"Ошибка при добавлении пользователя: {e}")
            await message.answer("Произошла ошибка при регистрации. Попробуйте еще раз позже.")
            return

    # Формируем реферальную ссылку для приглашений
    invite_link = f'https://t.me/BOF_Scanner_bot?start={referral_link}'
    # Получаем язык пользователя для локализации
    language = get_user_language(telegram_id)

    # Текст сообщения на русском языке
    response_text_rus = (
        '🎉 <b>Ваша реферальная программа</b>\n\n'
        f'👥 Приглашено пользователей: {user_invites}\n'
        f'🌍 Всего приглашений в системе: {total_system_invites}\n'
        f'🎯 Ваши шансы на победу: {winning_chance:.2f}%\n\n'
        '❗️ Ваша уникальная ссылка:\n'
        f'<a href="{invite_link}">{invite_link}</a>\n\n'
        '💡 Приглашайте друзей и увеличивайте свои шансы на выигрыш!\n'
        '🏆 Чем больше приглашений - тем выше шанс победить!'
    )

    # Текст сообщения на английском языке
    response_text_eng = (
        '🎉 <b>Your Referral Program</b>\n\n'
        f'👥 Users invited: {user_invites}\n'
        f'🌍 Total system invites: {total_system_invites}\n'
        f'🎯 Your winning chance: {winning_chance:.2f}%\n\n'
        '❗️ Your unique link:\n'
        f'<a href="{invite_link}">{invite_link}</a>\n\n'
        '💡 Invite friends to increase your chances of winning!\n'
        '🏆 More invites - higher chance to win!'
    )

    # Создаём кнопку участия с соответствующим текстом на выбранном языке
    participate_button = InlineKeyboardButton(
        text="🎉 Участвовать" if language != 'en' else "🎉 Participate",
        callback_data="participate"
    )
    # Создаём клавиатуру с этой кнопкой
    markup = InlineKeyboardMarkup(inline_keyboard=[[participate_button]])

    # Выбираем текст на нужном языке
    response_text = response_text_eng if language == 'en' else response_text_rus
    # Отправляем сообщение пользователю с форматированием HTML и кнопкой
    await message.answer(response_text, parse_mode='HTML', reply_markup=markup)


@router.callback_query(F.data == "participate")
async def participate_callback(call: types.CallbackQuery):
    telegram_id = call.from_user.id

    # Проверка, существует ли пользователь в таблице `users`
    user = execute_query("SELECT * FROM users WHERE telegram_id = ?", (telegram_id,)).fetchone()
    if not user:
        await call.answer("Вы еще не зарегистрированы. Пожалуйста, используйте команду /start для регистрации.",
                          show_alert=True)
        return

    # Проверка, участвует ли пользователь уже в конкурсе
    if user[5] == 1:  # Поле `particip` установлено в 1
        await call.answer("Вы уже участвуете в конкурсе!", show_alert=True)
        return

    inviter_id = user[4]  # Поле `inviter`
    if inviter_id:
        execute_query("UPDATE users SET invites_count = invites_count + 1 WHERE telegram_id = ?", (inviter_id,))

        # Проверка, что количество приглашений больше нуля перед обновлением `particip`
        invites_count = \
            execute_query("SELECT invites_count FROM users WHERE telegram_id = ?", (inviter_id,)).fetchone()[0]
        if invites_count > 0:
            execute_query("UPDATE users SET particip = 1 WHERE telegram_id = ?", (telegram_id,))

    await call.message.answer("Вы успешно участвуете в конкурсе!", parse_mode='HTML')


@router.message(Command('set_winners'))
async def set_winners(message: types.Message):
    if not is_admin(message.from_user.username):
        await message.answer('У вас нет прав для выполнения этой команды.')
        return

    try:
        # Извлекаем количество победителей из сообщения (например, /set_winners 5)
        new_winners_count = int(message.text.split()[1])
        global MAX_WINNERS
        MAX_WINNERS = new_winners_count  # Обновляем переменную
        await message.answer(f"Количество победителей успешно изменено на {MAX_WINNERS}.")
    except (IndexError, ValueError):
        await message.answer("Пожалуйста, укажите корректное количество победителей. Пример: /set_winners 3")


@router.message(Command('delete_user'))
async def delete_user(message: types.Message):
    if not is_admin(message.from_user.username):
        await message.answer('У вас нет прав для выполнения этой команды.')
        return

    try:
        telegram_id = int(message.text.split()[1])
    except (IndexError, ValueError):
        await message.answer('Пожалуйста, укажите корректный telegram_id. Пример: /delete_user 123456789')
        return

    user = execute_query("SELECT * FROM users WHERE telegram_id = ?", (telegram_id,)).fetchone()
    if not user:
        await message.answer(f'Пользователь с ID {telegram_id} не найден.')
    else:
        inviter_of_user = user[5]  # Проверяем поле 'inviter'
        if inviter_of_user:
            try:
                # Уменьшаем количество приглашенных у пригласившего, не допуская отрицательных значений
                execute_query("""
                    UPDATE users 
                    SET invites_count = 
                        CASE 
                            WHEN invites_count > 0 THEN invites_count - 1 
                            ELSE 0 
                        END 
                    WHERE telegram_id = ?
                """, (inviter_of_user,))

                # Удаляем пользователя из базы данных
                execute_query("DELETE FROM users WHERE telegram_id = ?", (telegram_id,))

                # Сбрасываем поле `particip`, если количество приглашений стало меньше 1
                execute_query("UPDATE users SET particip = 0 WHERE invites_count < 1 AND telegram_id = ?",
                              (inviter_of_user,))

                await message.answer(f'Пользователь с ID {telegram_id} был удален.')
            except Exception as e:
                await message.answer(f"Произошла ошибка при удалении пользователя: {e}")
        else:
            # Удаляем пользователя без пригласившего
            try:
                execute_query("DELETE FROM users WHERE telegram_id = ?", (telegram_id,))
                await message.answer(f'Пользователь с ID {telegram_id} был удален.')
            except Exception as e:
                await message.answer(f"Произошла ошибка при удалении пользователя: {e}")


@router.message(Command('draw'))
async def draw_raffle(message: types.Message):
    if not is_admin(message.from_user.username):
        await message.answer('У вас нет прав для выполнения этой команды.')
        return

    users = execute_query("SELECT telegram_id, username, invites_count FROM users WHERE invites_count > 0").fetchall()

    if len(users) < MAX_WINNERS:
        await message.answer('Недостаточно участников для проведения розыгрыша.')
        return

    # Используем invites_count как веса
    winners = set()
    while len(winners) < MAX_WINNERS:
        selected = random.choices(users, weights=[user[2] for user in users], k=1)[0]
        winners.add(selected)  # `set` гарантирует уникальность

    # Формируем ответ для победителей
    response = []
    for index, winner in enumerate(winners, start=1):
        response.append(f"{'🥇' if index == 1 else '🥈' if index == 2 else '🥉' if index == 3 else '🎖'} {index} место\n"
                        f"👤 ID: {winner[0]}\n"
                        f"🔹 Username: {winner[1]}\n"
                        f"👥 Рефералы: {winner[2]}\n")

    result_message = 'Победители:\n' + '\n'.join(response)
    await message.answer(result_message)

    # Отправка сообщения разработчикам
    devs = [815422218, 469372487]
    for dev in devs:
        try:
            await bot.send_message(dev, 'Результаты розыгрыша:\n\n' + result_message)
        except Exception as e:
            print(f'Не удалось отправить сообщение администратору {dev}: {e}')


@router.message(Command('reset_users'))
async def reset_users_command(message: types.Message):
    if not is_admin(message.from_user.username):
        await message.answer('У вас нет прав для выполнения этой команды.')
        return

    execute_query("DELETE FROM users")
    await message.answer('Все пользователи были удалены.')


@router.message(Command('participants'))
async def show_participants(message: types.Message):
    if not is_admin(message.from_user.username):
        await message.answer('У вас нет прав для выполнения этой команды.')
        return

    # Запрос всех пользователей и сортировка по количеству приглашенных
    users = execute_query(
        "SELECT telegram_id, username, invites_count FROM users ORDER BY invites_count DESC"
    ).fetchall()

    # Проверка, если в базе нет зарегистрированных пользователей
    if not users:
        await message.answer('Нет зарегистрированных пользователей.')
        return

    # Формируем сообщение с участниками и количеством приглашений
    participants_message = "Участники конкурса:\n\n"
    for index, user in enumerate(users, start=1):
        telegram_id, username, invites_count = user
        if invites_count > 0:  # Учитываем только пользователей с приглашениями
            username_display = username if username else "нет_userme"
            participants_message += f"{index}. ID: {telegram_id}, UsName: @{username_display}, Added: {invites_count}\n"

            # Получаем список приглашенных данным пользователем
            invited_users = execute_query("""
                SELECT telegram_id, username, referral_code 
                FROM users 
                WHERE inviter = ?
            """, (telegram_id,)).fetchall()

            if invited_users:
                participants_message += "   Приглашенные пользователи:\n"
                for i, invited_user in enumerate(invited_users, 1):
                    inv_telegram_id, inv_username, inv_referral_code = invited_user
                    inv_username_display = inv_username if inv_username else "нет_userme"
                    participants_message += f"   {i}) @{inv_username_display} (ID: {inv_telegram_id})\n"
            participants_message += "\n"  # Добавляем пустую строку для разделения пользователей

    # Разбиваем сообщение на части, если оно слишком длинное (лимит Telegram - 4096 символов)
    if len(participants_message) > 4000:
        messages = [participants_message[i:i + 4000] for i in range(0, len(participants_message), 4000)]
        for msg in messages:
            await message.answer(msg)
    else:
        await message.answer(participants_message)


@router.message(Command('top10'))
async def show_top10(message: types.Message):
    # Запрос 10 пользователей с наибольшим количеством приглашений, отсортированных по убыванию
    top_users = execute_query(
        "SELECT telegram_id, username, invites_count FROM users WHERE invites_count > 0 AND particip = 1 "
        "ORDER BY invites_count DESC LIMIT 10"
    ).fetchall()


    # Проверка, если в базе нет пользователей с приглашениями
    if not top_users:
        await message.answer('Нет зарегистрированных пользователей.')
        return

    # Формируем сообщение с топ-10 участников
    top_message = "🏆 <b>Top 10 participants by invitation</b>:\n\n"
    medals = ["🥇", "🥈", "🥉"] + ["🎖"] * 7  # Эмодзи для каждого места

    for index, user in enumerate(top_users, start=1):
        telegram_id, username, invites_count = user
        username_display = f"@{username}" if username else "unknown"
        medal = medals[index - 1] if index <= 10 else "🎖"
        top_message += (
            f"{medal} <b>{index} spot</b>\n"
            f"👤 <b>ID:</b> <code>{telegram_id}</code>\n"
            f"🔹 <b>Username:</b> {username_display}\n"
            f"👥 <b>Added:</b> <code>{invites_count}</code>\n\n"
        )

    # Отправка собранного сообщения
    await message.answer(top_message, parse_mode="HTML")


@router.message(Command('help_adm'))
async def admin_help_command(message: types.Message):
    if not is_admin(message.from_user.username):
        await message.answer('У вас нет прав для выполнения этой команды.')
        return

    help_message = """
Список команд для администраторов:
/help_adm - Показать этот список команд.
/set_winners [число] - Установить количество победителей в розыгрыше.
/draw - Провести розыгрыш.
/participants - Показать участников конкурса и количество приглашенных.
/delete_user [user_id] - Удалить пользователя по его ID.
/broadcast - рассылка. Начни с фото, если оно требуется

/reset_users - Удалить всех пользователей.
    """
    await message.answer(help_message)

# Команда для рассылки сообщений с изображениями (только для админов)
@router.message(Command('broadcast'))
async def broadcast_message(message: types.Message, state: FSMContext):
    if not message.from_user.username:
        await message.answer("У вас нет username, поэтому вы не можете использовать эту команду.")
        return

    if not is_admin(message.from_user.username):
        await message.answer("У вас нет прав для выполнения этой команды.")
        return

    # Сохраняем фото, если оно было отправлено
    if message.photo:
        photo = message.photo[-1].file_id
        await state.update_data(photo=photo)

    await message.answer("Отправь фото, если требуется или просто введите текст на русском языке:")
    await state.set_state(BroadcastState.waiting_for_broadcast_ru)


# Обработчик для сохранения фото в рассылке
@router.message(BroadcastState.waiting_for_broadcast_ru, F.photo)
async def save_photo(message: types.Message, state: FSMContext):
    await state.update_data(photo=message.photo[-1].file_id)
    await message.answer("Фото сохранено. Введите текст на русском языке:")


# Обработчик для получения текста на русском языке
@router.message(BroadcastState.waiting_for_broadcast_ru)
async def handle_broadcast_ru(message: types.Message, state: FSMContext):
    await state.update_data(broadcast_ru=message.text)
    await message.answer("Теперь введите текст на английском языке:")
    await state.set_state(BroadcastState.waiting_for_broadcast_en)


# Обработчик для получения текста на английском языке и отправки рассылки
@router.message(BroadcastState.waiting_for_broadcast_en)
async def handle_broadcast_en(message: types.Message, state: FSMContext):
    data = await state.get_data()
    text_ru = data.get("broadcast_ru")
    text_en = message.text
    photo = data.get("photo")

    users = get_all_users()
    failed_users = []

    # Отправляем сообщения пользователям
    async def send_message(user_id, text):
        try:
            if photo:
                await bot.send_photo(user_id, photo=photo, caption=text)
            else:
                await bot.send_message(user_id, text)
        except Exception as e:
            print(f"Не удалось отправить сообщение пользователю {user_id}: {e}")
            failed_users.append(user_id)

    tasks = [
        send_message(user_id, text_ru if language == "ru" else text_en)
        for user_id, language in users
    ]

    await asyncio.gather(*tasks)

    if failed_users:
        await message.answer(f"Сообщение не было доставлено {len(failed_users)} пользователям.")
    else:
        await message.answer("Сообщение успешно разослано.")
    await state.clear()


# Запуск бота
async def main():
    dp.include_router(router)
    await dp.start_polling(bot)


if __name__ == '__main__':
    asyncio.run(main())
    conn.close()