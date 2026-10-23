"""Runs the Wordlore bot; every morning posts the word of the day to CHANNEL and to DM subscribers."""
import asyncio
import logging
import random

from aiogram import Bot, Dispatcher
from aiogram.types import BufferedInputFile, InlineKeyboardButton, InlineKeyboardMarkup

from common.config import env
from datetime import datetime

from common.daily import TZ, every_day
from common.profile import setup_profile
from common.growth import broadcast, promo, ref_link, share_url
from lingvo.bot import URLS, WORDS, esc, pick, router, store, word_index, word_of_day, word_photo
from common.db import today
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
            [InlineKeyboardButton(text="📖 Подробнее на сайте / Read more", url=URLS[word_index(w)])],
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
            [InlineKeyboardButton(text=t["btn_share"], url=share_url(link, t["share_word"].format(word=w["word"]))),
             InlineKeyboardButton(text=t["btn_more"], url=URLS[word_index(w)])],
        ])
        await bot.send_photo(uid, photo, caption=f"<b>{esc(w['word'])}</b>\n\n{esc(w[lg])}"[:1000], parse_mode="HTML", reply_markup=kb)

    dead = await broadcast(store.subs(), send_dm)
    for uid in dead:  # people who blocked the bot are unsubscribed
        store.set_sub(uid, False)
    logging.info("daily DM: %s subscribers, %s dropped", len(store.subs()) + len(dead), len(dead))


def poll_word() -> dict:
    """A different word from the word of the day, stable for the whole day."""
    idx = (today().toordinal() * 7 + 3) % len(WORDS)
    if WORDS[idx] is word_of_day():
        idx = (idx + 1) % len(WORDS)
    return WORDS[idx]


async def post_poll(bot: Bot) -> None:
    """Evening quiz poll in the channel: people answer with one tap, see the explanation and stay."""
    channel = env("CHANNEL")
    if not channel:
        return
    w = poll_word()
    me = await bot.get_me()
    options = [(pick(w["a"], "ru"), True)] + [(pick(o, "ru"), False) for o in w["w"]]
    random.shuffle(options)
    explanation = ((w.get("fact") or {}).get("ru") or pick(w["a"], "ru"))[:200]
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🧠 Ещё вопросы в боте", url=f"https://t.me/{me.username}?start=quiz")]])
    await bot.send_poll(channel, question=w["q"]["ru"][:300], options=[o for o, _ in options], type="quiz",
                        correct_option_id=[ok for _, ok in options].index(True), explanation=explanation,
                        is_anonymous=True, reply_markup=kb)


async def weekly_summary(bot: Bot) -> None:
    """Sundays: each daily-DM subscriber gets their week in numbers (or a gentle nudge if they were away)."""
    if datetime.now(TZ).weekday() != 6:
        return

    async def send_week(uid: int) -> None:
        lg = store.get_lang(uid) or "ru"
        t = T[lg]
        delta = store.week_delta(uid)
        kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=t["btn_quiz"], callback_data="m:quiz")]])
        if delta["answered"] == 0:
            await bot.send_message(uid, t["week_idle"], reply_markup=kb)
        else:
            streak = store.streak(uid)[0]
            await bot.send_message(uid, t["week_active"].format(streak=streak, **delta), parse_mode="HTML", reply_markup=kb)

    for uid in await broadcast(store.subs(), send_week):
        store.set_sub(uid, False)


async def main() -> None:
    logging.basicConfig(level=logging.INFO)
    bot = Bot(env("BOT_TOKEN"))
    dp = Dispatcher()
    dp.include_router(router)
    await setup_profile(bot, COMMANDS, DESCRIPTION, SHORT)
    await asyncio.gather(
        dp.start_polling(bot),
        every_day(env("POST_TIME", "10:00"), lambda: post_word(bot)),
        every_day("18:00", lambda: weekly_summary(bot)),
        every_day(env("POLL_TIME", "18:30"), lambda: post_poll(bot)),
    )


if __name__ == "__main__":
    asyncio.run(main())
