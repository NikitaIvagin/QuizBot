from questions import quiz_data
from data_base import create_table, update_quiz_index, update_score, get_score, get_quiz_index
from constants import TIME_DELAY

import asyncio
import aiosqlite
import logging
from aiogram import Bot, Dispatcher, types
from aiogram.filters.command import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder
from aiogram import F

import nest_asyncio
nest_asyncio.apply()

# Включаем логирование, чтобы не пропустить важные сообщения
logging.basicConfig(level=logging.INFO)

# Замените "YOUR_BOT_TOKEN" на ваш токен
API_TOKEN = 'YOUR_BOT_TOKEN'

# Объект бота
bot = Bot(token=API_TOKEN)
# Диспетчер
dp = Dispatcher()



# Зададим имя базы данных
DB_NAME = 'quiz_bot.db'


def generate_options_keyboard(answer_options, right_answer):
    builder = InlineKeyboardBuilder()
    i = 0
    for option in answer_options:
        builder.add(types.InlineKeyboardButton(
            text=option,
            callback_data=f"right_answer:{i}" if option == right_answer else f"wrong_answer:{i}")
        )
        i += 1

    builder.adjust(1)
    return builder.as_markup()


@dp.callback_query(F.data.startswith("right_answer"))
async def right_answer(callback: types.CallbackQuery):

    await callback.bot.edit_message_reply_markup(
        chat_id=callback.from_user.id,
        message_id=callback.message.message_id,
        reply_markup=None
    )

    current_question_index = await get_quiz_index(callback.from_user.id)
    await callback.message.answer("Ваш ответ: " + quiz_data[current_question_index]['options'][int(callback.data.split(":")[1])])
    await asyncio.sleep(TIME_DELAY)

    await callback.message.answer("Верно!")
    await asyncio.sleep(TIME_DELAY)
    # Обновление номера текущего вопроса в базе данных
    current_question_index += 1
    await update_quiz_index(callback.from_user.id, current_question_index)

    current_score = await get_score(callback.from_user.id)
    current_score += 1
    await update_score(callback.from_user.id, current_score)


    if current_question_index < len(quiz_data):
        await get_question(callback.message, callback.from_user.id)
    else:
        result = await get_score(callback.from_user.id)
        await callback.message.answer(f"Квиз завершен! Вы набрали {result}/{len(quiz_data)} баллов!")
        await asyncio.sleep(TIME_DELAY)

        # Показываем сравнение с предыдущими результатами
        best_score = await get_previous_best_score(callback.from_user.id)
        if best_score > 0:
            if result > best_score:
                await callback.message.answer(f"Новый рекорд! Превышен предыдущий лучший результат: {best_score}")
            else:
                await callback.message.answer(f"Ваш лучший результат: {best_score}/{len(quiz_data)}")


@dp.callback_query(F.data.startswith("wrong_answer"))
async def wrong_answer(callback: types.CallbackQuery):
    await callback.bot.edit_message_reply_markup(
        chat_id=callback.from_user.id,
        message_id=callback.message.message_id,
        reply_markup=None
    )
    current_question_index = await get_quiz_index(callback.from_user.id)
    await callback.message.answer("Ваш ответ: " + quiz_data[current_question_index]['options'][int(callback.data.split(":")[1])])
    await asyncio.sleep(TIME_DELAY)

    # Получение текущего вопроса из словаря состояний пользователя
    correct_option = quiz_data[current_question_index]['correct_option']

    await callback.message.answer(f"Неправильно. Правильный ответ: {quiz_data[current_question_index]['options'][correct_option]}")
    await asyncio.sleep(TIME_DELAY)

    # Обновление номера текущего вопроса в базе данных
    current_question_index += 1
    current_score = await get_score(callback.from_user.id)

    await update_quiz_index(callback.from_user.id, current_question_index)

    if current_question_index < len(quiz_data):
        await get_question(callback.message, callback.from_user.id)
    else:
        result = await get_score(callback.from_user.id)
        await callback.message.answer(f"Квиз завершен! Вы набрали {result}/{len(quiz_data)} баллов!")
        await asyncio.sleep(TIME_DELAY)

        best_score = await get_previous_best_score(callback.from_user.id)
        if best_score > 0:
            if result > best_score:
                await callback.message.answer(f"Новый рекорд! Превышен предыдущий лучший результат: {best_score}")
            else:
                await callback.message.answer(f"Ваш лучший результат: {best_score}/{len(quiz_data)}")


# Хэндлер на команду /start
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    builder = ReplyKeyboardBuilder()
    builder.add(types.KeyboardButton(text="Начать игру"))
    await message.answer("Добро пожаловать в квиз!", reply_markup=builder.as_markup(resize_keyboard=True))


async def get_question(message, user_id):
    # Получение текущего вопроса из словаря состояний пользователя
    current_question_index = await get_quiz_index(user_id)
    correct_index = quiz_data[current_question_index]['correct_option']
    opts = quiz_data[current_question_index]['options']
    kb = generate_options_keyboard(opts, opts[correct_index])
    await message.answer(f"{quiz_data[current_question_index]['question']}", reply_markup=kb)



async def start_new_quiz(user_id):
    async with aiosqlite.connect(DB_NAME) as db:
        # Получаем текущий счет перед сбросом
        cursor = await db.execute('SELECT score FROM quiz_state WHERE user_id = ?', (user_id,))
        result = await cursor.fetchone()

        if result and result[0] > 0:
            # Сохраняем предыдущий результат в историю
            await db.execute('INSERT INTO quiz_history (user_id, score) VALUES (?, ?)',
                           (user_id, result[0]))

        # Сбрасываем прогресс для нового квиза
        await db.execute('''INSERT OR REPLACE INTO quiz_state
                          (user_id, question_index, score) VALUES (?, 0, 0)''',
                       (user_id,))
        await db.commit()

async def get_previous_best_score(user_id):
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute('''SELECT MAX(score) FROM quiz_history
                                   WHERE user_id = ?''', (user_id,))
        result = await cursor.fetchone()
        return result[0] if result[0] else 0

async def get_last_score(user_id):
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute('''SELECT score FROM quiz_history
                                   WHERE user_id = ?
                                   ORDER BY completed_at DESC LIMIT 1''', (user_id,))
        result = await cursor.fetchone()
        return result[0] if result else 0



@dp.message(F.text=="Начать игру")
@dp.message(Command("quiz"))
async def cmd_quiz(message: types.Message):
    user_id = message.from_user.id

    # Сохраняем предыдущий результат и начинаем новый квиз
    await start_new_quiz(user_id)

    # Показываем предыдущие достижения
    best_score = await get_previous_best_score(user_id)
    last_score = await get_last_score(user_id)

    if best_score > 0:
        await message.answer(f"Ваш лучший результат: {best_score}/10")
        await asyncio.sleep(TIME_DELAY)
        if last_score and last_score != best_score:
            await message.answer(f"Последний результат: {last_score}/10")
            await asyncio.sleep(TIME_DELAY)

    await message.answer(f"Давайте начнем квиз! Всего будет {len(quiz_data)} вопросов.")
    await asyncio.sleep(TIME_DELAY)
    await get_question(message, user_id)



# Запуск процесса поллинга новых апдейтов
async def main():
    # Запускаем создание таблицы базы данных
    await create_table()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())