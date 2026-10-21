"""Real-aiogram smoke run for Wordlore (see tests/real_aiogram.py)."""
import asyncio
import sys

sys.path.insert(0, "/app")
sys.path.insert(0, "/app/tests")

from real_aiogram import Harness  # noqa: E402
from lingvo import bot as wl  # noqa: E402


async def main():
    h = Harness(wl.router)
    calls = await h.say(10, "/start")
    h.expect(any(type(c).__name__ == "SendMessage" for c in calls), "/start replies")
    for data in [b for b in h.buttons(calls) if b and not b.startswith("http")]:
        await h.press(10, data)

    # a whole quiz round, answering right every time
    calls = await h.press(11, "m:quiz")
    for n in range(5):
        right = next(b for b in h.buttons(calls) if b.startswith("a:") and b.endswith(":1"))
        calls = await h.press(11, right)
        h.expect(any(type(c).__name__ == "EditMessageText" for c in calls), f"answer {n} edits the question")
        calls = await h.press(11, f"n:{n + 1}" if n < 4 else "n:end")
    h.expect(any(type(c).__name__ == "SendPhoto" for c in calls), "round ends with a result picture")

    # duel: challenge, a friend plays it, the challenger is notified
    calls = await h.press(11, "m:duel")
    link = next((c.text for c in calls if getattr(c, "text", None) and "duel_" in c.text), "")
    code = link.split("duel_")[1].split()[0] if "duel_" in link else ""
    h.expect(bool(code), "duel link created")
    calls = await h.say(12, f"/start duel_{code}", name="Друг")
    for n in range(5):
        pick = next(b for b in h.buttons(calls) if b.startswith("a:"))
        calls = await h.press(12, pick)
        calls = await h.press(12, f"n:{n + 1}" if n < 4 else "n:end")
    h.expect(any(getattr(c, "chat_id", None) == 11 for c in calls), "challenger gets the duel result")

    # paywall after the free round, then premium purchase
    wl.store.ensure_user(16)
    wl.store.take(16, 1)                       # today's free round is already used
    calls = await h.press(16, "m:quiz")
    h.expect("m:premium" in h.buttons(calls) and "m:invite" in h.buttons(calls), "paywall offers premium and invites")
    calls = await h.press(11, "buy:premium_30")
    h.expect(any(type(c).__name__ == "SendInvoice" for c in calls), "invoice sent")
    calls = await h.pre_checkout(11, "premium_30", 99)
    h.expect(any(type(c).__name__ == "AnswerPreCheckoutQuery" and c.ok for c in calls), "pre-checkout approved")
    calls = await h.pre_checkout(11, "premium_30", 1)
    h.expect(any(type(c).__name__ == "AnswerPreCheckoutQuery" and not c.ok for c in calls), "wrong price rejected")
    await h.paid(11, "premium_30", 99)
    h.expect(wl.store.is_premium(11), "premium granted")
    calls = await h.say(11, "/random")
    h.expect(any(type(c).__name__ == "SendPhoto" for c in calls), "/random works for premium")

    # gift: buy for a friend, the link arrives, the friend redeems it
    calls = await h.press(30, "buy:gift_30")
    h.expect("SendInvoice" in [type(c).__name__ for c in calls], "gift invoice")
    await h.pre_checkout(30, "gift_30", 99)
    calls = await h.paid(30, "gift_30", 99)
    link = next((c.text for c in calls if getattr(c, "text", None) and "gift_" in c.text), "")
    code = link.split("start=gift_")[1].split()[0] if "start=gift_" in link else ""
    h.expect(bool(code), "gift link sent after payment")
    calls = await h.say(31, f"/start gift_{code}")
    h.expect(wl.store.is_premium(31) and any(getattr(c, "chat_id", None) == 30 for c in calls), "gift redeemed, giver thanked")
    await h.say(30, "/gifts")

    # search, collections, other commands, support, stale buttons
    calls = await h.say(13, "шахматы")
    h.expect(any(type(c).__name__ == "SendPhoto" for c in calls), "search finds a word")
    await h.say(13, "абракадабра")
    calls = await h.say(13, "/collections")
    for data in h.buttons(calls):
        await h.press(13, data)
    await h.press(13, "cq:east")
    for cmd in ("/word", "/me", "/saved", "/invite", "/sub", "/premium", "/lang", "/help", "/paysupport test"):
        calls = await h.say(14, cmd)
        h.expect(bool(calls), f"{cmd} replies")
    calls = await h.press(14, "old:button")
    h.expect(any(type(c).__name__ == "AnswerCallbackQuery" and c.show_alert for c in calls), "stale button explained")
    calls = await h.say(14, "/nosuchcommand")
    h.expect(not calls, "unknown command stays silent")
    h.report()


asyncio.run(main())
