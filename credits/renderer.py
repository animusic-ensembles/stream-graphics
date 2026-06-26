from __future__ import annotations

from pathlib import Path
from typing import Tuple

from PIL import Image, ImageDraw

from .models import *


def render_card(plan: CardLayoutPlan) -> Image.Image:
    """
    Render a CardLayoutPlan to an image
    """
    img = Image.new("RGBA", (plan.card_w, plan.card_h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.fontmode = 'L'
    color = (255, 255, 255, 255)

    _draw_title_block(draw, plan, color)
    if plan.card_type == 'credits':
        _draw_credits(draw, plan, color)
    elif plan.card_type == 'list':
        _draw_list(draw, plan, color)
    elif plan.card_type == 'title_only':
        pass
    else:
        raise ValueError(f'Unknown card_type: {plan.card_type!r}')
    
    return img


def _draw_title_block(
        draw: ImageDraw.ImageDraw,
        plan: CardLayoutPlan,
        color: Tuple[int, int, int, int]
) -> None:
    """
    Draw the title and optional subtitle centered horizontally
    """
    center_x = plan.card_w // 2

    draw.text(
        (center_x, plan.title_y),
        plan.title,
        font=plan.fonts.title,
        fill=color,
        anchor='ma'
    )

    if plan.subtitle and plan.subtitle_y is not None:
        draw.text(
            (center_x, plan.subtitle_y),
            plan.subtitle,
            font=plan.fonts.subtitle,
            fill=color,
            anchor='ma'
        )


def _draw_list(
        draw: ImageDraw.ImageDraw,
        plan: CardLayoutPlan,
        color: Tuple[int, int, int, int]
) -> None:
    """
    Draw list in a single text column
    """
    body_font = plan.fonts.names
    baseline_offset, _ = body_font.getmetrics()

    for col in plan.columns:
        y = col.y + baseline_offset

        for block in col.blocks:
            for line in block:
                draw.text((col.center_x, y), line.name_text, font=body_font, fill=color, anchor='ms')
                y += plan.metrics.line_h


def _draw_credits(
        draw: ImageDraw.ImageDraw,
        plan: CardLayoutPlan,
        color: Tuple[int, int, int, int]
) -> None:
    """
    Draw credits in role/name subcolumns
    """
    role_font = plan.fonts.roles
    name_font = plan.fonts.names
    baseline_offset, _ = name_font.getmetrics()

    for col in plan.columns:
        y = col.y + baseline_offset

        for block in col.blocks:
            for line in block:
                if line.role_text:
                    draw.text((col.role_x, y), line.role_text, font=role_font, fill=color, anchor='rs')
                draw.text((col.name_x, y), line.name_text, font=name_font, fill=color, anchor='ls')

                y += plan.metrics.line_h


def save_card(img: Image.Image, out_path: str | Path) -> None:
    """
    Saves a rendered card image to a file
    """
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(out_path)
