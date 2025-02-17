from fastapi import FastAPI, HTTPException,Depends,Header, status
from fastapi.security import APIKeyHeader
import uvicorn
import asyncpg, asyncio
import config
from typing import Annotated
import json
app = FastAPI()
API_KEY_NAME = config.FASTAPI_KEY_NAME
api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=False)
# Создание пула соединений
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
# Пример маршрута с использованием пула соединений
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