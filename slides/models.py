from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class Crop:
    left: float
    top: float
    right: float
    bottom: float


@dataclass(slots=True)
class Placement:
    x: int
    y: int
    width: int
    height: int


@dataclass(slots=True)
class ShapeInventory:
    shape_id: int
    name: str
    shape_type: str
    z_index: int
    left: int
    top: int
    width: int
    height: int
    rotation: float
    crop: Crop | None
    grouped: bool
    placement: Placement
    children: list['ShapeInventory'] = field(default_factory=list)


@dataclass(slots=True)
class SlideLayer:
    type: str
    shape_id: int
    z_index: int
    source_file: str
    placement: Placement
    rotation: float
    flip_h: bool = False
    flip_v: bool = False
    full_canvas_file: str | None = None


@dataclass(slots=True)
class SlideInventory:
    slide_number: int
    slide_width: int
    slide_height: int
    output_width: int
    output_height: int
    scale_warning: str | None
    shapes: list[ShapeInventory]
    layers: list[SlideLayer] = field(default_factory=list)
