"""Renders a shareable picture card for a word (1080x1350, Telegram-friendly 4:5)."""
import hashlib
import io
import random
import re
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont

FONTS = Path(__file__).resolve().parent.parent / "assets" / "fonts"
W, H = 1080, 1350
PAD = 84

# (base top, base bottom, accent, glow1, glow2): picked per word so a word always looks the same
PALETTES = [
    ((14, 12, 38), (30, 16, 64), (255, 196, 87), (120, 60, 220), (255, 90, 140)),
    ((6, 24, 40), (8, 44, 66), (126, 240, 212), (20, 160, 200), (90, 80, 230)),
    ((34, 8, 24), (60, 14, 40), (255, 163, 143), (230, 60, 100), (255, 150, 60)),
    ((8, 22, 16), (12, 40, 30), (214, 255, 128), (40, 200, 120), (30, 140, 200)),
    ((16, 16, 28), (26, 28, 60), (150, 190, 255), (80, 110, 255), (180, 90, 255)),
    ((30, 14, 8), (56, 26, 12), (255, 214, 140), (255, 120, 40), (220, 60, 80)),
]


def font(name: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(FONTS / f"Inter-{name}.otf"), size)


def first_sentence(text: str, limit: int = 150) -> str:
    s = re.split(r"(?<=[.!?])\s", text.strip(), maxsplit=1)[0]
    return s if len(s) <= limit else s[: limit - 1].rsplit(" ", 1)[0] + "…"


def wrap(draw, text, fnt, width):
    lines, line = [], ""
    for word in text.split():
        trial = f"{line} {word}".strip()
        if draw.textlength(trial, font=fnt) <= width:
            line = trial
        else:
            lines.append(line)
            line = word
    return lines + [line] if line else lines


def background(top, bottom, glow1, glow2, rnd):
    strip = Image.new("RGB", (1, H))
    for y in range(H):
        t = y / (H - 1)
        strip.putpixel((0, y), tuple(int(top[i] + (bottom[i] - top[i]) * t) for i in range(3)))
    img = strip.resize((W, H)).convert("RGBA")
    # soft colour blobs give the mesh-gradient look
    blobs = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    bd = ImageDraw.Draw(blobs)
    for color, (cx, cy, r, a) in (
        (glow1, (rnd.randint(0, 400), rnd.randint(-100, 250), 520, 150)),
        (glow2, (rnd.randint(650, 1100), rnd.randint(700, 1300), 560, 120)),
        (glow1, (rnd.randint(700, 1100), rnd.randint(100, 500), 300, 70)),
    ):
        bd.ellipse((cx - r, cy - r, cx + r, cy + r), fill=color + (a,))
    img = over(img, blobs.filter(ImageFilter.GaussianBlur(130)))
    # dot grid in the upper right corner
    dots = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    dd = ImageDraw.Draw(dots)
    for x in range(W - 420, W - 40, 34):
        for y in range(70, 330, 34):
            dd.ellipse((x - 2, y - 2, x + 2, y + 2), fill=(255, 255, 255, 46))
    img = over(img, dots)
    # film grain
    grain = Image.effect_noise((W, H), 48).convert("RGB")
    return Image.blend(img, ImageChops.overlay(img, grain), 0.22)


def over(img, layer):
    return Image.alpha_composite(img.convert("RGBA"), layer).convert("RGB")


def glass(img, box, radius=44):
    """Frosted-glass panel: blurred backdrop, white tint and a thin bright edge."""
    x0, y0, x1, y1 = box
    mask = Image.new("L", (W, H), 0)
    ImageDraw.Draw(mask).rounded_rectangle(box, radius, fill=255)
    img = Image.composite(img.filter(ImageFilter.GaussianBlur(28)), img, mask)
    tint = Image.new("RGBA", (W, H), (255, 255, 255, 0))
    ImageDraw.Draw(tint).rounded_rectangle(box, radius, fill=(255, 255, 255, 22), outline=(255, 255, 255, 70), width=2)
    return over(img, tint)


def render(word: str, ru: str, en: str, origin: str = "", path=(), handle: str = "@wordlores") -> bytes:
    idx = int(hashlib.md5(word.encode()).hexdigest(), 16) % len(PALETTES)
    top, bottom, accent, g1, g2 = PALETTES[idx]
    rnd = random.Random(word)
    img = background(top, bottom, g1, g2, rnd)
    A = accent + (255,)
    white = (255, 255, 255, 255)

    # oversized ghost initial behind everything
    ghost = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(ghost).text((W + 40, 760), word[0].upper(), font=font("ExtraBold", 1000), fill=accent + (22,), anchor="rm")
    img = over(img, ghost)

    d = ImageDraw.Draw(img, "RGBA")
    # header: logo mark + name, date chip
    d.rounded_rectangle((PAD, 80, PAD + 64, 144), 18, fill=A)
    d.text((PAD + 32, 112), "W", font=font("ExtraBold", 40), fill=top + (255,), anchor="mm")
    d.text((PAD + 86, 112), "WORDLORE", font=font("Bold", 30), fill=white, anchor="lm")
    d.text((PAD + 86 + 190 + 24, 112), "СЛОВО ДНЯ · WORD OF THE DAY", font=font("Medium", 22), fill=(255, 255, 255, 140), anchor="lm")

    y = 215
    if origin:
        f = font("SemiBold", 28)
        tw = d.textlength(origin.upper(), font=f)
        d.rounded_rectangle((PAD, y, PAD + tw + 56, y + 58), 29, fill=accent + (38,), outline=accent + (140,), width=2)
        d.text((PAD + 28, y + 29), origin.upper(), font=f, fill=A, anchor="lm")
        y += 100

    size = 200
    while size > 70 and d.textlength(word, font=font("ExtraBold", size)) > W - 2 * PAD:
        size -= 6
    d.text((PAD, y), word, font=font("ExtraBold", size), fill=white)
    y += size + 60

    # glass panel with the etymology path and the short story
    panel_top = y
    nodes = [p.split("|", 1) for p in path]
    fr, fe = font("Medium", 40), font("Regular", 30)
    ru_lines = wrap(d, ru, fr, W - 2 * PAD - 80)
    en_lines = wrap(d, en, fe, W - 2 * PAD - 80)
    room = H - 175 - panel_top
    step = 92

    def need():
        return 56 + (len(nodes) * step + 24 if nodes else 0) + len(ru_lines) * 58 + 14 + len(en_lines) * 46 + 36

    if need() > room:  # never show half an English sentence: all or nothing
        en_lines = []
    panel_bottom = panel_top + need()
    img = glass(img, (PAD - 24, panel_top, W - PAD + 24, panel_bottom))
    d = ImageDraw.Draw(img, "RGBA")

    cy = panel_top + 56
    if nodes:
        x = PAD + 26
        d.line((x, cy + 14, x, cy + (len(nodes) - 1) * step + 14), fill=accent + (150,), width=4)
        for i, node in enumerate(nodes):
            term, gloss = node[0], (node[1] if len(node) > 1 else "")
            last = i == len(nodes) - 1
            r = 15 if last else 11
            d.ellipse((x - r, cy + 14 - r, x + r, cy + 14 + r), fill=A if last else top + (255,), outline=A, width=4)
            d.text((x + 52, cy + 14), term, font=font("ExtraBold" if last else "Bold", 40), fill=A if last else white, anchor="lm")
            if gloss and not last:
                tx = x + 52 + d.textlength(term, font=font("Bold", 40)) + 22
                gf = font("Regular", 27)
                limit = W - PAD - 30
                if tx + d.textlength(gloss, font=gf) > limit:  # keep only the first language if too long
                    gloss = gloss.split(" · ")[0]
                while gloss and tx + d.textlength(gloss, font=gf) > limit:
                    gf = font("Regular", gf.size - 2)
                d.text((tx, cy + 18), gloss, font=gf, fill=(255, 255, 255, 150), anchor="lm")
            cy += step
        cy += 16
        d.line((PAD + 26, cy - 22, W - PAD - 26, cy - 22), fill=(255, 255, 255, 40), width=2)
        cy += 8
    for line in ru_lines:
        d.text((PAD + 26, cy), line, font=fr, fill=(255, 255, 255, 240))
        cy += 58
    cy += 14
    for line in en_lines:
        d.text((PAD + 26, cy), line, font=fe, fill=(255, 255, 255, 150))
        cy += 46

    # footer
    d.line((PAD, H - 140, W - PAD, H - 140), fill=(255, 255, 255, 40), width=2)
    d.text((PAD, H - 90), handle, font=font("Bold", 36), fill=A, anchor="lm")
    d.text((W - PAD, H - 90), "t.me/wordlore_bot", font=font("Medium", 28), fill=(255, 255, 255, 150), anchor="rm")

    out = io.BytesIO()
    img.save(out, "JPEG", quality=92, optimize=True)
    return out.getvalue()
