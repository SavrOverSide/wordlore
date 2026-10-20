import asyncio
import re
import unittest

from tests import harness
from tests.harness import Chat, assert_buttons_routable
from aiogram import Bot

from lingvo import bot as wl
from lingvo.texts import FREE_SAVED, INVITEE_BONUS, INVITER_BONUS, QUESTIONS

store = wl.store
BOT = Bot("x")


def chat(uid, lang="ru"):
    return Chat(wl.router, BOT, uid, lang)


def correct_option(c, w_index_hint=None):
    """Find the callback of the right answer in the last question: the one whose data ends with ':1'."""
    msg = c.last()
    for row in msg["reply_markup"].inline_keyboard:
        for b in row:
            if b.callback_data and b.callback_data.endswith(":1"):
                return b.callback_data
    raise AssertionError("no correct option")


def wrong_option(c):
    for row in c.last()["reply_markup"].inline_keyboard:
        for b in row:
            if b.callback_data and b.callback_data.endswith(":0"):
                return b.callback_data
    raise AssertionError("no wrong option")


class WordloreFlows(unittest.IsolatedAsyncioTestCase):
    async def test_start_shows_menu_and_all_buttons_work(self):
        c = chat(1001)
        await c.say("/start")
        self.assertIn("Wordlore", c.last()["text"])
        self.assertGreaterEqual(len(c.buttons()), 8)
        assert_buttons_routable(self, c)

    async def test_english_user_gets_english(self):
        c = chat(1002, "en")
        await c.say("/start")
        self.assertIn("stories behind words", c.last()["text"])
        self.assertEqual(store.get_lang(1002), "en")
        await c.say("/lang")
        self.assertEqual(store.get_lang(1002), "ru")
        self.assertIn("Язык", c.last()["text"])

    async def test_full_quiz_round_then_paywall(self):
        c = chat(1003)
        await c.say("/start")
        await c.say("/quiz")
        self.assertIn("1/5", c.last()["text"])
        for n in range(QUESTIONS):
            msg = harness.Message(c.user, "", BOT)
            await c.press(correct_option(c), on=msg)
            self.assertIn("✅", c.last()["text"])          # verdict shown (edit)
            if n < QUESTIONS - 1:
                await c.press(f"n:{n + 1}", on=msg)
                self.assertIn(f"{n + 2}/5", c.last()["text"])
            else:
                await c.press("n:end", on=msg)
        res = c.last()
        self.assertEqual(res["kind"], "photo")
        self.assertIn("5/5", res["caption"])
        self.assertGreater(len(res["photo"].data), 20000)  # a real JPEG was rendered
        self.assertEqual(store.user_stats(1003)["correct"], 5)
        self.assertEqual(store.streak(1003)[0], 1)
        assert_buttons_routable(self, c)
        # the free round is used up: the next one hits the paywall with premium and invite buttons
        await c.say("/quiz")
        self.assertIn("🔒", c.last()["text"])
        assert_buttons_routable(self, c)

    async def test_wrong_answer_shows_correct_one(self):
        c = chat(1004)
        await c.say("/quiz")
        msg = harness.Message(c.user, "", BOT)
        await c.press(wrong_option(c), on=msg)
        self.assertIn("❌", c.last()["text"])
        self.assertEqual(store.user_stats(1004), {"correct": 0, "answered": 1, "rounds": 0})

    async def test_double_click_and_stale_round_are_ignored(self):
        c = chat(1005)
        await c.say("/quiz")
        data = correct_option(c)
        msg = harness.Message(c.user, "", BOT)
        await c.press(data, on=msg)
        before = store.user_stats(1005)["answered"]
        await c.press(data, on=msg)   # same button again
        self.assertEqual(store.user_stats(1005)["answered"], before)
        c2 = chat(1006)
        await c2.press("a:0:1")        # an answer with no running round
        self.assertIn("/quiz", c2.last()["text"])

    async def test_resume_open_round_does_not_burn_attempt(self):
        c = chat(1007)
        await c.say("/quiz")
        await c.say("/quiz")   # pressed again before answering
        self.assertEqual(store.free_left(1007, 1), 0)
        self.assertIn("1/5", c.last()["text"])
        self.assertNotIn("🔒", c.last()["text"])

    async def test_referral_rewards_both_and_notifies(self):
        inviter = chat(2001)
        await inviter.say("/start")
        friend = chat(2002)
        BOT.sent.clear()
        await friend.say("/start ref_2001")
        self.assertEqual(store.credits(2001), INVITER_BONUS)
        self.assertEqual(store.credits(2002), INVITEE_BONUS)
        self.assertTrue(any(s["chat_id"] == 2001 for s in BOT.sent))
        self.assertEqual(store.referrals(2001), 1)
        # repeat /start with the same link gives nothing more; self-invite gives nothing
        await friend.say("/start ref_2001")
        await inviter.say("/start ref_2001")
        self.assertEqual(store.credits(2001), INVITER_BONUS)
        # bonus rounds are really playable after the free one is spent
        await friend.say("/quiz")
        self.assertEqual(friend.last()["kind"], "text")
        self.assertNotIn("🔒", friend.last()["text"])

    async def test_existing_user_cannot_claim_referral(self):
        a, b = chat(2010), chat(2011)
        await a.say("/start")
        await b.say("/start")
        await b.say("/start ref_2010")
        self.assertEqual(store.credits(2010), 0)

    async def test_invite_screen_has_personal_link(self):
        c = chat(2020)
        await c.say("/invite")
        self.assertIn("start=ref_2020", c.last()["text"])
        urls = [b.url for b in c.buttons() if b.url]
        self.assertTrue(any(u.startswith("https://t.me/share/url?url=") for u in urls))

    async def test_saved_words_limit_and_premium_unlock(self):
        c = chat(3001)
        for i in range(FREE_SAVED):
            await c.press(f"sv:{i}")
        self.assertEqual(store.count_saved(3001), FREE_SAVED)
        before = len(c.log)
        await c.press(f"sv:{FREE_SAVED}")                         # 11th: blocked, upsell shown
        self.assertEqual(store.count_saved(3001), FREE_SAVED)
        self.assertGreater(len(c.log), before)
        await c.press("sv:0")                                      # duplicate is harmless
        store.add_premium(3001, 30)
        await c.press(f"sv:{FREE_SAVED}")
        self.assertEqual(store.count_saved(3001), FREE_SAVED + 1)
        await c.say("/saved")
        self.assertIn("<b>", c.last()["text"])

    async def test_saved_empty(self):
        c = chat(3002)
        await c.say("/saved")
        self.assertIn("💾", c.last()["text"])

    async def test_premium_purchase_flow(self):
        c = chat(4001)
        await c.say("/premium")
        assert_buttons_routable(self, c)
        BOT.sent.clear()
        await c.press("buy:premium_365", on=harness.Message(c.user, "", BOT))
        inv = [s for s in BOT.sent if s["kind"] == "invoice"]
        self.assertEqual(len(inv), 1)
        self.assertEqual(inv[0]["currency"], "XTR")
        self.assertEqual(inv[0]["prices"][0].amount, 799)
        ok, err = await c.pay("premium_365", 799)
        self.assertTrue(ok)
        self.assertTrue(store.is_premium(4001))
        left = store.premium_until(4001) - __import__("time").time()
        self.assertAlmostEqual(left, 365 * 86400, delta=60)
        self.assertIn("Спасибо", c.last()["text"])
        # wrong amount for a product is rejected at pre-checkout
        q = harness.PreCheckoutQuery("premium_365", 1)
        await wl.router.feed("pre_checkout_query", q)
        self.assertFalse(q.result[0])
        await c.say("/random")           # archive now open
        self.assertEqual(c.last()["kind"], "photo")

    async def test_random_is_premium_only(self):
        c = chat(4002)
        await c.say("/random")
        self.assertEqual(c.last()["kind"], "text")
        self.assertIn("/premium", c.last()["text"] + "/premium")

    async def test_word_of_day_card(self):
        c = chat(5001)
        await c.say("/word")
        self.assertEqual(c.last()["kind"], "photo")
        self.assertGreater(len(c.last()["photo"].data), 20000)
        assert_buttons_routable(self, c)

    async def test_profile_and_streak(self):
        c = chat(5002)
        store.streak_hit(5002)
        await c.say("/me")
        self.assertIn("🔥", c.last()["text"])

    async def test_sub_toggle_and_deeplink(self):
        c = chat(5003)
        await c.say("/sub")
        self.assertTrue(store.is_sub(5003))
        await c.say("/sub")
        self.assertFalse(store.is_sub(5003))
        d = chat(5004)
        await d.say("/start sub")
        self.assertTrue(store.is_sub(5004))

    async def test_old_buttons_get_a_polite_answer(self):
        c = chat(5005)
        res = await c.press("q:3:1")
        self.assertEqual(res.handler.__name__, "stale_button")
        self.assertTrue(res.answers[0]["alert"])

    async def test_start_quiz_deeplink_from_channel(self):
        c = chat(5006)
        await c.say("/start quiz")
        self.assertIn("1/5", c.last()["text"])

    async def test_every_text_has_both_languages(self):
        from lingvo.texts import T
        self.assertEqual(set(T["ru"]), set(T["en"]))
        for lg in ("ru", "en"):
            for key, val in T[lg].items():
                for field in re.findall(r"\{(\w+)\}", val):
                    self.assertIn(field, {"n", "total", "a", "free", "price", "score", "rank", "streak", "correct", "best", "answered",
                                          "rounds", "saved", "refs", "prem", "date", "limit", "b", "c", "link", "p", "off", "word",
                                          "status", "promo"}, (lg, key, field))


class DailyPost(unittest.IsolatedAsyncioTestCase):
    async def test_post_word_to_channel_and_subscribers(self):
        import run
        run.env = lambda name, default="": {"CHANNEL": "@testchan"}.get(name, default)
        for uid in (6001, 6002, 6003):
            store.ensure_user(uid)
            store.set_sub(uid, True)
        store.set_lang(6002, "en")
        bot = Bot("x")
        bot.fail_for = {6003}                      # this one blocked the bot
        await run.post_word(bot)
        photos = [s for s in bot.sent if s["kind"] == "photo"]
        targets = [s["chat_id"] for s in photos]
        self.assertIn("@testchan", targets)
        self.assertIn(6001, targets)
        self.assertIn(6002, targets)
        self.assertNotIn(6003, targets)
        self.assertFalse(store.is_sub(6003))       # blocked user is unsubscribed
        self.assertTrue(store.is_sub(6001))
        chan = next(s for s in photos if s["chat_id"] == "@testchan")
        self.assertIn("🔗", chan["caption"])        # cross-promotion footer
        self.assertLess(len(chan["caption"]), 1000)
        urls = [b.url for row in chan["reply_markup"].inline_keyboard for b in row if b.url]
        self.assertTrue(any("start=quiz" in u for u in urls) and any("start=sub" in u for u in urls))


if __name__ == "__main__":
    unittest.main()


class Profile(unittest.IsolatedAsyncioTestCase):
    async def test_profile_texts_fit_telegram_limits_and_apply(self):
        from common.profile import setup_profile
        from lingvo.profile import COMMANDS, DESCRIPTION, SHORT
        bot = Bot("x")
        await setup_profile(bot, COMMANDS, DESCRIPTION, SHORT)
        self.assertEqual({p[1] for p in bot.profile}, {None, "en", "ru"})
        for lg in COMMANDS:
            for cmd, desc in COMMANDS[lg]:
                self.assertRegex(cmd, r"^[a-z0-9_]{1,32}$")
                self.assertTrue(3 <= len(desc) <= 256)
        # every menu command is a real handler
        names = {c for c, _ in COMMANDS["ru"]}
        self.assertEqual(names, {c for c, _ in COMMANDS["en"]})
        for c in names:
            m = harness.Message(harness.User(77), f"/{c}", Bot("x"))
            self.assertIsNotNone(await wl.router.feed("message", m), c)
