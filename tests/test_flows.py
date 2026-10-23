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
        self.assertIn("Wordlore", c.log[0]["text"])
        self.assertEqual(c.last()["kind"], "photo")          # a new user sees today's word right away
        self.assertGreaterEqual(len(c.buttons()), 8)
        n = len(c.log)
        await c.say("/start")                               # a returning user just gets the menu
        self.assertEqual(len(c.log), n + 1)
        assert_buttons_routable(self, c)

    async def test_english_user_gets_english(self):
        c = chat(1002, "en")
        await c.say("/start")
        self.assertIn("stories behind words", c.log[0]["text"])
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
                                          "status", "promo", "name", "mine", "theirs", "verdict", "q", "days"}, (lg, key, field))


async def play_round(c, answers):
    """Plays a whole round, answering right/wrong as listed. Returns the questions asked."""
    msg = harness.Message(c.user, "", BOT)
    asked = []
    for n, ok in enumerate(answers):
        text = c.last()["text"]
        asked.append(text.split("\n")[2] if "\n" in text else text)
        data = correct_option(c) if ok else wrong_option(c)
        await c.press(data, on=msg)
        await c.press(f"n:{n + 1}" if n < len(answers) - 1 else "n:end", on=msg)


class Duels(unittest.IsolatedAsyncioTestCase):
    async def test_duel_full_cycle(self):
        a = chat(7001)
        a.user.first_name = "Аня"
        await a.say("/quiz")
        await play_round(a, [1, 1, 1, 0, 0])             # Anya scores 3
        BOT.sent.clear()
        await a.press("m:duel")
        link = next(x for x in a.last()["text"].split() if "start=duel_" in x)
        code = link.split("duel_")[1]
        self.assertEqual(store.get_duel(code)["score"], 3)
        await a.press("m:duel")                           # pressing again reuses the same challenge
        self.assertIn(code, a.last()["text"])
        assert_buttons_routable(self, a)
        # a friend opens the link: free round with the same questions, referral bonus goes to Anya
        b = chat(7002)
        b.user.first_name = "Боря"
        await b.say(f"/start duel_{code}")
        self.assertIn("Аня", b.log[-2]["text"] if len(b.log) > 1 else "")
        first_q = b.last()["text"]
        self.assertIn("1/5", first_q)
        self.assertEqual(store.credits(7001), INVITER_BONUS)
        self.assertEqual(store.free_left(7002, 1), 1)      # the duel did not spend his daily round
        qs_a = store.get_duel(code)["qs"]
        from lingvo.bot import ROUNDS
        self.assertEqual(ROUNDS[7002]["qs"], qs_a)
        BOT.sent.clear()
        await play_round(b, [1, 1, 1, 1, 0])               # Borya scores 4 and wins
        texts = " ".join(x.get("text", "") for x in b.log)
        self.assertIn("🏆", texts)
        self.assertEqual(store.free_left(7002, 1), 1)
        notice = [s for s in BOT.sent if s["chat_id"] == 7001]
        self.assertEqual(len(notice), 1)
        self.assertIn("Боря", notice[0]["text"])
        self.assertIn("4/5", notice[0]["text"])
        self.assertEqual(store.duel_plays(code), [("Боря", 4)])
        # he cannot replay the same duel, and Anya opening her own link just gets it back
        await b.say(f"/start duel_{code}")
        self.assertIn("уже играл", b.last()["text"])
        await a.say(f"/start duel_{code}")
        self.assertIn(code, a.last()["text"])

    async def test_duel_loss_and_draw_wording(self):
        a = chat(7010)
        await a.say("/quiz")
        await play_round(a, [1, 1, 1, 1, 1])
        await a.press("m:duel")
        code = next(x for x in a.last()["text"].split() if "start=duel_" in x).split("duel_")[1]
        b = chat(7011)
        await b.say(f"/start duel_{code}")
        await play_round(b, [0, 0, 0, 0, 0])
        self.assertTrue(any("😅" in x.get("text", "") for x in b.log))
        c2 = chat(7012)
        await c2.say(f"/start duel_{code}")
        await play_round(c2, [1, 1, 1, 1, 1])
        self.assertTrue(any("🤝" in x.get("text", "") for x in c2.log))

    async def test_unknown_duel_code(self):
        c = chat(7020)
        await c.say("/start duel_deadbeef")
        self.assertIn("не найден", c.last()["text"])
        await c.say("/start duel_x'; drop table users;--")
        self.assertIn("не найден", c.last()["text"])
        self.assertEqual(store.credits(7020), 0)

    async def test_duel_button_without_finished_round(self):
        c = chat(7030)
        await c.press("m:duel")
        self.assertIn("/quiz", c.last()["text"])


class Weekly(unittest.IsolatedAsyncioTestCase):
    async def test_weekly_summary_active_idle_blocked(self):
        import run
        from datetime import datetime as real_dt
        for uid in (9001, 9002, 9003):
            store.ensure_user(uid)
            store.set_sub(uid, True)
        store.add_answer(9001, True)
        store.add_answer(9001, False)
        store.finish_round(9001)
        store.streak_hit(9001)
        bot = Bot("x")
        bot.fail_for = {9003}

        class Sunday:
            @staticmethod
            def now(tz):
                return real_dt(2026, 10, 25, 18, 0, tzinfo=tz)  # a Sunday
        real, run.datetime = run.datetime, Sunday
        try:
            await run.weekly_summary(bot)
        finally:
            run.datetime = real
        by = {s["chat_id"]: s["text"] for s in bot.sent}
        self.assertIn("Ответов: 2", by[9001])
        self.assertIn("не заходил", by[9002])
        self.assertNotIn(9003, by)
        self.assertFalse(store.is_sub(9003))
        # the numbers are a delta: the next summary starts from zero
        bot2 = Bot("x")
        run.datetime = Sunday
        try:
            await run.weekly_summary(bot2)
        finally:
            run.datetime = real
        self.assertIn("не заходил", {s["chat_id"]: s["text"] for s in bot2.sent}[9001])
        # and nothing is sent on other days
        bot3 = Bot("x")
        await run.weekly_summary(bot3) if real.now(run.TZ).weekday() != 6 else None
        if real.now(run.TZ).weekday() != 6:
            self.assertEqual(bot3.sent, [])


class Search(unittest.IsolatedAsyncioTestCase):
    async def test_exact_word_returns_its_card(self):
        c = chat(9301)
        await c.say("Шахматы")
        self.assertEqual(c.last()["kind"], "photo")
        self.assertIn("шахматы", c.last()["caption"].lower())
        assert_buttons_routable(self, c)

    async def test_yo_and_case_and_punctuation_insensitive(self):
        from lingvo.bot import find_words, WORDS
        for i in (0, 5, 40):
            w = WORDS[i]["word"]
            self.assertIn(i, find_words(f"  {w.upper()}!! "))

    async def test_prefix_lists_choices_and_choice_opens_word(self):
        from lingvo.bot import WORDS, norm
        # find a 2-letter prefix shared by several words
        by = {}
        for i, w in enumerate(WORDS):
            by.setdefault(norm(w["word"])[:3], []).append(i)
        prefix = next(k for k, v in by.items() if len(v) >= 2 and len(k) == 3 and not any(norm(WORDS[j]["word"]) == k for j in v))
        c = chat(9302)
        await c.say(prefix)
        self.assertEqual(c.last()["kind"], "text")
        choices = [b for b in c.buttons() if b.callback_data.startswith("w:")]
        self.assertGreaterEqual(len(choices), 2)
        assert_buttons_routable(self, c)
        await c.press(choices[0].callback_data)
        self.assertEqual(c.last()["kind"], "photo")

    async def test_unknown_word_goes_to_wishes(self):
        c = chat(9303)
        await c.say("абракадабра")
        self.assertIn("пожеланий", c.last()["text"])
        d = chat(9304)
        await d.say("Абракадабра")
        self.assertEqual(store.top_wishes(1)[0], ("абракадабра", 2))

    async def test_commands_not_swallowed_by_search(self):
        c = chat(9305)
        await c.say("/paysupport help me")           # handled by the payments router
        self.assertIn("Проблема с оплатой", c.last()["text"])
        before = len(c.log)
        await c.say("/nosuchcommand")
        self.assertEqual(len(c.log), before)          # unknown commands: silence

    async def test_too_short_or_long_text_gets_hint(self):
        c = chat(9306)
        await c.say("a")
        self.assertIn("Напиши слово", c.last()["text"])
        await c.say("x" * 50)
        self.assertIn("Напиши слово", c.last()["text"])

    async def test_wishes_command_owner_only(self):
        import lingvo.bot as mod
        c = chat(9307)
        mod.env = lambda name, default="": {"OWNER_ID": "9307"}.get(name, default)
        await c.say("/wishes")
        self.assertIn("×", c.last()["text"])
        d = chat(9308)
        n = len(d.log)
        await d.say("/wishes")
        self.assertEqual(len(d.log), n)


class Gifts(unittest.IsolatedAsyncioTestCase):
    async def test_buy_gift_friend_redeems_giver_thanked(self):
        g = chat(9801)
        await g.say("/premium")
        self.assertIn("buy:gift_30", [b.callback_data for b in g.buttons()])
        BOT.sent.clear()
        await g.press("buy:gift_30", on=harness.Message(g.user, "", BOT))
        inv = [x for x in BOT.sent if x["kind"] == "invoice"][0]
        self.assertEqual((inv["payload"], inv["prices"][0].amount), ("gift_30", 99))
        ok, _ = await g.pay("gift_30", 99)
        self.assertTrue(ok)
        self.assertFalse(store.is_premium(9801))                 # the giver does not get it
        link = next(w for x in g.log if x.get("text") for w in x["text"].split() if "start=gift_" in w)
        code = link.split("gift_")[1]
        assert_buttons_routable(self, g)
        await g.say("/gifts")
        self.assertIn(code, g.last()["text"])
        await g.say(f"/start gift_{code}")                       # opening your own gift does nothing
        self.assertFalse(store.is_premium(9801))
        f = chat(9802)
        f.user.first_name = "Маша"
        BOT.sent.clear()
        await f.say(f"/start gift_{code}")
        self.assertTrue(store.is_premium(9802))
        self.assertIn("🎁", f.log[0]["text"])
        thanks = [x for x in BOT.sent if x["chat_id"] == 9801]
        self.assertTrue(thanks and "Маша" in thanks[0]["text"])
        h = chat(9803)
        await h.say(f"/start gift_{code}")                       # second use: refused
        self.assertFalse(store.is_premium(9803))
        self.assertIn("уже активирован", h.last()["text"])
        await g.say("/gifts")
        self.assertIn("нет", g.last()["text"])

    async def test_unknown_gift_code(self):
        c = chat(9804)
        await c.say("/start gift_nope")
        self.assertFalse(store.is_premium(9804))


class StreakReward(unittest.IsolatedAsyncioTestCase):
    async def test_seventh_day_gives_bonus_round_once(self):
        from datetime import timedelta
        from common.db import today
        c = chat(9501)
        # six earlier days in a row, last one yesterday
        for back in range(6, 0, -1):
            store.conn.execute("INSERT OR REPLACE INTO streaks VALUES (?, ?, ?, ?)",
                               (9501, (today() - timedelta(days=back)).isoformat(), 7 - back, 7 - back))
        store.conn.commit()
        await c.say("/quiz")
        await play_round(c, [1, 1, 1, 1, 1])
        self.assertEqual(store.streak(9501)[0], 7)
        self.assertTrue(any("🎁" in x.get("text", "") and "7" in x.get("text", "") for x in c.log))
        self.assertEqual(store.credits(9501), 1)
        await c.press("m:quiz")                                    # the bonus round is real and playable
        self.assertIn("1/5", c.last()["text"])

    async def test_no_bonus_on_ordinary_days(self):
        c = chat(9502)
        await c.say("/quiz")
        await play_round(c, [1, 1, 1, 1, 1])
        self.assertEqual(store.credits(9502), 0)


class Collections(unittest.IsolatedAsyncioTestCase):
    async def test_every_word_is_in_exactly_one_collection(self):
        from lingvo.bot import WORDS
        from lingvo.collections import all_keys, members
        seen = []
        for k in all_keys():
            seen += members(WORDS, k)
        self.assertEqual(sorted(seen), list(range(len(WORDS))))

    async def test_free_collection_opens_and_cycles_without_repeats(self):
        from lingvo.collections import FREE_COLLECTION
        c = chat(9401)
        await c.say("/collections")
        self.assertIn("🔒", " ".join(b.text for b in c.buttons()))
        assert_buttons_routable(self, c)
        shown = []
        for _ in range(6):
            await c.press(f"c:{FREE_COLLECTION}")
            self.assertEqual(c.last()["kind"], "photo")
            shown.append(c.last()["caption"])
        self.assertTrue(all(a != b for a, b in zip(shown, shown[1:])))     # never the same word twice in a row
        assert_buttons_routable(self, c)

    async def test_locked_collection_shows_upsell_then_unlocks_with_premium(self):
        c = chat(9402)
        await c.press("c:antique")
        self.assertIn("🔒", c.last()["text"])
        self.assertIn("m:premium", [b.callback_data for b in c.buttons()])
        store.add_premium(9402, 30)
        await c.press("c:antique")
        self.assertEqual(c.last()["kind"], "photo")

    async def test_collection_quiz_uses_only_words_of_that_collection(self):
        from lingvo.bot import ROUNDS, WORDS
        from lingvo.collections import FREE_COLLECTION, members
        c = chat(9405)
        await c.press(f"c:{FREE_COLLECTION}")
        self.assertIn(f"cq:{FREE_COLLECTION}", [b.callback_data for b in c.buttons()])
        assert_buttons_routable(self, c)
        await c.press(f"cq:{FREE_COLLECTION}")
        self.assertIn("1/5", c.last()["text"])
        self.assertTrue(set(ROUNDS[9405]["qs"]) <= set(members(WORDS, FREE_COLLECTION)))
        self.assertEqual(len(set(ROUNDS[9405]["qs"])), 5)
        # a free user used the daily round on it; a locked collection quiz does nothing for them
        d = chat(9406)
        before = len(d.log)
        await d.press("cq:antique")
        self.assertEqual(len(d.log), before)
        store.add_premium(9406, 30)
        await d.press("cq:antique")
        self.assertTrue(set(ROUNDS[9406]["qs"]) <= set(members(WORDS, "antique")))

    async def test_bad_collection_key_ignored(self):
        c = chat(9403)
        before = len(c.log)
        await c.press("c:nonsense")
        self.assertEqual(len(c.log), before)

    async def test_menu_has_collections_button(self):
        c = chat(9404)
        await c.say("/start")
        self.assertIn("m:coll", [b.callback_data for b in c.buttons()])
        await c.press("m:coll")
        self.assertIn("📚", c.last()["text"])


class Poll(unittest.IsolatedAsyncioTestCase):
    async def test_every_word_makes_a_valid_telegram_quiz_poll(self):
        import run
        from lingvo.bot import WORDS
        from lingvo.bot import pick
        for w in WORDS:                       # Telegram limits: question 300, option 100, explanation 200, 2-10 options
            self.assertLessEqual(len(w["q"]["ru"]), 300)
            opts = [pick(w["a"], "ru")] + [pick(o, "ru") for o in w["w"]]
            self.assertTrue(2 <= len(opts) <= 10 and all(1 <= len(o) <= 100 for o in opts), w["word"])
            self.assertEqual(len(set(opts)), len(opts), w["word"])
            self.assertLessEqual(len(((w.get("fact") or {}).get("ru") or opts[0])[:200]), 200)

    async def test_poll_posted_with_right_answer_marked(self):
        import run
        run.env = lambda name, default="": {"CHANNEL": "@c"}.get(name, default)
        bot = Bot("x")
        await run.post_poll(bot)
        poll = next(s for s in bot.sent if s["kind"] == "poll")
        self.assertEqual(poll["chat_id"], "@c")
        w = run.poll_word()
        self.assertNotEqual(w, run.word_of_day())
        right = run.pick(w["a"], "ru")
        self.assertEqual(poll["options"][poll["correct_option_id"]], right)
        self.assertEqual(poll["type"], "quiz")
        self.assertTrue(poll["is_anonymous"])         # channels only allow anonymous polls
        self.assertIn("start=quiz", poll["reply_markup"].inline_keyboard[0][0].url)

    async def test_no_channel_no_poll(self):
        import run
        run.env = lambda name, default="": ""
        bot = Bot("x")
        await run.post_poll(bot)
        self.assertEqual(bot.sent, [])


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


class Website(unittest.TestCase):
    def test_every_word_has_a_built_page(self):
        import pathlib
        docs = pathlib.Path(__file__).resolve().parent.parent / "docs" / "w"
        for url in wl.URLS:
            self.assertTrue((docs / url.rsplit("/", 1)[1]).exists(), url)
        self.assertEqual(len(set(wl.URLS)), len(wl.WORDS))
