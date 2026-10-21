"""Wordlore bot: word of the day with etymology, 5-question quiz rounds, streaks, ranks, referrals.
Premium (unlimited rounds, archive, unlimited saved words) is paid in Telegram Stars."""
import asyncio
import functools
import html
import re
import json
import random
import time
from datetime import datetime
from pathlib import Path

from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.types import BufferedInputFile, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from common.config import env, lang_of
from common.db import Store, today
from common.daily import TZ
from common.growth import parse_ref, ref_link, share_url, start_arg
from common.stars import payments_router, send_invoice
from .card import render, render_result
from .collections import FREE_COLLECTION, all_keys, members, title as coll_title
from .texts import (FREE_ROUNDS, FREE_SAVED, INVITEE_BONUS, INVITER_BONUS, PRODUCT_DAYS, PRODUCTS, QUESTIONS, T, rank_for)

WORDS = json.loads((Path(__file__).parent / "words.json").read_text(encoding="utf-8"))

store = Store("lingvo")
router = Router()
LAST: dict = {}     # user id -> their last finished round (to turn it into a challenge)
ROUNDS: dict = {}   # user id -> running quiz round (in memory: a restart just ends open rounds)


# ---------------------------------------------------------------------------------------------
# small helpers
# ---------------------------------------------------------------------------------------------
def lang(user) -> str:
    """Stored choice first, then the Telegram interface language."""
    return store.get_lang(user.id) or lang_of(user)


def tr(user, key: str, **kw) -> str:
    return T[lang(user)][key].format(**kw) if kw else T[lang(user)][key]


def word_of_day() -> dict:
    return WORDS[today().toordinal() % len(WORDS)]


def word_index(word: dict) -> int:
    return WORDS.index(word)


def esc(text: str) -> str:
    return html.escape(text, quote=False)


def card(w: dict, lg: str) -> str:
    return f"<b>{esc(w['word'])}</b>\n\n{esc(w[lg])}"


def pick(option: str, lg: str) -> str:
    parts = option.split(" / ")
    return parts[0] if lg == "ru" or len(parts) == 1 else parts[1]


def button(text: str, data: str = "", url: str = "") -> InlineKeyboardButton:
    return InlineKeyboardButton(text=text, url=url) if url else InlineKeyboardButton(text=text, callback_data=data)


def keyboard(*rows) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[list(r) for r in rows])


def menu(user) -> InlineKeyboardMarkup:
    t = T[lang(user)]
    sub = t["btn_sub_off"] if store.is_sub(user.id) else t["btn_sub_on"]
    return keyboard(
        [button(t["btn_quiz"], "m:quiz"), button(t["btn_word"], "m:word")],
        [button(t["btn_me"], "m:me"), button(t["btn_saved"], "m:saved")],
        [button(t["btn_coll"], "m:coll"), button(t["btn_invite"], "m:invite")],
        [button(t["btn_premium"], "m:premium"), button(sub, "m:sub")],
        [button(t["btn_lang"], "m:lang")],
    )


@functools.lru_cache(maxsize=64)
def _image(word: str, ru: str, en: str, origin: str, path: tuple) -> bytes:
    return render(word, ru, en, origin, path)


async def word_photo(w: dict) -> BufferedInputFile:
    """Picture card for a word, rendered off the event loop and cached."""
    fact = w.get("fact") or {"ru": w["ru"], "en": w["en"]}
    data = await asyncio.to_thread(_image, w["word"], fact["ru"], fact["en"], w.get("origin", ""), tuple(w.get("path", ())))
    return BufferedInputFile(data, filename=f"{w['word']}.jpg")


async def bot_username(bot) -> str:
    return (await bot.me()).username


def word_keyboard(user, w: dict, link: str, coll: str = "") -> InlineKeyboardMarkup:
    t = T[lang(user)]
    text = t["share_word"].format(word=w["word"])
    rows = [
        [button(t["btn_save"], f"sv:{word_index(w)}"), button(t["btn_share"], url=share_url(link, text))],
        [button(t["btn_quiz"], "m:quiz")],
    ]
    if coll:
        rows.insert(1, [button(t["btn_more_coll"], f"c:{coll}"), button(t["btn_all_coll"], "m:coll")])
    return keyboard(*rows)


async def send_word(m: Message, user, w: dict, coll: str = "") -> None:
    lg = lang(user)
    link = ref_link(await bot_username(m.bot), user.id)
    await m.answer_photo(await word_photo(w), caption=card(w, lg)[:1000], parse_mode="HTML",
                         reply_markup=word_keyboard(user, w, link, coll))


# ---------------------------------------------------------------------------------------------
# start, menu, profile
# ---------------------------------------------------------------------------------------------
@router.message(CommandStart())
async def start(m: Message):
    user = m.from_user
    created = store.ensure_user(user.id)
    if not store.get_lang(user.id):
        store.set_lang(user.id, lang_of(user))  # remember it, so notifications can be localized later
    arg = start_arg(m.text)
    duel_code = arg[5:] if arg.startswith("duel_") else None
    inviter = parse_ref(arg)
    if duel_code and store.get_duel(duel_code):
        inviter = store.get_duel(duel_code)["creator"]  # whoever sent the challenge also gets the invite bonus
    if created and inviter and store.add_referral(user.id, inviter):
        store.add_credits(inviter, INVITER_BONUS)
        store.add_credits(user.id, INVITEE_BONUS)
        await m.answer(tr(user, "invite_welcome", c=INVITEE_BONUS))
        try:
            await m.bot.send_message(inviter, T[store.get_lang(inviter) or "ru"]["invite_notice"].format(b=INVITER_BONUS))
        except Exception:
            pass  # the inviter may have blocked the bot
    if duel_code is not None:
        return await start_duel(m, user, duel_code)
    if arg == "quiz":
        return await start_round(m, user)
    if arg == "sub":
        store.set_sub(user.id, True)
        return await m.answer(tr(user, "sub_on"), reply_markup=menu(user))
    await m.answer(tr(user, "welcome"), parse_mode="HTML", reply_markup=menu(user))


@router.message(Command("help"))
async def help_cmd(m: Message):
    await m.answer(tr(m.from_user, "welcome"), parse_mode="HTML", reply_markup=menu(m.from_user))


@router.message(Command("lang"))
async def lang_cmd(m: Message):
    await toggle_lang(m, m.from_user)


async def toggle_lang(m: Message, user) -> None:
    store.set_lang(user.id, "en" if lang(user) == "ru" else "ru")
    await m.answer(tr(user, "lang_set"), reply_markup=menu(user))


def profile_text(user) -> str:
    uid = user.id
    st = store.user_stats(uid)
    streak, best = store.streak(uid)
    rank_ru, rank_en, _, _ = rank_for(st["correct"])
    prem = (tr(user, "prem_on", date=datetime.fromtimestamp(store.premium_until(uid), TZ).strftime("%d.%m.%Y"))
            if store.is_premium(uid) else tr(user, "prem_off"))
    return tr(user, "me", rank=rank_ru if lang(user) == "ru" else rank_en, correct=st["correct"], answered=st["answered"],
              rounds=st["rounds"], streak=streak, best=best, saved=store.count_saved(uid), refs=store.referrals(uid), prem=prem)


@router.message(Command("me"))
async def me_cmd(m: Message):
    await m.answer(profile_text(m.from_user), parse_mode="HTML", reply_markup=menu(m.from_user))


# ---------------------------------------------------------------------------------------------
# word of the day, archive, saved words
# ---------------------------------------------------------------------------------------------
@router.message(Command("word"))
async def word_cmd(m: Message):
    await send_word(m, m.from_user, word_of_day())


COLL_LAST: dict = {}   # (user id, collection) -> index of the word shown last, to avoid showing it twice in a row


def can_open(user, key: str) -> bool:
    return key == FREE_COLLECTION or store.is_premium(user.id)


@router.message(Command("collections"))
async def collections_cmd(m: Message):
    await show_collections(m, m.from_user)


async def show_collections(m: Message, user) -> None:
    lg = lang(user)
    free = coll_title(FREE_COLLECTION, lg)
    rows = []
    for key in all_keys():
        n = len(members(WORDS, key))
        if n:
            lock = "" if can_open(user, key) else "🔒 "
            rows.append([button(f"{lock}{coll_title(key, lg)} · {n}", f"c:{key}")])
    await m.answer(T[lg]["coll_title"].format(free=free), parse_mode="HTML", reply_markup=keyboard(*rows))


@router.callback_query(F.data.startswith("c:"))
async def open_collection(c: CallbackQuery):
    user, key = c.from_user, c.data[2:]
    ids = members(WORDS, key) if key in all_keys() else []
    if not ids:
        return await c.answer()
    store.ensure_user(user.id)
    if not can_open(user, key):
        t = T[lang(user)]
        await c.message.answer(t["coll_locked"].format(free=coll_title(FREE_COLLECTION, lang(user))), reply_markup=keyboard(
            [button(coll_title(FREE_COLLECTION, lang(user)), f"c:{FREE_COLLECTION}")], [button(t["btn_premium"], "m:premium")]))
        return await c.answer()
    last = COLL_LAST.get((user.id, key))
    choices = [i for i in ids if i != last] or ids
    pick_i = random.choice(choices)
    COLL_LAST[(user.id, key)] = pick_i
    await send_word(c.message, user, WORDS[pick_i], coll=key)
    await c.answer()


@router.message(Command("random"))
async def random_cmd(m: Message):
    user = m.from_user
    if not store.is_premium(user.id):
        return await m.answer(tr(user, "need_premium", n=len(WORDS)), reply_markup=keyboard([button(T[lang(user)]["btn_premium"], "m:premium")]))
    await send_word(m, user, random.choice(WORDS))


@router.callback_query(F.data.startswith("sv:"))
async def save_word(c: CallbackQuery):
    user, idx = c.from_user, int(c.data[3:])
    if not 0 <= idx < len(WORDS):
        return await c.answer()
    if store.has_saved(user.id, str(idx)):
        return await c.answer(tr(user, "saved_already"))
    if not store.is_premium(user.id) and store.count_saved(user.id) >= FREE_SAVED:
        await c.message.answer(tr(user, "saved_full", n=FREE_SAVED), reply_markup=keyboard([button(T[lang(user)]["btn_premium"], "m:premium")]))
        return await c.answer()
    store.save_item(user.id, str(idx), WORDS[idx]["word"])
    await c.answer(tr(user, "saved_ok"))


@router.message(Command("saved"))
async def saved_cmd(m: Message):
    await show_saved(m, m.from_user)


async def show_saved(m: Message, user) -> None:
    lg, rows = lang(user), store.list_saved(user.id, 40)
    limit = "" if store.is_premium(user.id) else f"/{FREE_SAVED}"
    if not rows:
        return await m.answer(tr(user, "saved_empty"))
    lines = []
    for key, _ in rows:
        w = WORDS[int(key)]
        fact = (w.get("fact") or {}).get(lg) or ""
        lines.append(f"• <b>{esc(w['word'])}</b> — {esc(fact)}")
    await m.answer(tr(user, "saved_title", n=len(rows), limit=limit) + "\n\n" + "\n".join(lines), parse_mode="HTML")


# ---------------------------------------------------------------------------------------------
# quiz rounds
# ---------------------------------------------------------------------------------------------
async def paywall(m: Message, user) -> None:
    t = T[lang(user)]
    await m.answer(t["limit"].format(b=INVITER_BONUS, c=INVITEE_BONUS), parse_mode="HTML",
                   reply_markup=keyboard([button(t["btn_premium"], "m:premium")], [button(t["btn_invite"], "m:invite")]))


async def start_round(m: Message, user) -> None:
    open_round = ROUNDS.get(user.id)
    if open_round and not open_round["answered"] and time.time() - open_round["t"] < 3600:
        text, markup = question(user)  # resume the unfinished round instead of spending another attempt
        return await m.answer(text, parse_mode="HTML", reply_markup=markup)
    if not store.take(user.id, FREE_ROUNDS):
        return await paywall(m, user)
    now = time.time()
    for uid in [u for u, r in ROUNDS.items() if now - r["t"] > 3600]:
        del ROUNDS[uid]
    ROUNDS[user.id] = {"qs": random.sample(range(len(WORDS)), QUESTIONS), "i": 0, "score": 0, "answered": False, "t": now}
    text, markup = question(user)
    await m.answer(text, parse_mode="HTML", reply_markup=markup)


def display_name(user, lg: str) -> str:
    return esc(getattr(user, "first_name", None) or T[lg]["friend"])


async def start_duel(m: Message, user, code: str) -> None:
    d = store.get_duel(code)
    if d is None:
        return await m.answer(tr(user, "duel_gone"), reply_markup=menu(user))
    if d["creator"] == user.id:
        link = f"https://t.me/{await bot_username(m.bot)}?start=duel_{code}"
        return await m.answer(tr(user, "duel_own", link=link), disable_web_page_preview=True)
    if store.duel_played(code, user.id):
        return await m.answer(tr(user, "duel_done"), reply_markup=menu(user))
    lg = lang(user)
    await m.answer(tr(user, "duel_intro", name=esc(d["name"]), total=QUESTIONS), parse_mode="HTML")
    ROUNDS[user.id] = {"qs": d["qs"], "i": 0, "score": 0, "answered": False, "t": time.time(), "duel": code}
    text, markup = question(user)
    await m.answer(text, parse_mode="HTML", reply_markup=markup)


def question(user):
    r, lg = ROUNDS[user.id], lang(user)
    w = WORDS[r["qs"][r["i"]]]
    options = [(w["a"], 1)] + [(o, 0) for o in w["w"]]
    random.shuffle(options)
    text = f"<i>{T[lg]['q_header'].format(n=r['i'] + 1, total=QUESTIONS)}</i>\n\n<b>{esc(w['word'])}</b>\n{esc(w['q'][lg])}"
    rows = [[button(pick(o, lg), f"a:{r['i']}:{ok}")] for o, ok in options]
    return text, InlineKeyboardMarkup(inline_keyboard=rows)


@router.message(Command("quiz"))
async def quiz_cmd(m: Message):
    store.ensure_user(m.from_user.id)
    await start_round(m, m.from_user)


@router.callback_query(F.data.startswith("a:"))
async def answer(c: CallbackQuery):
    user = c.from_user
    _, i, ok = c.data.split(":")
    r = ROUNDS.get(user.id)
    if r is None or r["i"] != int(i):
        await c.message.answer(tr(user, "round_gone"))
        return await c.answer()
    if r["answered"]:
        return await c.answer()
    r["answered"] = True
    lg, w, right = lang(user), WORDS[r["qs"][r["i"]]], ok == "1"
    r["score"] += 1 if right else 0
    store.add_answer(user.id, right)
    verdict = T[lg]["right"] if right else T[lg]["wrong"].format(a=pick(w["a"], lg))
    last = r["i"] == QUESTIONS - 1
    t = T[lg]
    nxt = button(t["btn_finish"], "n:end") if last else button(t["btn_next"].format(n=r["i"] + 2, total=QUESTIONS), f"n:{r['i'] + 1}")
    await c.message.edit_text(f"{verdict}\n\n{card(w, lg)}", parse_mode="HTML",
                              reply_markup=keyboard([nxt], [button(t["btn_save"], f"sv:{r['qs'][r['i']]}")]))
    await c.answer()


@router.callback_query(F.data.startswith("n:"))
async def next_step(c: CallbackQuery):
    user, step = c.from_user, c.data[2:]
    r = ROUNDS.get(user.id)
    if r is None:
        await c.message.answer(tr(user, "round_gone"))
        return await c.answer()
    if step == "end":
        if not r["answered"] or r["i"] != QUESTIONS - 1:
            return await c.answer()
        await finish_round(c, user, r)
    elif int(step) == r["i"] + 1 and r["answered"]:
        r["i"] += 1
        r["answered"] = False
        text, markup = question(user)
        await c.message.edit_text(text, parse_mode="HTML", reply_markup=markup)
    await c.answer()


async def finish_round(c: CallbackQuery, user, r: dict) -> None:
    lg, t = lang(user), T[lang(user)]
    del ROUNDS[user.id]
    store.finish_round(user.id)
    streak, best, _ = store.streak_hit(user.id, grace=1 if store.is_premium(user.id) else 0)
    correct = store.user_stats(user.id)["correct"]
    rank_ru, rank_en, progress, next_ru = rank_for(correct)
    rank = rank_ru if lg == "ru" else rank_en
    image = await asyncio.to_thread(render_result, r["score"], QUESTIONS, rank_ru, rank_en, streak, progress, next_ru)
    caption = t["result_caption"].format(score=r["score"], total=QUESTIONS, rank=rank, correct=correct,
                                         streak=t["streak_line"].format(n=streak, best=best) if streak > 1 else t["streak_none"])
    link = ref_link(await bot_username(c.bot), user.id)
    share_text = t["share_result"].format(score=r["score"], total=QUESTIONS, rank=rank)
    rows = [[button(t["btn_again"], "m:quiz"), button(t["btn_share"], url=share_url(link, share_text))],
            [button(t["btn_duel"], "m:duel")]]
    LAST[user.id] = {"qs": r["qs"], "score": r["score"], "code": r.get("duel")}
    if not store.is_premium(user.id):
        rows.append([button(t["btn_premium"], "m:premium")])
    await c.message.answer_photo(BufferedInputFile(image, filename="result.jpg"), caption=caption, parse_mode="HTML",
                                 reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))
    if r.get("duel"):
        await settle_duel(c, user, r)


async def settle_duel(c: CallbackQuery, user, r: dict) -> None:
    """Compares a challenged player with the challenger and tells both."""
    d = store.get_duel(r["duel"])
    if d is None or not store.duel_play(r["duel"], user.id, getattr(user, "first_name", None) or "", r["score"]):
        return
    mine, theirs, lg = r["score"], d["score"], lang(user)
    key = "duel_win" if mine > theirs else "duel_draw" if mine == theirs else "duel_lose"
    await c.message.answer(tr(user, key, mine=mine, theirs=theirs, total=QUESTIONS, name=esc(d["name"])), parse_mode="HTML")
    clg = store.get_lang(d["creator"]) or "ru"
    verdict = T[clg]["verdict_win" if theirs > mine else "verdict_draw" if mine == theirs else "verdict_lose"]
    try:
        await c.bot.send_message(d["creator"], T[clg]["duel_notice"].format(
            name=display_name(user, clg), mine=theirs, theirs=mine, total=QUESTIONS, verdict=verdict), parse_mode="HTML")
    except Exception:
        pass  # the challenger may have blocked the bot


async def make_duel(c: CallbackQuery, user) -> None:
    last = LAST.get(user.id)
    if not last:
        return await c.message.answer(tr(user, "round_gone"))
    if last.get("made") is None:
        name = getattr(user, "first_name", None) or ""
        last["made"] = store.create_duel(user.id, name or T[lang(user)]["friend"], last["qs"], last["score"])
    t = T[lang(user)]
    link = f"https://t.me/{await bot_username(c.bot)}?start=duel_{last['made']}"
    await c.message.answer(tr(user, "duel_made", score=last["score"], total=QUESTIONS, link=link), parse_mode="HTML",
                           disable_web_page_preview=True,
                           reply_markup=keyboard([button(t["btn_share"], url=share_url(link, t["duel_share"].format(score=last["score"], total=QUESTIONS)))]))


# ---------------------------------------------------------------------------------------------
# invite, daily DM, premium
# ---------------------------------------------------------------------------------------------
@router.message(Command("invite"))
async def invite_cmd(m: Message):
    await show_invite(m, m.from_user)


async def show_invite(m: Message, user) -> None:
    t = T[lang(user)]
    link = ref_link(await bot_username(m.bot), user.id)
    await m.answer(tr(user, "invite", b=INVITER_BONUS, c=INVITEE_BONUS, link=link, n=store.referrals(user.id)),
                   parse_mode="HTML", disable_web_page_preview=True,
                   reply_markup=keyboard([button(t["btn_share"], url=share_url(link, t["share_word"].format(word="Wordlore")))]))


@router.message(Command("sub"))
async def sub_cmd(m: Message):
    await toggle_sub(m, m.from_user)


async def toggle_sub(m: Message, user) -> None:
    on = not store.is_sub(user.id)
    store.set_sub(user.id, on)
    await m.answer(tr(user, "sub_on" if on else "sub_off"), reply_markup=menu(user))


@router.message(Command("premium"))
async def premium_cmd(m: Message):
    await show_premium(m, m.from_user)


async def show_premium(m: Message, user) -> None:
    t = T[lang(user)]
    uid = user.id
    status = (tr(user, "prem_on", date=datetime.fromtimestamp(store.premium_until(uid), TZ).strftime("%d.%m.%Y"))
              if store.is_premium(uid) else "")
    off = round(100 - 100 * PRODUCTS["premium_365"] / (12 * PRODUCTS["premium_30"]))
    await m.answer(tr(user, "premium", n=len(WORDS), status=status), parse_mode="HTML", reply_markup=keyboard(
        [button(t["buy_30"].format(p=PRODUCTS["premium_30"]), "buy:premium_30")],
        [button(t["buy_365"].format(p=PRODUCTS["premium_365"], off=off), "buy:premium_365")]))


@router.callback_query(F.data.startswith("buy:"))
async def buy(c: CallbackQuery):
    user, key = c.from_user, c.data[4:]
    if key not in PRODUCTS:
        return await c.answer()
    t = T[lang(user)]
    kind = key.split("_")[1]
    await send_invoice(c.bot, c.message.chat.id, t[f"inv_title_{kind}"], t["inv_desc"], key, PRODUCTS[key])
    await c.answer()


def on_paid(uid: int, payload: str) -> str:
    store.add_premium(uid, PRODUCT_DAYS.get(payload, 30))
    date = datetime.fromtimestamp(store.premium_until(uid), TZ).strftime("%d.%m.%Y")
    return T["ru"]["paid"].format(date=date) + "\n\n" + T["en"]["paid"].format(date=date)


# ---------------------------------------------------------------------------------------------
# menu buttons (inline) route to the same screens as the commands
# ---------------------------------------------------------------------------------------------
@router.callback_query(F.data.startswith("m:"))
async def menu_button(c: CallbackQuery):
    user, action, m = c.from_user, c.data[2:], c.message
    store.ensure_user(user.id)
    if action == "quiz":
        await start_round(m, user)
    elif action == "word":
        await send_word(m, user, word_of_day())
    elif action == "me":
        await m.answer(profile_text(user), parse_mode="HTML", reply_markup=menu(user))
    elif action == "saved":
        await show_saved(m, user)
    elif action == "invite":
        await show_invite(m, user)
    elif action == "coll":
        await show_collections(m, user)
    elif action == "premium":
        await show_premium(m, user)
    elif action == "duel":
        await make_duel(c, user)
    elif action == "sub":
        await toggle_sub(m, user)
    elif action == "lang":
        await toggle_lang(m, user)
    await c.answer()


router.include_router(payments_router(store, PRODUCTS, on_paid))

# Free-text search lives in its own router that is included AFTER the payments router, so commands
# like /paysupport and /stats (which are handled there) are never swallowed by a catch-all text handler.
search = Router()


def norm(s: str) -> str:
    return re.sub(r"[^\w]+", " ", s.lower().replace("ё", "е")).strip()


def find_words(query: str, limit: int = 6) -> list:
    q = norm(query)
    if len(q) < 2:
        return []
    keyed = [(i, norm(w["word"])) for i, w in enumerate(WORDS)]
    for hit in (lambda k: k == q, lambda k: k.startswith(q), lambda k: q in k):
        found = [i for i, k in keyed if hit(k)]
        if found:
            return found[:limit]
    return []


@search.message(F.text)
async def search_word(m: Message):
    user, text = m.from_user, (m.text or "").strip()
    if text.startswith("/"):
        return  # an unknown command: stay quiet
    store.ensure_user(user.id)
    if not 2 <= len(text) <= 40:
        return await m.answer(tr(user, "search_hint"))
    found = find_words(text)
    if not found:
        store.add_wish(user.id, norm(text))
        return await m.answer(tr(user, "search_none", q=esc(text[:40])), parse_mode="HTML", reply_markup=menu(user))
    if len(found) == 1:
        return await send_word(m, user, WORDS[found[0]])
    await m.answer(tr(user, "search_pick"), reply_markup=keyboard(*[[button(WORDS[i]["word"], f"w:{i}")] for i in found]))


@search.callback_query(F.data.startswith("w:"))
async def open_word(c: CallbackQuery):
    try:
        w = WORDS[int(c.data[2:])]
    except (ValueError, IndexError):
        return await c.answer()
    await send_word(c.message, c.from_user, w)
    await c.answer()


@router.message(Command("wishes"))
async def wishes_cmd(m: Message):
    if str(m.from_user.id) != env("OWNER_ID"):
        return
    rows = store.top_wishes()
    await m.answer("\n".join(f"{n}× {w}" for w, n in rows) or "—")


@search.callback_query()
async def stale_button(c: CallbackQuery):
    """Buttons from older versions of the bot (or expired rounds)."""
    await c.answer(tr(c.from_user, "stale"), show_alert=True)


router.include_router(search)
