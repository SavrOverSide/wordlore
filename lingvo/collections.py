"""Collections of words grouped by where they came from. Built from each word's `origin` field,
so a new word lands in the right collection automatically."""

# key -> (emoji, name ru, name en, origin names (Russian part, lowercase) that belong to it)
COLLECTIONS = {
    "east": ("🐎", "Степь и Восток", "Steppe and the East",
             {"тюркский", "тюркские", "казахский", "тюрко-монгольский", "турецкий", "арабский", "персидский", "староиранский", "хинди", "санскрит"}),
    "antique": ("🏛", "Античность", "Antiquity", {"греческий", "латынь"}),
    "romance": ("🥐", "Из Франции, Италии, Испании", "From France, Italy and Spain",
                {"французский", "старофранцузский", "итальянский", "испанский"}),
    "asia": ("🌸", "Дальний Восток", "The Far East", {"японский", "китайский", "корейский", "яванский", "японский (из английского)"}),
    "north": ("⚔️", "Север и германцы", "The North and Germanic",
              {"английский", "немецкий", "нидерландский", "древнескандинавский", "гэльский", "датский", "староанглийский", "нижненемецкий", "саамский"}),
    "slavic": ("🌾", "Славянские корни", "Slavic roots", {"праславянский", "русский", "чешский", "коми"}),
}
FREE_COLLECTION = "east"   # the one collection everybody can browse; the others come with premium
OTHER = ("🌍", "Со всего света", "From around the world")


def origin_key(origin: str) -> str:
    name = (origin or "").split("·")[0].strip().lower()
    for key, (_e, _r, _n, names) in COLLECTIONS.items():
        if name in names:
            return key
    return "world"


def title(key: str, lg: str) -> str:
    if key == "world":
        emoji, ru, en = OTHER
    else:
        emoji, ru, en, _ = COLLECTIONS[key]
    return f"{emoji} {ru if lg == 'ru' else en}"


def members(words: list, key: str) -> list:
    return [i for i, w in enumerate(words) if origin_key(w.get("origin", "")) == key]


def all_keys() -> list:
    return list(COLLECTIONS) + ["world"]
