"""All user-facing strings of the Wordlore bot (ru/en) and the rank ladder."""

FREE_ROUNDS = 1        # free quiz rounds per day (5 questions each)
QUESTIONS = 5
FREE_SAVED = 10        # saved words for free users
INVITER_BONUS = 2      # extra rounds for whoever invites a friend
INVITEE_BONUS = 1      # extra round for the friend
PRODUCTS = {"premium_30": 99, "premium_365": 799}   # payload -> Stars
PRODUCT_DAYS = {"premium_30": 30, "premium_365": 365}

# (minimum correct answers, ru title, en title)
RANKS = [
    (0, "Любопытный", "Curious"),
    (10, "Знаток корней", "Root Reader"),
    (30, "Этимолог", "Etymologist"),
    (80, "Лингвист-детектив", "Linguist Detective"),
    (200, "Хранитель слов", "Keeper of Words"),
]


def rank_for(correct: int) -> tuple:
    """(ru title, en title, progress 0..1 to the next rank, next rank ru title or '')."""
    idx = max(i for i, (need, _, _) in enumerate(RANKS) if correct >= need)
    _, ru, en = RANKS[idx]
    if idx == len(RANKS) - 1:
        return ru, en, 1.0, ""
    lo, hi = RANKS[idx][0], RANKS[idx + 1][0]
    return ru, en, (correct - lo) / (hi - lo), RANKS[idx + 1][1]


T = {
    "ru": {
        "welcome": ("<b>Wordlore</b> — истории слов.\n\nОткуда взялись «шахматы», что общего у «спасибо» с Богом и почему "
                    "robot — это «подневольный труд»? Каждый день новое слово с цепочкой происхождения, "
                    "а ещё викторины, серии и ранги.\n\n🧠 Раунд из 5 вопросов бесплатно каждый день."),
        "btn_quiz": "🧠 Викторина", "btn_word": "📖 Слово дня", "btn_me": "🔥 Моя серия", "btn_saved": "💾 Мои слова",
        "btn_invite": "👥 Пригласить", "btn_premium": "⭐ Премиум", "btn_sub_on": "🔔 Слово дня в личку",
        "btn_sub_off": "🔕 Отключить рассылку", "btn_next": "➡️ Дальше ({n}/{total})", "btn_finish": "🏁 Итог",
        "btn_save": "💾 Сохранить", "btn_share": "📤 Поделиться", "btn_again": "🔁 Ещё раунд", "btn_lang": "🌐 English",
        "q_header": "Вопрос {n}/{total}", "right": "✅ Верно!", "wrong": "❌ Нет. Правильно: {a}",
        "stale": "Эта кнопка устарела. Нажми /start.", "round_gone": "Раунд уже закончился. Начни новый: /quiz",
        "limit": ("🔒 <b>Бесплатный раунд на сегодня сыгран.</b>\n\nХочешь ещё прямо сейчас?\n"
                  "• ⭐ Премиум: безлимитные раунды, весь архив, сохранённые слова без лимита\n"
                  "• 👥 Позови друга: +{b} раунда тебе и +{c} ему"),
        "result_caption": "🏁 <b>{score}/{total}</b> · {rank}\n{streak}\nВсего верных ответов: {correct}",
        "streak_line": "🔥 Серия: {n} дн. (рекорд {best})", "streak_none": "Начни серию: заходи каждый день!",
        "me": ("<b>Твой профиль</b>\n\nРанг: <b>{rank}</b>\nВерных ответов: {correct} из {answered}\nРаундов: {rounds}\n"
               "🔥 Серия: {streak} дн. (рекорд {best})\n💾 Сохранено слов: {saved}\n👥 Приглашено друзей: {refs}\n{prem}"),
        "prem_on": "⭐ Премиум до {date}", "prem_off": "⭐ Премиум не активен",
        "saved_title": "<b>Мои слова</b> ({n}{limit})", "saved_empty": "Пока пусто. Жми «💾 Сохранить» под любым словом.",
        "saved_full": "💾 Лимит сохранений для бесплатного режима: {n}. Безлимит даёт премиум: /premium",
        "saved_ok": "💾 Сохранено", "saved_already": "Уже в твоих словах",
        "invite": ("👥 <b>Позови друга</b>\n\nЗа каждого друга, который зайдёт по твоей ссылке: <b>+{b} бесплатных раунда</b> тебе "
                   "и +{c} ему.\n\nТвоя ссылка:\n{link}\n\nПриглашено: {n}"),
        "invite_notice": "🎉 По твоей ссылке пришёл друг! Тебе +{b} раунда викторины.",
        "btn_duel": "⚔️ Вызвать друга",
        "duel_made": "⚔️ <b>Вызов готов!</b>\n\nТвой счёт: {score}/{total}. Отправь ссылку другу: он сыграет в те же {total} вопросов, и вы сравните результат. Ему это ничего не стоит.\n\n{link}",
        "duel_share": "Я набрал {score}/{total} в викторине про происхождение слов. Сможешь лучше? Те же вопросы:",
        "duel_intro": "⚔️ <b>{name} вызывает тебя!</b>\n\nТе же {total} вопросов, что были у него. Это бесплатно и не тратит твой дневной раунд.",
        "duel_own": "Это твой вызов. Отправь эту ссылку другу:\n{link}",
        "duel_done": "Ты уже играл в этом вызове. Хочешь свой? Жми «🧠 Викторина».",
        "duel_gone": "Вызов не найден. Начни свой: /quiz",
        "duel_win": "🏆 <b>Победа!</b> У тебя {mine}/{total}, у {name} — {theirs}/{total}.",
        "duel_draw": "🤝 <b>Ничья!</b> У обоих по {mine}/{total}.",
        "duel_lose": "😅 <b>В этот раз не вышло.</b> У тебя {mine}/{total}, у {name} — {theirs}/{total}. Сыграй свой раунд и брось реванш.",
        "duel_notice": "⚔️ {name} сыграл твой вызов: у него {theirs}/{total}, у тебя {mine}/{total}. {verdict}",
        "verdict_win": "Ты впереди!", "verdict_draw": "Ничья.", "verdict_lose": "Он тебя обошёл, пора на реванш.",
        "friend": "друг",
        "week_active": "📊 <b>Твоя неделя в Wordlore</b>\n\nОтветов: {answered}, из них верных: {correct}\nРаундов: {rounds}\n🔥 Серия: {streak} дн.\n\nНовая неделя, новые слова. Сыграем?",
        "week_idle": "👋 На этой неделе викторина ждала, а ты не заходил. Один раунд занимает минуту, а слово дня ты всё равно получаешь каждое утро.",
        "invite_welcome": "🎁 Ты пришёл по приглашению: +{c} бонусный раунд викторины.",
        "premium": ("⭐ <b>Wordlore Премиум</b>\n\n• Безлимитные раунды викторины\n• Весь архив: любое слово из {n} через /random\n"
                    "• Сохранённые слова без лимита\n• Серия переживёт один пропущенный день\n\n{status}"),
        "buy_30": "30 дней · {p} ⭐", "buy_365": "Год · {p} ⭐ (−{off}%)",
        "inv_title_30": "Премиум на 30 дней", "inv_title_365": "Премиум на год",
        "inv_desc": "Безлимитные викторины, весь архив и сохранённые слова",
        "paid": "Спасибо! ⭐ Премиум активен до {date}. /random открывает любое слово из архива.",
        "need_premium": "Архив из {n} слов открыт в премиуме: /premium",
        "sub_on": "🔔 Готово! Буду присылать слово дня в 10:00 (Алматы). Отключить: /sub",
        "sub_off": "🔕 Рассылка отключена. Включить снова: /sub",
        "lang_set": "Язык: русский",
        "daily_caption": "Слово дня",
        "share_word": "Слово дня в Wordlore: {word}", "share_result": "Я набрал {score}/{total} в викторине Wordlore ({rank}). А сколько наберёшь ты?",
        "promo_footer": "Ещё: {promo}",
    },
    "en": {
        "welcome": ("<b>Wordlore</b> — the stories behind words.\n\nWhy is a robot 'forced labour'? What do 'salary' and salt "
                    "have in common? Every day a new word with its family tree, plus quizzes, streaks and ranks.\n\n"
                    "🧠 One 5-question round is free every day."),
        "btn_quiz": "🧠 Quiz", "btn_word": "📖 Word of the day", "btn_me": "🔥 My streak", "btn_saved": "💾 My words",
        "btn_invite": "👥 Invite", "btn_premium": "⭐ Premium", "btn_sub_on": "🔔 Daily word in DM",
        "btn_sub_off": "🔕 Turn off daily DM", "btn_next": "➡️ Next ({n}/{total})", "btn_finish": "🏁 Result",
        "btn_save": "💾 Save", "btn_share": "📤 Share", "btn_again": "🔁 Another round", "btn_lang": "🌐 Русский",
        "q_header": "Question {n}/{total}", "right": "✅ Correct!", "wrong": "❌ No. Correct answer: {a}",
        "stale": "This button is outdated. Tap /start.", "round_gone": "That round is over. Start a new one: /quiz",
        "limit": ("🔒 <b>Today's free round is done.</b>\n\nWant more right now?\n"
                  "• ⭐ Premium: unlimited rounds, the full archive, unlimited saved words\n"
                  "• 👥 Invite a friend: +{b} rounds for you and +{c} for them"),
        "result_caption": "🏁 <b>{score}/{total}</b> · {rank}\n{streak}\nTotal correct answers: {correct}",
        "streak_line": "🔥 Streak: {n} days (best {best})", "streak_none": "Start a streak: come back every day!",
        "me": ("<b>Your profile</b>\n\nRank: <b>{rank}</b>\nCorrect answers: {correct} of {answered}\nRounds: {rounds}\n"
               "🔥 Streak: {streak} days (best {best})\n💾 Saved words: {saved}\n👥 Friends invited: {refs}\n{prem}"),
        "prem_on": "⭐ Premium until {date}", "prem_off": "⭐ Premium is not active",
        "saved_title": "<b>My words</b> ({n}{limit})", "saved_empty": "Nothing yet. Tap “💾 Save” under any word.",
        "saved_full": "💾 Free accounts can save {n} words. Premium is unlimited: /premium",
        "saved_ok": "💾 Saved", "saved_already": "Already in your words",
        "invite": ("👥 <b>Invite a friend</b>\n\nFor every friend who joins through your link: <b>+{b} free rounds</b> for you "
                   "and +{c} for them.\n\nYour link:\n{link}\n\nInvited: {n}"),
        "invite_notice": "🎉 A friend joined through your link! +{b} quiz rounds for you.",
        "btn_duel": "⚔️ Challenge a friend",
        "duel_made": "⚔️ <b>Challenge ready!</b>\n\nYour score: {score}/{total}. Send the link to a friend: they play the same {total} questions and you compare. It costs them nothing.\n\n{link}",
        "duel_share": "I got {score}/{total} in a quiz about where words come from. Can you beat it? Same questions:",
        "duel_intro": "⚔️ <b>{name} challenges you!</b>\n\nThe same {total} questions they had. It's free and doesn't use up your daily round.",
        "duel_own": "This is your own challenge. Send this link to a friend:\n{link}",
        "duel_done": "You've already played this challenge. Want your own? Tap “🧠 Quiz”.",
        "duel_gone": "Challenge not found. Start your own: /quiz",
        "duel_win": "🏆 <b>You win!</b> You {mine}/{total}, {name} {theirs}/{total}.",
        "duel_draw": "🤝 <b>A draw!</b> Both got {mine}/{total}.",
        "duel_lose": "😅 <b>Not this time.</b> You {mine}/{total}, {name} {theirs}/{total}. Play your own round and send a rematch.",
        "duel_notice": "⚔️ {name} played your challenge: {theirs}/{total} against your {mine}/{total}. {verdict}",
        "verdict_win": "You're ahead!", "verdict_draw": "A draw.", "verdict_lose": "They beat you, time for a rematch.",
        "friend": "a friend",
        "week_active": "📊 <b>Your week in Wordlore</b>\n\nAnswers: {answered}, correct: {correct}\nRounds: {rounds}\n🔥 Streak: {streak} days\n\nNew week, new words. Shall we play?",
        "week_idle": "👋 The quiz waited all week and you didn't drop by. A round takes a minute, and you still get a word every morning.",
        "invite_welcome": "🎁 You joined by invitation: +{c} bonus quiz round.",
        "premium": ("⭐ <b>Wordlore Premium</b>\n\n• Unlimited quiz rounds\n• Full archive: any of {n} words via /random\n"
                    "• Unlimited saved words\n• Your streak survives one missed day\n\n{status}"),
        "buy_30": "30 days · {p} ⭐", "buy_365": "1 year · {p} ⭐ (−{off}%)",
        "inv_title_30": "Premium, 30 days", "inv_title_365": "Premium, 1 year",
        "inv_desc": "Unlimited quizzes, the full archive and saved words",
        "paid": "Thank you! ⭐ Premium is active until {date}. /random shows any word from the archive.",
        "need_premium": "The archive of {n} words is a premium feature: /premium",
        "sub_on": "🔔 Done! I'll send the word of the day at 10:00 (Almaty). Turn off: /sub",
        "sub_off": "🔕 Daily DM turned off. Turn on again: /sub",
        "lang_set": "Language: English",
        "daily_caption": "Word of the day",
        "share_word": "Word of the day on Wordlore: {word}", "share_result": "I scored {score}/{total} in the Wordlore quiz ({rank}). Can you beat it?",
        "promo_footer": "More: {promo}",
    },
}
