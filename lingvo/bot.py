"""Lingvo bot: word of the day with etymology and quizzes. Premium is paid in Telegram Stars."""
import asyncio
import functools
import json
import random
from datetime import date
from pathlib import Path

from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.types import BufferedInputFile, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from common.config import lang_of
from common.db import Store
from common.stars import payments_router, send_invoice
from .card import render

WORDS = json.loads((Path(__file__).parent / "words.json").read_text(encoding="utf-8"))
FREE_QUIZZES = 3
PRODUCTS = {"premium_30": 99}  # payload -> Stars

store = Store("lingvo")
router = Router()

T = {
    "ru": {
        "start": "Привет! Я рассказываю, откуда берутся слова.\n\n/word слово дня\n/quiz викторина ({free} в день бесплатно)\n/premium безлимит и весь архив за {price} ⭐ на 30 дней",
        "limit": "Бесплатные викторины на сегодня закончились. Премиум даёт безлимит: /premium",
        "right": "✅ Верно!", "wrong": "❌ Нет. Правильно: {a}",
        "premium_title": "Премиум на 30 дней",
        "premium_desc": "Безлимитные викторины и весь архив слов",
        "paid": "Спасибо! Премиум активен 30 дней. /random открывает случайное слово из архива.",
        "need_premium": "Архив доступен в премиуме: /premium",
    },
    "en": {
        "start": "Hi! I tell the stories behind words.\n\n/word word of the day\n/quiz quiz ({free} free per day)\n/premium unlimited + full archive for {price} ⭐ / 30 days",
        "limit": "You've used today's free quizzes. Premium is unlimited: /premium",
        "right": "✅ Correct!", "wrong": "❌ No. Correct answer: {a}",
        "premium_title": "Premium, 30 days",
        "premium_desc": "Unlimited quizzes and the full word archive",
        "paid": "Thank you! Premium is active for 30 days. /random shows a random word from the archive.",
        "need_premium": "The archive is a premium feature: /premium",
    },
}


def pick(option: str, lang: str) -> str:
    parts = option.split(" / ")
    return parts[0] if lang == "ru" or len(parts) == 1 else parts[1]


def card(w: dict, lang: str) -> str:
    return f"<b>{w['word']}</b>\n\n{w[lang]}"


@functools.lru_cache(maxsize=64)
def _image(word: str, ru: str, en: str, origin: str, path: tuple) -> bytes:
    return render(word, ru, en, origin, path)


async def photo(w: dict) -> BufferedInputFile:
    """Picture card for a word, rendered off the event loop and cached."""
    fact = w.get("fact") or {"ru": w["ru"], "en": w["en"]}
    data = await asyncio.to_thread(_image, w["word"], fact["ru"], fact["en"], w.get("origin", ""), tuple(w.get("path", ())))
    return BufferedInputFile(data, filename=f"{w['word']}.jpg")


@router.message(CommandStart())
async def start(m: Message):
    if m.text and m.text.endswith(" quiz"):
        return await quiz(m)
    await m.answer(T[lang_of(m.from_user)]["start"].format(free=FREE_QUIZZES, price=PRODUCTS["premium_30"]))


@router.message(Command("word"))
async def word(m: Message):
    w = WORDS[date.today().toordinal() % len(WORDS)]
    lang = lang_of(m.from_user)
    await m.answer_photo(await photo(w), caption=card(w, lang)[:1000], parse_mode="HTML")


@router.message(Command("random"))
async def random_word(m: Message):
    lang = lang_of(m.from_user)
    if not store.is_premium(m.from_user.id):
        return await m.answer(T[lang]["need_premium"])
    w = random.choice(WORDS)
    await m.answer_photo(await photo(w), caption=card(w, lang)[:1000], parse_mode="HTML")


@router.message(Command("quiz"))
async def quiz(m: Message):
    lang = lang_of(m.from_user)
    if not store.take(m.from_user.id, FREE_QUIZZES):
        return await m.answer(T[lang]["limit"])
    n = random.randrange(len(WORDS))
    w = WORDS[n]
    options = [(w["a"], 1)] + [(o, 0) for o in w["w"]]
    random.shuffle(options)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=pick(o, lang), callback_data=f"q:{n}:{ok}")] for o, ok in options
    ])
    await m.answer(f"<b>{w['word']}</b>\n{w['q'][lang]}", reply_markup=kb, parse_mode="HTML")


@router.callback_query(F.data.startswith("q:"))
async def answer(c: CallbackQuery):
    _, n, ok = c.data.split(":")
    lang = lang_of(c.from_user)
    w = WORDS[int(n)]
    verdict = T[lang]["right"] if ok == "1" else T[lang]["wrong"].format(a=pick(w["a"], lang))
    await c.message.edit_text(f"{verdict}\n\n{card(w, lang)}", parse_mode="HTML")
    await c.answer()


@router.message(Command("premium"))
async def premium(m: Message):
    t = T[lang_of(m.from_user)]
    await send_invoice(m.bot, m.chat.id, t["premium_title"], t["premium_desc"], "premium_30", PRODUCTS["premium_30"])


def on_paid(uid: int, payload: str) -> str:
    store.add_premium(uid, 30)
    return T["ru"]["paid"] + "\n\n" + T["en"]["paid"]


router.include_router(payments_router(store, PRODUCTS, on_paid))
