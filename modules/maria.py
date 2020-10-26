# Project: Fansite Bot
# File: maria.py
# Author: Joinemm
# Date created: 16/10/20
# Python Version: 3.8

import aiomysql
import asyncio
from modules import logger as log, exceptions


logger = log.get_logger(__name__)


class MariaDB:
    def __init__(self, bot):
        self.bot = bot
        self.pool = None
        bot.loop.create_task(self.initialize_pool())

    async def wait_for_pool(self):
        i = 0
        while self.pool is None and i < 10:
            logger.warning("Pool not initialized yet. waiting...")
            await asyncio.sleep(1)
            i += 1

        if self.pool is None:
            logger.error("Pool wait timeout! ABORTING")
            return False
        else:
            return True

    async def initialize_pool(self):
        self.pool = await aiomysql.create_pool(**self.bot.config.dbcredentials)
        logger.info("Initialized MariaDB connection pool")

    async def cleanup(self):
        self.pool.close()
        await self.pool.wait_closed()
        logger.info("Closed MariaDB connection pool")

    async def execute(self, statement, *params, onerow=False):
        print(statement, *params)
        if await self.wait_for_pool():
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    await cur.execute(statement, params)
                    await conn.commit()
                    data = await cur.fetchall()
            if data is None:
                return ()
            else:
                if data:
                    return data[0] if onerow else data
                else:
                    return ()
        else:
            raise exceptions.Error("Could not connect to the local MariaDB instance!")
