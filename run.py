"""Runs the Wordlore bot; every morning posts the word of the day to CHANNEL and to DM subscribers."""
import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.types import BufferedInputFile, InlineKeyboardButton, InlineKeyboardMarkup

from common.config import env
from common.daily import every_day
from common.profile import setup_profile
from common.growth import broadcast, promo, ref_link, share_url
from lingvo.bot import WORDS, esc, router, store, word_index, word_of_day, word_photo
from lingvo.profile import COMMANDS, DESCRIPTION, SHORT
from lingvo.texts import T


async def post_word(bot: Bot) -> None:
    w = word_of_day()
    me = await bot.get_me()
    photo = await word_photo(w)

    channel = env("CHANNEL")
    if channel:
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🧠 Викторина / Quiz", url=f"https://t.me/{me.username}?start=quiz")],
            [InlineKeyboardButton(text="🔔 Слово дня в личку / Daily DM", url=f"https://t.me/{me.username}?start=sub")],
        ])
        caption = f"<b>{esc(w['word'])}</b>\n\n🇷🇺 {esc(w['ru'])}\n\n🇬🇧 {esc(w['en'])}\n\n{promo('words')}"
        try:
            await bot.send_photo(channel, photo, caption=caption[:1000], parse_mode="HTML", reply_markup=kb)
        except Exception:
            logging.exception("channel post failed")

    async def send_dm(uid: int) -> None:
        lg = store.get_lang(uid) or "ru"
        t = T[lg]
        link = ref_link(me.username, uid)
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=t["btn_quiz"], callback_data="m:quiz"),
             InlineKeyboardButton(text=t["btn_save"], callback_data=f"sv:{word_index(w)}")],
            [InlineKeyboardButton(text=t["btn_share"], url=share_url(link, t["share_word"].format(word=w["word"])))],
        ])
        await bot.send_photo(uid, photo, caption=f"<b>{esc(w['word'])}</b>\n\n{esc(w[lg])}"[:1000], parse_mode="HTML", reply_markup=kb)

    dead = await broadcast(store.subs(), send_dm)
    for uid in dead:  # people who blocked the bot are unsubscribed
        store.set_sub(uid, False)
    logging.info("daily DM: %s subscribers, %s dropped", len(store.subs()) + len(dead), len(dead))


async def main() -> None:
    logging.basicConfig(level=logging.INFO)
    bot = Bot(env("BOT_TOKEN"))
    dp = Dispatcher()
    dp.include_router(router)
    await setup_profile(bot, COMMANDS, DESCRIPTION, SHORT)
    await asyncio.gather(
        dp.start_polling(bot),
        every_day(env("POST_TIME", "10:00"), lambda: post_word(bot)),
    )


if __name__ == "__main__":
    asyncio.run(main())
