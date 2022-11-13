import asyncio
from typing import Optional
import aiomysql

from loguru import logger


class MariaDB:
    def __init__(self, bot):
        self.bot = bot
        self.pool: Optional[aiomysql.Pool] = None

    async def wait_for_pool(self):
        i = 0
        while self.pool is None and i < 10:
            logger.warning("Pool not initialized yet. waiting...")
            await asyncio.sleep(1)
            i += 1

        if self.pool is None:
            logger.error("Pool wait timeout! ABORTING")
            return False
        return True

    async def initialize_pool(self):
        while self.pool is None:
            try:
                self.pool = await aiomysql.create_pool(
                    **self.bot.config.dbcredentials,
                    autocommit=True,
                )
            except Exception as e:
                logger.error(e)
                await asyncio.sleep(1)
        logger.info("Initialized MariaDB connection pool")

    async def cleanup(self):
        if self.pool:
            self.pool.close()
            await self.pool.wait_closed()
        logger.info("Closed MariaDB connection pool")

    async def execute(self, statement, *params, one_row=False, one_value=False, as_list=False):
        if await self.wait_for_pool() and self.pool:
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    await cur.execute(statement, params)
                    data = await cur.fetchall()
            if data is None:
                return ()
            if data:
                if one_value:
                    return data[0][0]
                if one_row:
                    return data[0]
                if as_list:
                    return [row[0] for row in data]
                return data
            return ()
        raise Exception("Could not connect to the local MariaDB instance!")

    async def executemany(self, statement, params):
        if await self.wait_for_pool() and self.pool:
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    await cur.executemany(statement, params)
                    await conn.commit()
            return ()
        raise Exception("Could not connect to the local MariaDB instance!")
