from __future__ import annotations

from pathlib import Path
from typing import Iterable

from pptx import Presentation
from pptx.enum.shapes import MSO_SHAPE_TYPE
from pptx.shapes.base import BaseShape

from .models import Crop, Placement, ShapeInventory, SlideInventory


OUTPUT_WIDTH = 1920
OUTPUT_HEIGHT = 1080


def _shape_type_name(shape: BaseShape) -> str:
    try:
        return MSO_SHAPE_TYPE(shape.shape_type).name
    except ValueError:
        return str(shape.shape_type)


def _crop(shape: BaseShape) -> Crop | None:
    if not hasattr(shape, 'crop_left'):
        return None

    return Crop(
        left=float(getattr(shape, 'crop_left', 0.0)),
        top=float(getattr(shape, 'crop_top', 0.0)),
        right=float(getattr(shape, 'crop_right', 0.0)),
        bottom=float(getattr(shape, 'crop_bottom', 0.0)),
    )


def _placement(left: int, top: int, width: int, height: int, slide_width: int, slide_height: int) -> Placement:
    return Placement(
        x=round(left / slide_width * OUTPUT_WIDTH),
        y=round(top / slide_height * OUTPUT_HEIGHT),
        width=round(width / slide_width * OUTPUT_WIDTH),
        height=round(height / slide_height * OUTPUT_HEIGHT),
    )


def _absolute_inventory(
        shape: BaseShape,
        z_index: int,
        slide_width: int,
        slide_height: int,
        parent_left: int = 0,
        parent_top: int = 0,
        grouped: bool = False
) -> ShapeInventory:
    left = parent_left + int(shape.left)
    top = parent_top + int(shape.top)
    width = int(shape.width)
    height = int(shape.height)

    children: list[ShapeInventory] = []
    if shape.shape_type == MSO_SHAPE_TYPE.GROUP:
        for child_z_index, child in enumerate(shape.shapes, start=1):
            children.append(
                _absolute_inventory(
                    child,
                    child_z_index,
                    slide_width,
                    slide_height,
                    parent_left=left,
                    parent_top=top,
                    grouped=True,
                )
            )

    return ShapeInventory(
        shape_id=int(shape.shape_id),
        name=str(shape.name),
        shape_type=_shape_type_name(shape),
        z_index=z_index,
        left=left,
        top=top,
        width=width,
        height=height,
        rotation=float(shape.rotation or 0.0),
        crop=_crop(shape),
        grouped=grouped,
        placement=_placement(left, top, width, height, slide_width, slide_height),
        children=children,
    )


def _slide_inventory(slide_number: int, shapes: Iterable[BaseShape], slide_width: int, slide_height: int) -> SlideInventory:
    scale_warning = None
    if round(slide_width / slide_height, 4) != round(OUTPUT_WIDTH / OUTPUT_HEIGHT, 4):
        scale_warning = 'Presentation is not 16:9; placements are scaled to 1920x1080 output.'

    return SlideInventory(
        slide_number=slide_number,
        slide_width=slide_width,
        slide_height=slide_height,
        output_width=OUTPUT_WIDTH,
        output_height=OUTPUT_HEIGHT,
        scale_warning=scale_warning,
        shapes=[
            _absolute_inventory(shape, z_index, slide_width, slide_height)
            for z_index, shape in enumerate(shapes, start=1)
        ],
    )


def inventory_presentation(path: str | Path) -> list[SlideInventory]:
    presentation = Presentation(path)
    slide_width = int(presentation.slide_width)
    slide_height = int(presentation.slide_height)

    return [
        _slide_inventory(index, slide.shapes, slide_width, slide_height)
        for index, slide in enumerate(presentation.slides, start=1)
    ]
