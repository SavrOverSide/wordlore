"""Static website with every word's story (for search engines and for sharing), built into docs/.

python3 tools/site.py   ->  docs/index.html, docs/w/<slug>.html, docs/sitemap.xml, docs/robots.txt
Published with GitHub Pages (Settings -> Pages -> Deploy from branch: main, /docs).
"""
import html
import zlib
import json
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from lingvo.collections import all_keys, members, title as coll_title  # noqa: E402
from lingvo.site import SITE as BASE, slugs  # noqa: E402

OUT = ROOT / "docs"
WORDS = json.loads((ROOT / "lingvo" / "words.json").read_text(encoding="utf-8"))
SLUGS = slugs(WORDS)
e = lambda s: html.escape(str(s), quote=True)  # noqa: E731
COLL = {i: k for k in all_keys() for i in members(WORDS, k)}

CSS = """
:root{--ink:#14202b;--muted:#4f5d6b;--ground:#f5f7f9;--card:#fff;--line:#dfe5eb;--accent:#0b6e75;--accent-ink:#fff}
*{box-sizing:border-box}body{margin:0;background:var(--ground);color:var(--ink);font:17px/1.6 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Arial,sans-serif}
a{color:var(--accent)}a:hover{color:#08494e}
.wrap{max-width:820px;margin:0 auto;padding:0 20px}
header{border-bottom:1px solid var(--line);background:var(--card)}
header .wrap{display:flex;align-items:center;justify-content:space-between;gap:12px;min-height:60px;flex-wrap:wrap}
.brand{font-weight:800;text-decoration:none;color:var(--ink);font-size:19px}
.btn{display:inline-flex;align-items:center;justify-content:center;min-height:44px;padding:0 18px;border-radius:12px;background:var(--accent);color:var(--accent-ink);font-weight:700;text-decoration:none}
.btn:hover{background:#08494e;color:#fff}.btn.alt{background:var(--card);color:var(--ink);border:1px solid var(--line)}
h1{font-size:clamp(28px,5vw,40px);line-height:1.15;margin:32px 0 8px}
.badge{display:inline-block;padding:4px 10px;border-radius:999px;background:#e2f0f1;color:#08494e;font-weight:700;font-size:14px}
.chain{display:flex;flex-wrap:wrap;gap:8px;align-items:center;margin:24px 0;padding:0;list-style:none}
.chain li{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:8px 12px}
.chain b{display:block}.chain span{color:var(--muted);font-size:14px}
.chain .arrow{border:0;background:none;padding:0;color:var(--muted)}
.card{background:var(--card);border:1px solid var(--line);border-radius:16px;padding:20px 22px;margin:20px 0}
.card h2{font-size:20px;margin:0 0 8px}
details summary{cursor:pointer;font-weight:700;color:var(--accent);min-height:44px;display:flex;align-items:center}
.cta{background:var(--ink);color:#fff;border-radius:18px;padding:24px;margin:28px 0;display:flex;flex-wrap:wrap;gap:16px;align-items:center;justify-content:space-between}
.cta p{margin:0;flex:1 1 320px}.cta .btn{background:#fff;color:var(--ink)}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(150px,1fr));gap:8px;padding:0;list-style:none}
.grid a{display:block;background:var(--card);border:1px solid var(--line);border-radius:10px;padding:10px 12px;text-decoration:none;color:var(--ink);font-weight:600}
.grid a:hover{border-color:var(--accent)}
input[type=search]{width:100%;min-height:48px;font:inherit;padding:0 14px;border-radius:12px;border:1px solid var(--line)}
footer{color:var(--muted);font-size:14px;padding:32px 0 48px}
.muted{color:var(--muted)}
"""


def page(title, desc, path, body, lang="ru"):
    url = f"{BASE}/{path}"
    return f"""<!doctype html>
<html lang="{lang}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{e(title)}</title>
<meta name="description" content="{e(desc)}">
<link rel="canonical" href="{e(url)}">
<meta property="og:title" content="{e(title)}">
<meta property="og:description" content="{e(desc)}">
<meta property="og:url" content="{e(url)}">
<meta property="og:image" content="{BASE}/og.jpg">
<meta property="og:type" content="article">
<link rel="stylesheet" href="{'../' if '/' in path else ''}style.css">
</head>
<body>
<header><div class="wrap"><a class="brand" href="{'../' if '/' in path else './'}">Wordlore</a>
<a class="btn" href="https://t.me/wordlore_bot?start=quiz">Викторина в Telegram</a></div></header>
<main class="wrap">
{body}
</main>
<footer class="wrap">Wordlore: истории слов. Каждый день новое слово в Telegram: <a href="https://t.me/wordlores">@wordlores</a>.
Этимология дана по открытым словарям (Etymonline, Викисловарь и др.); спорные версии помечены.<br>Ещё наш проект: <a href="https://savroverside.github.io/ideaforgegen/">генераторы идей для настольных ролевых игр</a>.</footer>
</body>
</html>
"""


def ru_gloss(g: str) -> str:
    return g.split(" · ")[0]


def word_page(i: int) -> str:
    w = WORDS[i]
    origin = w.get("origin", "").split(" · ")[0]
    chain = []
    for n, step in enumerate(w.get("path", [])):
        term, _, gloss = step.partition("|")
        if n:
            chain.append('<li class="arrow" aria-hidden="true">→</li>')
        chain.append(f"<li><b>{e(term)}</b>" + (f"<span>{e(ru_gloss(gloss))}</span>" if gloss else "") + "</li>")
    opts = [w["a"]] + w["w"]
    opts = sorted(opts, key=lambda o: zlib.crc32((w["word"] + o).encode()))
    options = "".join(f"<li>{e(o.split(' / ')[0])}</li>" for o in opts)
    related = [j for j in members(WORDS, COLL[i]) if j != i][:12]
    rel = "".join(f'<li><a href="{SLUGS[j]}.html">{e(WORDS[j]["word"])}</a></li>' for j in related)
    body = f"""
<p><a href="../">← Все слова</a></p>
<h1>Происхождение слова «{e(w['word'])}»</h1>
<p><span class="badge">{e(origin)}</span> <span class="muted">· {e(coll_title(COLL[i], 'ru'))}</span></p>
<ol class="chain" aria-label="Путь слова">{''.join(chain)}</ol>
<p>{e(w['ru'])}</p>
<div class="card"><h2>Проверь себя</h2>
<p>{e(w['q']['ru'])}</p><ul>{options}</ul>
<details><summary>Показать ответ</summary><p><b>{e(w['a'].split(' / ')[0])}</b>. {e((w.get('fact') or {}).get('ru', ''))}</p></details></div>
<div class="card" lang="en"><h2>In English</h2><p>{e(w['en'])}</p></div>
<div class="cta"><p><b>Понравилось?</b> Каждое утро новое слово с такой историей в Telegram, а в боте викторина на 5 вопросов и дуэли с друзьями.</p>
<a class="btn" href="https://t.me/wordlore_bot?start=quiz">Сыграть в викторину</a></div>
<h2>Ещё слова из коллекции «{e(coll_title(COLL[i], 'ru').split(' ', 1)[1])}»</h2>
<ul class="grid">{rel}</ul>
"""
    desc = w["ru"] if len(w["ru"]) <= 155 else w["ru"][:152].rsplit(" ", 1)[0] + "…"
    return page(f"Откуда слово «{w['word']}»: происхождение и история | Wordlore", desc, f"w/{SLUGS[i]}.html", body)


def index_page() -> str:
    sections = []
    for k in all_keys():
        ids = sorted(members(WORDS, k), key=lambda j: WORDS[j]["word"].lower())
        if not ids:
            continue
        items = "".join(f'<li data-w="{e(WORDS[j]["word"].lower())}"><a href="w/{SLUGS[j]}.html">{e(WORDS[j]["word"])}</a></li>' for j in ids)
        sections.append(f'<section><h2>{e(coll_title(k, "ru"))} <span class="muted">· {len(ids)}</span></h2><ul class="grid">{items}</ul></section>')
    body = f"""
<h1>Истории слов</h1>
<p>Откуда пришли слова, которыми мы пользуемся каждый день: {len(WORDS)} коротких историй с цепочкой языков, через которые слово дошло до нас. Русские и английские слова, заимствования из тюркских, арабского, греческого, латыни и других языков.</p>
<p><label for="q" class="muted">Найти слово</label><input id="q" type="search" placeholder="например, шахматы или robot" autocomplete="off"></p>
{''.join(sections)}
<div class="cta"><p><b>Каждый день по слову.</b> Подпишитесь на канал или сыграйте в викторину в Telegram.</p>
<a class="btn" href="https://t.me/wordlores">Канал @wordlores</a></div>
<script>
document.getElementById('q').addEventListener('input', function () {{
  var q = this.value.trim().toLowerCase().replace(/ё/g, 'е');
  document.querySelectorAll('li[data-w]').forEach(function (li) {{
    li.hidden = q && li.dataset.w.replace(/ё/g, 'е').indexOf(q) === -1;
  }});
  document.querySelectorAll('section').forEach(function (s) {{
    s.hidden = q && !s.querySelector('li[data-w]:not([hidden])');
  }});
}});
</script>
"""
    return page("Wordlore: происхождение слов, истории и этимология", f"{len(WORDS)} историй о происхождении слов: откуда они пришли и что значили раньше. Викторина и слово дня в Telegram.", "", body)


def main():
    (OUT / "w").mkdir(parents=True, exist_ok=True)
    (OUT / "style.css").write_text(CSS.strip() + "\n", encoding="utf-8")
    (OUT / "index.html").write_text(index_page(), encoding="utf-8")
    for i in range(len(WORDS)):
        (OUT / "w" / f"{SLUGS[i]}.html").write_text(word_page(i), encoding="utf-8")
    today = date.today().isoformat()
    urls = [f"{BASE}/"] + [f"{BASE}/w/{s}.html" for s in SLUGS]
    (OUT / "sitemap.xml").write_text('<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
                                     + "".join(f"<url><loc>{u}</loc><lastmod>{today}</lastmod></url>\n" for u in urls) + "</urlset>\n",
                                     encoding="utf-8")
    (OUT / "robots.txt").write_text(f"User-agent: *\nAllow: /\nSitemap: {BASE}/sitemap.xml\n", encoding="utf-8")
    (OUT / ".nojekyll").write_text("", encoding="utf-8")
    print(len(urls), "pages")


if __name__ == "__main__":
    main()
