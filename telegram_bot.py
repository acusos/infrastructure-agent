import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.core import answer_question

load_dotenv()

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
AUTHORIZED_USER = str(os.getenv("AUTHORIZED_USER"))


async def start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    await update.message.reply_text(
        "Infrastructure Agent Online"
    )


async def handle_message(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    user_id = str(update.effective_user.id)

    if AUTHORIZED_USER and user_id != AUTHORIZED_USER:

        await update.message.reply_text(
            f"Unauthorized user id: {user_id}"
        )

        return

    question = update.message.text

    try:

        response = answer_question(question)

        await update.message.reply_text(response)

    except Exception as e:

        await update.message.reply_text(
            f"Error: {e}"
        )


def main():

    if not BOT_TOKEN:
        raise RuntimeError(
            "TELEGRAM_BOT_TOKEN missing from .env"
        )

    app = ApplicationBuilder().token(
        BOT_TOKEN
    ).build()

    app.add_handler(
        CommandHandler(
            "start",
            start
        )
    )

    app.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            handle_message
        )
    )

    print("Infrastructure Telegram Agent Running")

    app.run_polling()


if __name__ == "__main__":
    main()
