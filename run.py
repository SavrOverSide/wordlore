"""Runs the Wordlore bot and posts the word of the day to CHANNEL every morning."""
import asyncio
import logging
from datetime import date

from aiogram import Bot, Dispatcher
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from common.config import env
from common.daily import every_day
from lingvo.bot import WORDS, router


async def post_word(bot: Bot) -> None:
    channel = env("CHANNEL")
    if not channel:
        return
    me = await bot.get_me()
    w = WORDS[date.today().toordinal() % len(WORDS)]
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="🧠 Викторина / Quiz", url=f"https://t.me/{me.username}?start=quiz")
    ]])
    await bot.send_message(channel, f"<b>{w['word']}</b>\n\n🇷🇺 {w['ru']}\n\n🇬🇧 {w['en']}",
                           parse_mode="HTML", reply_markup=kb)


async def main() -> None:
    logging.basicConfig(level=logging.INFO)
    bot = Bot(env("BOT_TOKEN"))
    dp = Dispatcher()
    dp.include_router(router)
    await asyncio.gather(
        dp.start_polling(bot),
        every_day(env("POST_TIME", "10:00"), lambda: post_word(bot)),
    )


if __name__ == "__main__":
    asyncio.run(main())
