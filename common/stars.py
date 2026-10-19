"""Telegram Stars payments shared by both bots."""
from typing import Callable

from aiogram import Bot, F, Router
from aiogram.filters import Command
from aiogram.types import LabeledPrice, Message, PreCheckoutQuery

from .config import env, lang_of
from .db import Store


async def send_invoice(bot: Bot, chat_id: int, title: str, description: str, payload: str, stars: int):
    await bot.send_invoice(
        chat_id=chat_id,
        title=title,
        description=description,
        payload=payload,
        currency="XTR",
        prices=[LabeledPrice(label=title, amount=stars)],
    )


def payments_router(store: Store, products: dict, on_paid: Callable[[int, str], str]) -> Router:
    """products: payload -> stars. on_paid(user_id, payload) grants the item and returns a reply."""
    router = Router()

    @router.pre_checkout_query()
    async def pre_checkout(query: PreCheckoutQuery):
        ok = products.get(query.invoice_payload) == query.total_amount
        await query.answer(ok=ok, error_message=None if ok else "Product changed, try again")

    @router.message(F.successful_payment)
    async def paid(message: Message):
        p = message.successful_payment
        if store.record_payment(p.telegram_payment_charge_id, message.from_user.id, p.total_amount, p.invoice_payload):
            await message.answer(on_paid(message.from_user.id, p.invoice_payload))

    @router.message(Command("paysupport"))
    async def paysupport(message: Message):
        if lang_of(message.from_user) == "ru":
            text = "Проблема с оплатой? Опиши её одним сообщением, начав с /paysupport, и мы ответим."
        else:
            text = "Payment problem? Describe it in one message starting with /paysupport and we will reply."
        await message.answer(text)
        owner = env("OWNER_ID")
        if owner and message.text and len(message.text) > len("/paysupport"):
            await message.bot.send_message(int(owner), f"paysupport from {message.from_user.id}: {message.text}")

    @router.message(Command("stats"))
    async def stats(message: Message):
        if str(message.from_user.id) == env("OWNER_ID"):
            await message.answer(store.stats())

    return router
