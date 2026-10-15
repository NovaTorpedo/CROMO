"""Seeded page renderer for the synthetic CROMO archive.

Turns a document spec (see scenario_docs.py) into page images. Digital documents
also get a text layer (like the embedded text of a born-digital PDF); scanned,
faxed and handwritten documents get none, so the pipeline must read them with a
vision model. For offline fixture mode we additionally record each scanned page's
transcription, keyed by the image hash.
"""

from __future__ import annotations

import math
import random
import textwrap
from dataclasses import dataclass, field
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

FONTS = Path(__file__).parent / "fonts"
W, H = 1000, 1414
MARGIN = 78


def font(name: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(FONTS / name), size)


@dataclass
class Line:
    text: str
    bbox: tuple[int, int, int, int]
    kind: str = "body"  # body | header | handwritten | stamp | meta


@dataclass
class Page:
    image: Image.Image
    lines: list[Line] = field(default_factory=list)


# ----------------------------------------------------------------------------
# style per document form
# ----------------------------------------------------------------------------
STYLES = {
    "digital": dict(body="IBMPlexSans.ttf", size=21, head="IBMPlexSans.ttf", ink=(28, 30, 34), paper=(255, 255, 255)),
    "email": dict(body="IBMPlexMono-Regular.ttf", size=19, head="IBMPlexMono-Bold.ttf", ink=(25, 25, 25), paper=(255, 255, 255)),
    "typed": dict(body="SpecialElite-Regular.ttf", size=23, head="CourierPrime-Bold.ttf", ink=(40, 38, 52), paper=(246, 240, 225)),
    "scan": dict(body="CourierPrime-Regular.ttf", size=22, head="CourierPrime-Bold.ttf", ink=(30, 30, 38), paper=(250, 248, 242)),
    "fax": dict(body="CourierPrime-Regular.ttf", size=23, head="CourierPrime-Bold.ttf", ink=(20, 20, 20), paper=(238, 238, 236)),
    "handwritten": dict(body="Caveat.ttf", size=34, head="Caveat.ttf", ink=(24, 46, 120), paper=(244, 236, 214)),
}


def _wrap(draw: ImageDraw.ImageDraw, text: str, fnt, max_w: int) -> list[str]:
    words = text.split()
    if not words:
        return [""]
    lines, cur = [], words[0]
    for w in words[1:]:
        trial = cur + " " + w
        if draw.textlength(trial, font=fnt) <= max_w:
            cur = trial
        else:
            lines.append(cur)
            cur = w
    lines.append(cur)
    return lines


class PageWriter:
    def __init__(self, form: str, rng: random.Random, aged: float):
        self.form = form
        self.rng = rng
        self.style = STYLES[form]
        self.aged = aged  # 0 = new, 1 = 30 years old
        self.pages: list[Page] = []
        self._new_page()

    # -- page management -----------------------------------------------------
    def _new_page(self):
        paper = self.style["paper"]
        if self.form in ("typed", "scan", "handwritten"):
            k = self.aged * 18
            paper = tuple(max(0, int(c - k * f)) for c, f in zip(paper, (0.3, 0.6, 1.4)))
        img = Image.new("RGB", (W, H), paper)
        self.page = Page(img)
        self.draw = ImageDraw.Draw(img)
        self.pages.append(self.page)
        self.y = MARGIN
        if self.form == "handwritten":
            for yy in range(150, H - 60, 46):
                self.draw.line([(50, yy), (W - 40, yy)], fill=(170, 190, 215), width=1)
            self.draw.line([(110, 40), (110, H - 30)], fill=(215, 150, 150), width=2)
        if self.form in ("typed", "scan", "fax") and self.rng.random() < 0.6:
            for hy in (H * 0.3, H * 0.7):
                self.draw.ellipse([22, hy - 13, 48, hy + 13], fill=(205, 200, 190))

    def ensure(self, needed: int):
        if self.y + needed > H - MARGIN:
            self._new_page()

    # -- writing ---------------------------------------------------------------
    def text(self, txt: str, *, size: int | None = None, bold=False, kind="body", indent=0, gap=6,
             font_name: str | None = None, color=None, x: int | None = None, record=True):
        st = self.style
        size = size or st["size"]
        fname = font_name or (st["head"] if bold else st["body"])
        fnt = font(fname, size)
        max_w = W - 2 * MARGIN - indent
        for ln in _wrap(self.draw, txt, fnt, max_w):
            lh = int(size * (1.25 if self.form != "handwritten" else 1.05))
            self.ensure(lh)
            xx = (x if x is not None else MARGIN) + indent
            if self.form == "handwritten":
                xx += self.rng.randint(-4, 6)
            ink = color or st["ink"]
            if self.form in ("typed",) and self.aged > 0.3:
                ink = tuple(min(255, c + self.rng.randint(0, 40)) for c in ink)
            self.draw.text((xx, self.y), ln, font=fnt, fill=ink)
            wpx = int(self.draw.textlength(ln, font=fnt))
            if record and ln.strip():
                self.page.lines.append(Line(ln, (xx, self.y, xx + wpx, self.y + lh), kind))
            self.y += lh
        self.y += gap

    def rule(self, gap=10, color=(150, 150, 150)):
        self.ensure(gap * 2)
        self.draw.line([(MARGIN, self.y), (W - MARGIN, self.y)], fill=color, width=2)
        self.y += gap

    def space(self, px: int):
        self.y += px


# ----------------------------------------------------------------------------
# headers
# ----------------------------------------------------------------------------
def letterhead(pw: PageWriter, org: str, sub: str | None, ref: str | None, date_str: str | None, title: str | None):
    if pw.form == "handwritten":
        if date_str:
            pw.text(date_str, size=30, kind="meta")
        return
    head_font = "LibreBaskerville.ttf" if pw.form in ("digital", "scan") else None
    pw.text(org, size=27 if pw.form != "fax" else 24, bold=True, kind="header", font_name=head_font)
    if sub:
        pw.text(sub, size=14 if pw.form == "digital" else 15, kind="header", gap=2)
    pw.rule(gap=14, color=(120, 120, 120) if pw.form != "digital" else (196, 116, 52))
    meta = []
    if ref:
        meta.append(f"Ref. {ref}")
    if date_str:
        meta.append(date_str)
    if meta:
        pw.text("    ".join(meta), size=17, kind="meta", gap=8)
    if title:
        pw.text(title, size=23, bold=True, kind="header", gap=12)


def fax_banner(pw: PageWriter, sender_no: str, date_str: str, pages: int = 1):
    banner = f"FROM: {sender_no}     {date_str}     P.01/{pages:02d}"
    pw.draw.rectangle([0, 0, W, 34], fill=(225, 225, 222))
    pw.draw.text((30, 8), banner, font=font("IBMPlexMono-Regular.ttf", 16), fill=(30, 30, 30))
    pw.page.lines.append(Line(banner, (30, 8, 600, 30), "meta"))
    pw.y = max(pw.y, 60)


# ----------------------------------------------------------------------------
# decorations / degradation
# ----------------------------------------------------------------------------
def stamp(page: Page, rng: random.Random, text: str, color=(176, 36, 48)):
    sw, sh = 330, 92
    layer = Image.new("RGBA", (sw, sh), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    d.rounded_rectangle([3, 3, sw - 3, sh - 3], radius=10, outline=color + (200,), width=4)
    lines = text.split("\n")
    fy = 12 if len(lines) > 1 else 28
    for i, t in enumerate(lines):
        f = font("CourierPrime-Bold.ttf", 26 if i == 0 else 20)
        tw = d.textlength(t, font=f)
        d.text(((sw - tw) / 2, fy + i * 32), t, font=f, fill=color + (190,))
    layer = layer.rotate(rng.uniform(-14, 14), expand=True, resample=Image.BICUBIC)
    x = rng.randint(max(40, W - 120 - layer.width - 200), W - 60 - layer.width)
    y = rng.randint(H - 430, H - 130 - layer.height)
    page.image.paste(layer, (x, y), layer)
    page.lines.append(Line("[stamp] " + text.replace("\n", " "), (x, y, x + layer.width, y + layer.height), "stamp"))


def margin_note(page: Page, rng: random.Random, text: str, ink=(30, 60, 150)):
    f = font("ReenieBeanie.ttf", 36)
    d = ImageDraw.Draw(page.image)
    x = rng.randint(MARGIN + 20, MARGIN + 160)
    y = rng.randint(int(H * 0.72), int(H * 0.8))
    wrapped = textwrap.wrap(text, 34)
    for i, t in enumerate(wrapped):
        d.text((x, y + i * 38), t, font=f, fill=ink)
    page.lines.append(Line("[handwritten note] " + text, (x, y, x + 560, y + 38 * len(wrapped)), "handwritten"))


def signature(page: Page, rng: random.Random, name: str, y: int | None = None):
    d = ImageDraw.Draw(page.image)
    f = font("HomemadeApple-Regular.ttf", 30)
    x = rng.randint(W - 420, W - 330)
    y = y or rng.randint(H - 260, H - 200)
    d.text((x, y), name, font=f, fill=(20, 30, 90))


def coffee_ring(img: Image.Image, rng: random.Random):
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    cx, cy, r = rng.randint(200, W - 200), rng.randint(200, H - 200), rng.randint(70, 120)
    for k in range(6):
        d.ellipse([cx - r - k, cy - r - k, cx + r + k, cy + r + k], outline=(120, 80, 30, 26 - k * 3), width=3)
    d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(150, 100, 40, 14))
    img.paste(Image.alpha_composite(img.convert("RGBA"), layer).convert("RGB"))


def degrade(page: Page, rng: random.Random, form: str, aged: float) -> Image.Image:
    img = page.image
    if form in ("digital", "email"):
        return img
    if rng.random() < 0.25 + 0.4 * aged:
        coffee_ring(img, rng)
    # speckle noise
    d = ImageDraw.Draw(img)
    n = int(900 + 2600 * aged) if form != "fax" else 5200
    for _ in range(n):
        x, y = rng.randrange(W), rng.randrange(H)
        g = rng.randint(90, 180)
        d.point((x, y), fill=(g, g, g))
    if form == "fax":
        img = img.convert("L").point(lambda p: 255 if p > 150 else 0).convert("RGB")
        img = img.resize((W // 2, H // 2), Image.NEAREST).resize((W, H), Image.NEAREST)
    if form in ("typed", "scan") and aged > 0.4:
        img = img.filter(ImageFilter.GaussianBlur(0.6))
    angle = rng.uniform(-1.3, 1.3)
    bg = img.getpixel((5, H // 2))
    img = img.rotate(angle, resample=Image.BICUBIC, fillcolor=bg)
    # scanner edge shadow
    d = ImageDraw.Draw(img)
    for i in range(10):
        shade = 70 + i * 16
        d.line([(i, 0), (i, H)], fill=(shade, shade, shade))
    return img


def aged_factor(year: int) -> float:
    return max(0.0, min(1.0, (2026 - year) / 32))


def human_date(iso: str, lang: str, form: str) -> str:
    y, m, d = (int(p) for p in iso.split("-"))
    it_months = ["gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno", "luglio", "agosto",
                 "settembre", "ottobre", "novembre", "dicembre"]
    en_months = ["January", "February", "March", "April", "May", "June", "July", "August", "September",
                 "October", "November", "December"]
    if form == "handwritten":
        return f"{d}/{m}/{str(y)[2:]}"
    if form == "fax":
        return f"{d:02d}-{m:02d}-{str(y)[2:]}"
    if lang == "it":
        return f"Borgo Valdorso, {d} {it_months[m - 1]} {y}"
    if form == "email":
        return f"{d} {en_months[m - 1][:3]} {y}"
    return f"{d} {en_months[m - 1]} {y}"


def to_rgb_webp_bytes(img: Image.Image, quality: int = 62) -> bytes:
    import io

    buf = io.BytesIO()
    img.save(buf, format="WEBP", quality=quality, method=5)
    return buf.getvalue()


__all__ = [
    "PageWriter", "Page", "Line", "letterhead", "fax_banner", "stamp", "margin_note", "signature",
    "degrade", "aged_factor", "human_date", "to_rgb_webp_bytes", "W", "H", "math",
]
