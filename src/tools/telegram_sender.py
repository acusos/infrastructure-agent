import os
import asyncio

from dotenv import load_dotenv
from telegram import Bot


load_dotenv()


BOT_TOKEN = os.getenv(
    "TELEGRAM_BOT_TOKEN"
)

AUTHORIZED_USER = os.getenv(
    "AUTHORIZED_USER"
)


async def _send(message):

    bot = Bot(BOT_TOKEN)

    await bot.send_message(
        chat_id=AUTHORIZED_USER,
        text=message,
    )


def send_telegram_message(message):

    if not BOT_TOKEN:
        return "TELEGRAM_BOT_TOKEN missing"

    if not AUTHORIZED_USER:
        return "AUTHORIZED_USER missing"

    try:

        asyncio.run(
            _send(message)
        )

        return "Message sent"

    except Exception as e:

        return str(e)
