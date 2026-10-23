"""Addresses of the words on the public website (built by tools/site.py into docs/)."""
import re

SITE = "https://savroverside.github.io/wordlore"
TR = dict(zip("абвгдеёжзийклмнопрстуфхцчшщъыьэюя",
              "a b v g d e e zh z i y k l m n o p r s t u f kh ts ch sh shch - y - e yu ya".split()))


def slugs(words: list) -> list:
    """One unique url slug per word, in the order of the list (stable as long as the list order is)."""
    used, out = set(), []
    for w in words:
        s = "".join(TR.get(c, c) for c in w["word"].lower()).replace("-", "")
        s = re.sub(r"[^a-z0-9]+", "-", s).strip("-") or "word"
        base, n = s, 2
        while s in used:
            s, n = f"{base}-{n}", n + 1
        used.add(s)
        out.append(s)
    return out


def word_urls(words: list) -> list:
    return [f"{SITE}/w/{s}.html" for s in slugs(words)]
