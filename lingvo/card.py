"""Renders a shareable picture card for a word (1080x1350, Telegram-friendly 4:5)."""
import hashlib
import io
import re
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

FONTS = Path(__file__).resolve().parent.parent / "assets" / "fonts"
W, H = 1080, 1350
PAD = 90

# (top, bottom, accent) — picked deterministically per word, so a word always looks the same
PALETTES = [
    ((18, 16, 46), (74, 36, 120), (255, 196, 87)),
    ((8, 32, 50), (14, 90, 110), (126, 240, 212)),
    ((40, 12, 28), (140, 38, 70), (255, 163, 143)),
    ((12, 24, 18), (30, 94, 66), (214, 255, 128)),
    ((20, 20, 24), (62, 70, 140), (150, 190, 255)),
    ((38, 18, 8), (150, 72, 20), (255, 214, 140)),
]


def font(name: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(FONTS / f"Inter-{name}.otf"), size)


def first_sentence(text: str, limit: int = 170) -> str:
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


def gradient(top, bottom):
    strip = Image.new("RGB", (1, H))
    for y in range(H):
        t = y / (H - 1)
        strip.putpixel((0, y), tuple(int(top[i] + (bottom[i] - top[i]) * t) for i in range(3)))
    return strip.resize((W, H))


def render(word: str, ru: str, en: str, tag: str = "СЛОВО ДНЯ · WORD OF THE DAY", handle: str = "@wordlores") -> bytes:
    idx = int(hashlib.md5(word.encode()).hexdigest(), 16) % len(PALETTES)
    top, bottom, accent = PALETTES[idx]
    img = gradient(top, bottom).convert("RGBA")

    # giant ghost letter + soft glow for depth
    ghost = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    gd = ImageDraw.Draw(ghost)
    gf = font("ExtraBold", 1100)
    gd.text((W - 80, H - 120), word[0].upper(), font=gf, fill=accent + (26,), anchor="rb")
    glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(glow).ellipse((-300, -300, 700, 700), fill=accent + (60,))
    img = Image.alpha_composite(img, glow.filter(ImageFilter.GaussianBlur(160)))
    img = Image.alpha_composite(img, ghost)

    d = ImageDraw.Draw(img)
    d.text((PAD, 110), tag, font=font("SemiBold", 30), fill=accent + (255,))
    d.rounded_rectangle((PAD, 160, PAD + 90, 166), 3, fill=accent + (255,))

    # word, shrunk to fit
    size = 190
    while size > 70 and d.textlength(word, font=font("ExtraBold", size)) > W - 2 * PAD:
        size -= 6
    d.text((PAD, 250), word, font=font("ExtraBold", size), fill=(255, 255, 255, 255))

    y = 250 + size + 90
    for text, fsize, color in ((first_sentence(ru), 44, (255, 255, 255, 235)), (first_sentence(en), 36, (255, 255, 255, 170))):
        f = font("Medium", fsize)
        for line in wrap(d, text, f, W - 2 * PAD)[:5]:
            d.text((PAD, y), line, font=f, fill=color)
            y += int(fsize * 1.45)
        y += 50
        d.line((PAD, y - 25, PAD + 60, y - 25), fill=accent + (160,), width=3)
        y += 20

    d.text((PAD, H - 120), handle, font=font("Bold", 36), fill=accent + (255,))
    d.text((W - PAD, H - 120), "t.me/wordlore_bot", font=font("Medium", 30), fill=(255, 255, 255, 150), anchor="ra")

    out = io.BytesIO()
    img.convert("RGB").save(out, "JPEG", quality=92, optimize=True)
    return out.getvalue()
