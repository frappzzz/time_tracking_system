from fastapi import FastAPI, HTTPException,Depends,Header, status
from fastapi.security import APIKeyHeader
import uvicorn
import asyncpg, asyncio
import config
import string, random
from typing import Annotated
import json
app = FastAPI()
API_KEY_NAME = config.FASTAPI_KEY_NAME
api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=False)
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
    return await asyncpg.create_pool(config.DB_URL)
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