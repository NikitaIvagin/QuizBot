import aiosqlite

# Зададим имя базы данных
DB_NAME = 'quiz_bot.db'


async def create_table():
    async with aiosqlite.connect(DB_NAME) as db:
        # Таблица для текущего прогресса в квизе
        await db.execute('''CREATE TABLE IF NOT EXISTS quiz_state
                         (user_id INTEGER PRIMARY KEY,
                          question_index INTEGER DEFAULT 0,
                          score INTEGER DEFAULT 0)''')

        # Таблица для истории результатов
        await db.execute('''CREATE TABLE IF NOT EXISTS quiz_history
                         (id INTEGER PRIMARY KEY AUTOINCREMENT,
                          user_id INTEGER,
                          score INTEGER,
                          completed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
        await db.commit()



async def update_quiz_index(user_id, index):
    # Создаем соединение с базой данных (если она не существует, она будет создана)
    async with aiosqlite.connect(DB_NAME) as db:
        # Вставляем новую запись или заменяем ее, если с данным user_id уже существует
        await db.execute('UPDATE quiz_state SET question_index = ? WHERE user_id = ?', (index, user_id))
        # Сохраняем изменения
        await db.commit()



async def update_score(user_id, score):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute('UPDATE quiz_state SET score = ? WHERE user_id = ?', (score, user_id))
        await db.commit()



async def get_score(user_id):
     # Подключаемся к базе данных
     async with aiosqlite.connect(DB_NAME) as db:
        # Получаем запись для заданного пользователя
        async with db.execute('SELECT score FROM quiz_state WHERE user_id = (?)', (user_id, )) as cursor:
            # Возвращаем результат
            results = await cursor.fetchone()
            if results is not None:
                return results[0]
            else:
                return 0



async def get_quiz_index(user_id):
     async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute('SELECT question_index FROM quiz_state WHERE user_id = (?)', (user_id, )) as cursor:
            results = await cursor.fetchone()
            if results is not None:
                return results[0]
            else:
                return 0