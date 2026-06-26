from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from PIL import ImageFont
from typing import cast
from .models import Metrics, FontPack


PROJECT_ROOT = Path(__file__).resolve().parent.parent
FONTS_DIR = PROJECT_ROOT / 'fonts'


def _load_font(path: Path, size: int) -> ImageFont.FreeTypeFont:
    try:
        return ImageFont.truetype(str(path), size=size)
    except OSError:
        pass
    return cast(ImageFont.FreeTypeFont, ImageFont.load_default())


def _line_height(font: ImageFont.FreeTypeFont) -> int:
    ascent, descent = font.getmetrics()
    total_height = ascent + abs(descent)
    return int(total_height)


FONT_PATH = FONTS_DIR / 'InterDisplay-Regular.ttf'
LIGHT_FONT_PATH = FONTS_DIR / 'InterDisplay-Light.ttf'

TITLE_FONT_SIZE = 40
SUBTITLE_FONT_SIZE = 36
BODY_FONT_SIZE = 32
SMALL_FONT_SIZE = 28

FONTS = FontPack(
    title=_load_font(FONT_PATH, TITLE_FONT_SIZE),
    subtitle=_load_font(LIGHT_FONT_PATH, SUBTITLE_FONT_SIZE),
    roles=_load_font(LIGHT_FONT_PATH, BODY_FONT_SIZE),
    names=_load_font(FONT_PATH, BODY_FONT_SIZE)
)

FONTS_SMALL = FontPack(
    title=_load_font(FONT_PATH, TITLE_FONT_SIZE),
    subtitle=_load_font(LIGHT_FONT_PATH, SUBTITLE_FONT_SIZE),
    roles=_load_font(LIGHT_FONT_PATH, SMALL_FONT_SIZE),
    names=_load_font(FONT_PATH, SMALL_FONT_SIZE)
)

METRICS = Metrics(
    card_w=1920,
    card_h=1080,

    margin_l=100,
    margin_r=100,
    margin_t=100,
    margin_b=100,

    title_line_h=_line_height(FONTS.title),
    subtitle_line_h=_line_height(FONTS.subtitle),
    title_gap_after=20,

    line_h=_line_height(FONTS.names),

    max_cols=3,
    
    col_centers={
        1: [0.50],
        2: [0.3, 0.7],
        3: [0.15, 0.50, 0.85]
    },

    col_width_frac={
        1: 0.70,
        2: 0.44,
        3: 0.27,
    },

    role_col_w=260,
    role_name_gap=24
)

METRICS_SMALL = replace(METRICS, line_h=_line_height(FONTS_SMALL.names))
