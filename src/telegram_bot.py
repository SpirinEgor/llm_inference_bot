from html import escape
from os import environ
from uuid import uuid4

from loguru import logger
from telegram import (
    Update,
    InlineQueryResultArticle,
    InputTextMessageContent,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.constants import ParseMode
from telegram.ext import Application, ContextTypes, CommandHandler, InlineQueryHandler, ChosenInlineResultHandler

from src.dialogue_tracker import DialogueTracker

_TG_API_TOKEN = "TG_API_TOKEN"
_TG_USERS_PREFIX = "tg_"

WHITELIST_FILE = "tg_id_whitelist.txt"

MESSAGE_TEMPLATE = "<b>Q:</b> {}\n<b>A:</b> {}"
IN_PROGRESS_MSG = "<i>In progress...</i>"


def validate_user(user_id: int) -> bool:
    with open(WHITELIST_FILE, "r") as f:
        for line in f:
            if int(line) == user_id:
                return True
    return False


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send a message when the command `/start` is issued."""
    user = update.message.from_user
    await update.message.reply_text(f"Hi, {user.username} ({user.id})! The bot is in closed beta testing, stay tuned 🤙")


async def inline_query(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle the inline query. This is run when you type: `@botusername <query>`"""
    user_id = update.inline_query.from_user.id
    if not validate_user(user_id):
        await update.inline_query.answer(
            [],
            switch_pm_text="You must be a registered user",
            switch_pm_parameter=str(user_id),
            next_offset="",
            cache_time=0,
        )
        return

    query = update.inline_query.query
    if query == "":
        return

    keyboard = [[InlineKeyboardButton("🤙", callback_data="🤙")]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    results = [
        InlineQueryResultArticle(
            id=str(uuid4()),
            title=f"Q: {query}",
            input_message_content=InputTextMessageContent(
                MESSAGE_TEMPLATE.format(escape(query), IN_PROGRESS_MSG), parse_mode=ParseMode.HTML
            ),
            reply_markup=reply_markup,
        )
    ]

    await update.inline_query.answer(results, cache_time=0)


class UpdateInlineQuery:
    def __init__(self):
        self.dialogue_tracker = DialogueTracker(messages_in_history=0)

    async def __call__(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        inline_message_id = update.chosen_inline_result.inline_message_id
        query = update.chosen_inline_result.query
        user_id = update.chosen_inline_result.from_user.id

        response = self.dialogue_tracker.on_message(query, _TG_USERS_PREFIX + str(user_id))
        message = MESSAGE_TEMPLATE.format(escape(query), escape(response))
        await context.bot.editMessageText(message, inline_message_id=inline_message_id, parse_mode=ParseMode.HTML)


def main():
    logger.info(f"Starting Telegram bot")
    token = environ.get(_TG_API_TOKEN)

    # Create the Application and pass it your bot's token.
    application = Application.builder().token(token).build()

    # on different commands - answer in Telegram
    application.add_handler(CommandHandler("start", start))

    # on non command i.e message - echo the message on Telegram
    application.add_handler(InlineQueryHandler(inline_query))

    on_chosen_inline_query = UpdateInlineQuery()
    application.add_handler(ChosenInlineResultHandler(on_chosen_inline_query))

    # Run the bot until the user presses Ctrl-C
    application.run_polling()


if __name__ == "__main__":
    main()
