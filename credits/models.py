from dataclasses import dataclass
from typing import List, Dict, Optional, Literal
from PIL import ImageFont


@dataclass(slots=True)
class RoleCredit:
    """
    Represents a single role in the credits (e.g. Violin, Trumpet, Conductor)
    and the names associated with it.
    """
    role: str    
    names: List[str]


CardType = Literal['credits', 'list', 'title_only']


@dataclass(slots=True)
class CardData:
    """
    The credit card to render.
    """
    card_id: str
    title: str
    card_type: CardType

    roles: List[RoleCredit]

    list_items: List[str]

    subtitle: Optional[str] = None


@dataclass(slots=True)
class Metrics:
    """
    Formatting variables.
    """
    # Card dimensions (px)
    card_w: int
    card_h: int

    # Margins (px)
    margin_l: int
    margin_r: int
    margin_t: int
    margin_b: int

    # Title/subtitle region
    title_line_h: int
    subtitle_line_h: int
    title_gap_after: int

    # Body typography
    line_h: int

    # Columns
    max_cols: int

    col_centers: Dict[int, List[float]]
    col_width_frac: Dict[int, float]  

    # Credits layout
    role_col_w: int
    role_name_gap: int


@dataclass
class FontPack:
    title: ImageFont.FreeTypeFont
    subtitle: ImageFont.FreeTypeFont
    roles: ImageFont.FreeTypeFont
    names: ImageFont.FreeTypeFont


@dataclass(slots=True)
class CreditLine:
    """
    A single credit line
    Entirely semantic
    """
    role_text: str
    name_text: str


@dataclass(slots=True)
class ColumnLayout:
    """
    Layout for a single column of credits
    """
    center_x: int
    role_x: int
    name_x: int
    y: int
    width: int
    blocks: List[List[CreditLine]]
    total_lines: int


@dataclass(slots=True)
class CardLayoutPlan:
    """
    Complete layout plan for a card
    """
    card_id: str
    card_type: str
    title: str
    subtitle: Optional[str]

    card_w: int
    card_h: int
    content_left: int
    content_right: int
    content_top: int
    content_bottom: int

    title_y: int
    subtitle_y: Optional[int]
    body_y: int
    body_bottom: int

    columns: List[ColumnLayout]
    list_items: List[str]

    metrics: Metrics
    fonts: FontPack
