"""What people see before they press START, and the command menu."""
COMMANDS = {
    "ru": [("start", "Начать"), ("word", "Слово дня"), ("quiz", "Викторина на 5 вопросов"), ("me", "Мой ранг и серия"),
           ("saved", "Мои слова"), ("random", "Случайное слово (премиум)"), ("invite", "Позвать друга, получить раунды"),
           ("sub", "Слово дня в личку: вкл/выкл"), ("premium", "Премиум"), ("lang", "English / Русский")],
    "en": [("start", "Start"), ("word", "Word of the day"), ("quiz", "5-question quiz"), ("me", "My rank and streak"),
           ("saved", "My saved words"), ("random", "Random word (premium)"), ("invite", "Invite a friend, get rounds"),
           ("sub", "Daily word in DM: on/off"), ("premium", "Premium"), ("lang", "English / Русский")],
}
DESCRIPTION = {
    "ru": ("Каждый день одно слово и его настоящая история: откуда пришло, через какие языки дошло, что значило раньше.\n\n"
           "Красивая карточка, которой не стыдно поделиться. Плюс викторина на 5 вопросов, серия дней и ранги: "
           "от «Любопытного» до «Хранителя слов».\n\nНажми START."),
    "en": ("One word a day and its real story: where it came from, which languages it passed through, what it used to mean.\n\n"
           "A good-looking card you can share. Plus a 5-question quiz, daily streaks and ranks, "
           "from Curious to Keeper of Words.\n\nPress START."),
}
SHORT = {
    "ru": "Слово дня с историей происхождения, викторины и ранги",
    "en": "A word of the day with its origin story, quizzes and ranks",
}
