from fastapi import FastAPI, HTTPException,Depends,Header, status
from fastapi.security import APIKeyHeader
from fastapi.responses import JSONResponse
import uvicorn
import asyncpg, asyncio
import config
import string, random
from pydantic import BaseModel
from datetime import datetime, timedelta
from typing import Annotated, Union
import json
app = FastAPI()
API_KEY_NAME = config.FASTAPI_KEY_NAME
api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=False)



class JsonCategory(BaseModel):
    id_user: int
    name_category: str
class JsonStartTask(BaseModel):
    id_user: int
    name_category: str



def generate_code():
    letter = random.choice(string.ascii_uppercase)  # Генерируем случайную букву (заглавную)
    digits = ''.join(random.choices(string.digits, k=5))  # Генерируем 5 случайных цифр
    return letter + digits
def get_api_key(api_key: str = Depends(api_key_header)):
    if api_key == config.FASTAPI_TOKEN:
        return api_key
    else:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid or missing API Key",
        )



async def create_db_pool():
    return await asyncpg.create_pool(config.DB_URL,max_inactive_connection_lifetime=3)
async def get_db():
    pool = await create_db_pool()
    async with pool.acquire() as connection:
        yield connection


@app.get("/date_stats_chronological/")
async def date_stats_chronological(id_user: int, date_user: str, api_key: str = Depends(get_api_key),
                                   conn: asyncpg.Connection = Depends(get_db)):
    try:
        # Преобразуем дату из формата dd.mm.yyyy в datetime
        date_obj = datetime.strptime(date_user, "%d.%m.%Y")
        date = date_obj.date()
        date_yesterday = date - timedelta(days=1)
        date_tomorrow = date + timedelta(days=1)

        # Вычисляем временные границы
        date_start = datetime.combine(date, datetime.min.time())
        date_end = datetime.combine(date, datetime.max.time())

        res = await conn.fetch("""
            SELECT 
                t.start_time,
                t.end_time,
                c.name_category,
                CASE
                    WHEN t.start_time::date = $1 THEN $3  -- Началась вчера
                    ELSE t.start_time::date  -- Началась сегодня
                END as adjusted_date
            FROM tasks t
            JOIN categories c ON t.id_category = c.id_category
            WHERE 
                t.id_user = $4
                AND c.id_user = $4
                AND t.end_time IS NOT NULL
                AND (
                    (t.start_time BETWEEN $1 AND $2)  -- Задачи, активные в целевом дне
                    OR (t.end_time BETWEEN $1 AND $2)
                )
            ORDER BY GREATEST(t.start_time, $1), t.start_time
        """, date_start, date_end, date_yesterday, id_user)

        if res:
            # Преобразуем записи в список словарей и форматируем даты
            formatted_records = []
            for record in res:
                formatted = dict(record)
                # Форматируем время для вывода
                formatted['start_time'] = formatted['start_time'].strftime('%H:%M')
                if formatted['end_time']:
                    formatted['end_time'] = formatted['end_time'].strftime('%H:%M')
                formatted_records.append(formatted)
            return formatted_records
        else:
            raise HTTPException(status_code=404, detail="Нет данных за указанную дату")

    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Неверный формат даты: {e}")
    except asyncpg.PostgresError as e:
        raise HTTPException(status_code=500, detail=f"Ошибка базы данных: {e}")
@app.get("/date_stats_seconds/")
async def date_stats_seconds(id_user: int, date_user: str, api_key: str = Depends(get_api_key), conn: asyncpg.Connection = Depends(get_db)):
    try:
        # Преобразуем дату из формата dd.mm.yyyy в yyyy-mm-dd
        date_obj = datetime.strptime(date_user, "%d.%m.%Y")
        date = date_obj.date()  # Получаем только дату без времени
        date_0 = datetime.combine(date, datetime.min.time())  # Начало дня
        date_23 = datetime.combine(date, datetime.max.time())  # Конец дня
        date_tomorrow = date + timedelta(days=1)

        res = await conn.fetch("""
            SELECT 
                c.name_category,
                SUM(
                    CASE
                        WHEN t.start_time < $1 THEN 
                            EXTRACT(EPOCH FROM LEAST(t.end_time, $2) - $1)
                        WHEN t.start_time::date = $3 AND t.end_time::date = $3 THEN 
                            EXTRACT(EPOCH FROM t.end_time - t.start_time)
                        WHEN t.start_time::date = $3 AND t.end_time::date = $4 THEN 
                            EXTRACT(EPOCH FROM $2 - t.start_time)
                    END
                ) AS total_time_seconds
            FROM tasks t
            JOIN categories c ON t.id_category = c.id_category
            WHERE 
                t.id_user = $5
                AND c.id_user = $5
                AND t.end_time IS NOT NULL
                AND (
                    (t.start_time::date = $3 AND t.end_time::date = $3)
                    OR
                    (t.start_time < $1 AND t.end_time::date = $3)
                    OR
                    (t.start_time::date = $3 AND t.end_time::date = $4)
                )
            GROUP BY c.name_category;
        """, date_0, date_23, date, date_tomorrow, id_user)

        if res:
            return res
        else:
            raise HTTPException(status_code=404, detail="No data found for the specified date")
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use dd.mm.yyyy")
    except asyncpg.PostgresError as e:
        raise HTTPException(status_code=500, detail=f"Database error: {e}")
@app.get("/today_stats_seconds/{id_user}")
async def today_stats_seconds(id_user: int,api_key: str = Depends(get_api_key),conn: asyncpg.Connection = Depends(get_db)):
    try:
        today=datetime.now() #3
        today_0=today.replace(hour=0, minute=0, second=0, microsecond=0) #1
        today_23=today.replace(hour=23, minute=59, second=59, microsecond=0) #2
        res=await conn.fetch("""SELECT 
    c.name_category, -- Выводим название категории вместо id_category
    SUM(
        CASE
            -- Если задача началась до 21 февраля, считаем время с 21 февраля 00:00
            WHEN t.start_time < $1 THEN 
                EXTRACT(EPOCH FROM LEAST(t.end_time, $2) - $1)
            -- Если задача началась 21 февраля, считаем полное время выполнения
            ELSE 
                EXTRACT(EPOCH FROM LEAST(t.end_time, $2) - t.start_time)
        END
    ) AS total_time_seconds
FROM tasks t
JOIN categories c ON t.id_category = c.id_category -- Присоединяем таблицу категорий
WHERE 
    t.id_user = $4 -- Учитываем только задачи для пользователя с id_user = 5
    AND c.id_user = $4 -- Учитываем только категории для пользователя с id_user = 5
    AND t.end_time IS NOT NULL -- Игнорируем задачи с end_time = NULL
    AND (
        -- Задачи, которые начались и закончились 21 февраля
        (t.start_time::date = $3 AND t.end_time::date = $3)
        OR
        -- Задачи, которые начались до 21 февраля, но закончились 21 февраля
        (t.start_time < $1 AND t.end_time::date = $3)
        OR
        -- Задачи, которые начались 21 февраля, но закончились после 21 февраля (но в пределах 21 февраля 23:59)
        (t.start_time::date = $3 AND t.end_time <= $2)
    )
GROUP BY c.name_category; -- Группируем по названию категории""", today_0,today_23,today,id_user)
#         res = await conn.fetch("""SELECT
#     id_category,
#     SUM(
#         CASE
#             -- Если задача началась до 21 февраля, считаем время с 21 февраля 00:00
#             WHEN start_time < $1 THEN
#                 EXTRACT(EPOCH FROM LEAST(end_time, $2) - $1)
#             -- Если задача началась 21 февраля, считаем полное время выполнения
#             ELSE
#                 EXTRACT(EPOCH FROM LEAST(end_time, $2) - start_time)
#         END
#     ) AS total_time_seconds
# FROM tasks
# WHERE
#     id_user = $4 -- Учитываем только задачи для пользователя с id_user = 5
#     AND end_time IS NOT NULL -- Игнорируем задачи с end_time = NULL
#     AND (
#         -- Задачи, которые начались и закончились 21 февраля
#         (start_time::date = $3 AND end_time::date = $3)
#         OR
#         -- Задачи, которые начались до 21 февраля, но закончились 21 февраля
#         (start_time < $1 AND end_time::date = $3)
#         OR
#         -- Задачи, которые начались 21 февраля, но закончились после 21 февраля (но в пределах 21 февраля 23:59)
#         (start_time::date = $3 AND end_time <= $2)
#     )
# GROUP BY id_category;""", today_0,today_23,today,id_user)
        if res:
            return dict(res)
        else:
            raise HTTPException(status_code=404, detail="Key not found")
    except asyncpg.PostgresError as e:
        raise HTTPException(status_code=500, detail=f"Database error: {e}")
@app.get("/today_stats_chronological/{id_user}")
async def today_stats_chronological(id_user: int,api_key: str = Depends(get_api_key),conn: asyncpg.Connection = Depends(get_db)):
    try:
        today=datetime.now() #3
        today_0=today.replace(hour=0, minute=0, second=0, microsecond=0) #1
        today_23=today.replace(hour=23, minute=59, second=59, microsecond=0) #2
        yesterday=today-timedelta(days=1) #4
        res=await conn.fetch("""SELECT 
    t.id_task,
    t.id_user,
    t.id_category,
    c.name_category, -- Добавляем название категории
    t.start_time,
    t.end_time
FROM tasks t
JOIN categories c ON t.id_category = c.id_category -- Присоединяем таблицу категорий
WHERE 
    t.id_user = $3 -- Учитываем только задачи для пользователя с id_user = 5
    AND c.id_user = $3 -- Учитываем только категории для пользователя с id_user = 5
    AND t.end_time IS NOT NULL -- Исключаем задачи с end_time = NULL
    AND (
        -- Задачи, которые начались 20 февраля и закончились 21 февраля
        (t.start_time::date = $2 AND t.end_time::date = $1)
        OR
        -- Задачи, которые начались и закончились 21 февраля
        (t.start_time::date = $1 AND t.end_time::date = $1)
    )
ORDER BY t.start_time; -- Сортируем по start_time в хронологическом порядке""", today,yesterday,id_user)
        if res:
            return res
        else:
            raise HTTPException(status_code=404, detail="Key not found")
    except asyncpg.PostgresError as e:
        raise HTTPException(status_code=500, detail=f"Database error: {e}")
@app.get("/generate_auth_key")
async def generate_auth_key(api_key: str = Depends(get_api_key),conn: asyncpg.Connection = Depends(get_db)):
    auth_key=generate_code()
    try:
        await conn.execute("INSERT INTO auth_keys (id_user_tg, auth_key) VALUES (0,$1)",auth_key)
        return auth_key
    except asyncpg.PostgresError as e:
        raise HTTPException(status_code=500, detail=f"Database error: {e}")

@app.get("/check_auth_key/{auth_key}")
async def check_auth_key(auth_key: str,api_key: str = Depends(get_api_key),conn: asyncpg.Connection = Depends(get_db)):
    print(auth_key)
    try:
        res=await conn.fetchrow("SELECT auth_key FROM auth_keys WHERE auth_key=$1",auth_key)
        if res:
            return dict(res)
        else:
            raise HTTPException(status_code=404, detail="Key not found")
    except asyncpg.PostgresError as e:
        raise HTTPException(status_code=500, detail=f"Database error: {e}")
@app.get("/get_id_user_by_id_user_tg/{id_user_tg}")
async def get_id_user_by_id_user_tg(id_user_tg: int,api_key: str = Depends(get_api_key),conn: asyncpg.Connection = Depends(get_db)):
    try:
        res=await conn.fetchrow("SELECT id_user FROM users WHERE id_user_tg=$1",id_user_tg)
        if res:
            return res
        else:
            raise HTTPException(status_code=404, detail="User not found")
    except asyncpg.PostgresError as e:
        raise HTTPException(status_code=500, detail=f"Database error: {e}")
@app.post("/auth_user/")
async def auth_user(auth_key: str,id_user_tg: int,api_key: str = Depends(get_api_key),conn: asyncpg.Connection = Depends(get_db)):
    print(auth_key)
    print(id_user_tg)
    try:
        res = await conn.fetchrow("SELECT auth_key FROM auth_keys WHERE auth_key=$1", auth_key)
        if not res:
            raise HTTPException(status_code=404, detail="Key not found")
        await conn.execute("UPDATE auth_keys SET id_user_tg=$1 WHERE auth_key=$2", id_user_tg,auth_key)
        await conn.execute("INSERT INTO users (id_user_tg, name_user) VALUES ($1,$2)",id_user_tg,"anonymous")
        return JSONResponse(
            status_code=200,
            content={"message": "User authorized successfully"}
        )
    except asyncpg.PostgresError as e:
        raise HTTPException(status_code=500, detail=f"Database error: {e}")


@app.post("/start_task/")
async def start_task(body: JsonStartTask, api_key: str = Depends(get_api_key),
                     conn: asyncpg.Connection = Depends(get_db)):
    try:
        # Проверяем существование категории
        res = await conn.fetchrow(
            "SELECT id_category FROM categories WHERE id_user=$1 AND LOWER(name_category)=$2",
            body.id_user,
            body.name_category.lower()
        )

        # Если категории нет, создаем ее
        if not res:
            await conn.execute(
                "INSERT INTO categories (id_user, name_category) VALUES ($1, $2)",
                body.id_user,
                body.name_category
            )
            res = await conn.fetchrow(
                "SELECT id_category FROM categories WHERE id_user=$1 AND LOWER(name_category)=$2",
                body.id_user,
                body.name_category.lower()
            )

        # Создаем задачу и возвращаем id_task
        row = await conn.fetchrow(
            "INSERT INTO tasks (id_user, id_category, start_time) VALUES ($1, $2, NOW()) RETURNING id_task",
            body.id_user,
            res['id_category']
        )
        id_task = row['id_task']

        return JSONResponse(
            status_code=200,
            content={"message": "Task started successfully", "id_task": id_task}
        )
    except asyncpg.PostgresError as e:
        raise HTTPException(status_code=500, detail=f"Database error: {e}")
@app.post("/stop_task/{id_task}")
async def stop_task(id_task: int, api_key: str = Depends(get_api_key), conn: asyncpg.Connection = Depends(get_db)):
    try:
        await conn.execute(
             "UPDATE tasks SET end_time=NOW() WHERE id_task=$1",id_task)
        return JSONResponse(
            status_code=200,
            content={"message": "Task stopped successfully"}
        )
    except asyncpg.PostgresError as e:
        raise HTTPException(status_code=500, detail=f"Database error: {e}")
@app.get("/get_categories_by_id_user/{id_user}")
async def get_categories_by_id_user(id_user: int,api_key: str = Depends(get_api_key),conn: asyncpg.Connection = Depends(get_db)):
    print(id_user)
    try:
        res=await conn.fetch("SELECT * FROM categories WHERE id_user=$1",id_user)
        if res:
            return res
        else:
            raise HTTPException(status_code=200, detail="User not found")
    except asyncpg.PostgresError as e:
        raise HTTPException(status_code=500, detail=f"Database error: {e}")
@app.get("/check_category/")
async def check_category(body: JsonCategory,api_key: str = Depends(get_api_key),conn: asyncpg.Connection = Depends(get_db)):
    try:
        res=await conn.fetch("SELECT * FROM categories WHERE id_user=$1 AND LOWER(name_category)=$2",body.id_user,body.name_category.lower())
        if res:
            return JSONResponse(
                status_code=200,
                content={"exists": True}
            )
        else:
            return JSONResponse(
                status_code=200,
                content={"exists": False}
            )
    except asyncpg.PostgresError as e:
        raise HTTPException(status_code=500, detail=f"Database error: {e}")
@app.post("/add_category/")
async def add_category(body: JsonCategory,api_key: str = Depends(get_api_key),conn: asyncpg.Connection = Depends(get_db)):
    print(body.id_user)
    print(body.name_category)
    try:
        await conn.execute("INSERT INTO categories (id_user, name_category) VALUES ($1,$2)",body.id_user,body.name_category)
        return JSONResponse(
            status_code=200,
            content={"message": "Category added successfully"}
        )
    except asyncpg.PostgresError as e:
        raise HTTPException(status_code=500, detail=f"Database error: {e}")

@app.get("/check_id_user_tg/{id_user_tg}")
async def check_id_user_tg(id_user_tg: int,api_key: str = Depends(get_api_key),conn: asyncpg.Connection = Depends(get_db)):
    print(id_user_tg)
    try:
        res=await conn.fetchrow("SELECT id_user_tg FROM users WHERE id_user_tg=$1",id_user_tg)
        if res:
            return dict(res)
        else:
            raise HTTPException(status_code=404, detail="User not found")
    except asyncpg.PostgresError as e:
        raise HTTPException(status_code=500, detail=f"Database error: {e}")

@app.get("/items")
async def read_items(api_key: str = Depends(get_api_key),conn: asyncpg.Connection = Depends(get_db)):
    try:
        res=await conn.fetch("SELECT * FROM users")
        res_dict=[dict(record) for record in res]
        print(type(res_dict))
        print(res_dict)
        return res_dict
    except asyncpg.PostgresError as e:
        raise HTTPException(status_code=500, detail=f"Database error: {e}")
@app.get("/header")
async def protected_route(api_key: str = Depends(get_api_key)):
    return {"message": "You have access to the protected route", "your_token": api_key}
if __name__ == "__main__":
    uvicorn.run("api:app", port=5000, log_level="info")