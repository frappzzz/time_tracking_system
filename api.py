from fastapi import FastAPI, HTTPException,Depends,Header, status
from fastapi.security import APIKeyHeader
from fastapi.responses import JSONResponse
import uvicorn
import asyncpg, asyncio
import config
import string, random
from pydantic import BaseModel
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
async def start_task(body: JsonStartTask, api_key: str = Depends(get_api_key), conn: asyncpg.Connection = Depends(get_db)):
    try:
        res=await conn.fetchrow("SELECT id_category FROM categories WHERE id_user=$1 AND LOWER(name_category)=$2",body.id_user,body.name_category.lower())
        # Добавляем задачу в базу данных
        await conn.execute(
             "INSERT INTO tasks (id_user, id_category, start_time) VALUES ($1, $2, NOW())",
             body.id_user, res[0]
         )
        return JSONResponse(
            status_code=200,
            content={"message": "Task started successfully"}
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
            raise HTTPException(status_code=404, detail="User not found")
    except asyncpg.PostgresError as e:
        raise HTTPException(status_code=500, detail=f"Database error: {e}")
@app.get("/check_category/")
async def check_category(body: JsonCategory,conn: asyncpg.Connection = Depends(get_db)):
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