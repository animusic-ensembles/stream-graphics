import csv, re
from dataclasses import dataclass
from pathlib import Path
from typing import List, Dict, Optional, Sequence

from .models import CardData, RoleCredit

# ============================================================
# Error class
# ============================================================


@dataclass(slots=True)
class ParseError(Exception):
    message: str
    row_num: int
    row: Sequence[str]

    def __str__(self) -> str:
        return f'ParseError(row {self.row_num}): {self.message} | {list(self.row)}'


# ============================================================
# Helper functions
# ============================================================


def _clean(cell: str) -> str:
    """
    Strip whitespace
    """
    return (cell or '').strip()


def _slugify(text: str) -> str:
    """
    Deterministic slug

    - lowercase
    - non-alphabet/number to underscore
    - collapse underscores
    """
    _slug_re = re.compile(r'[^a-z0-9]+')
    s = text.strip().lower()
    s = _slug_re.sub('_', s)
    s = re.sub(r'_+', '_' , s).strip('_')
    return s or 'untitled'


def _make_card_id(card_index: int, title: str) -> str:
    return f'{card_index:02d}_{_slugify(title)}'


def _is_blank_row(c0: str, c1: str, c2: str) -> bool:
    return c0 == '' and c1 == '' and c2 == ''


# ============================================================
# Parser
# ============================================================


def parse_cards_csv(path: str | Path) -> List[CardData]:
    """
    Parse a credits CSV file into a list of CardData
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(path)
    
    cards: list[CardData] = []

    # Global numbering for card_id
    card_index: int = 0

    # Current card state
    title: Optional[str] = None
    subtitle: Optional[str] = None
    awaiting_subtitle_or_titleonly: bool = False

    # Current card data accumulation
    current_role: Optional[str] = None
    role_to_names: Dict[str, List[str]] = {}
    role_order: List[str] = []
    
    list_items: List[str] = []
    mode: Optional[str] = None  # None | 'credits' | 'list'
    
    def reset_state() -> None:
        nonlocal title, subtitle, awaiting_subtitle_or_titleonly
        nonlocal current_role, role_to_names, role_order, list_items, mode
        title = None
        subtitle = None
        awaiting_subtitle_or_titleonly = False
        current_role = None
        role_to_names = {}
        role_order = []
        list_items = []
        mode = None

    def flush_title_only() -> None:
        """
        Flush a title-only card
        """
        nonlocal card_index
        assert title is not None

        cards.append(
            CardData(
                card_id=_make_card_id(card_index, title),
                title=title,
                subtitle=subtitle,
                card_type='title_only',
                roles=[],
                list_items=[]
            )
        )
        card_index += 1
        reset_state()
    
    def flush_current() -> None:
        """
        Flush the current card
        """
        nonlocal card_index
        if title is None:
            return

        # Decide card-type
        if mode == 'list':
            card_type = 'list'
            role_list: List[RoleCredit] = []
            li = list_items[:]
        else:
            card_type = 'credits'
            li = []
            role_list = []

            for role in role_order:
                names = role_to_names.get(role, [])
                if not names:
                    continue
                role_list.append(RoleCredit(role=role, names=names))

        cards.append(
            CardData(
                card_id=_make_card_id(card_index, title),
                title=title,
                subtitle=subtitle,
                card_type=card_type,    # 'credits' | 'list'
                roles=role_list,
                list_items=li
            )
        )
        card_index += 1
        reset_state()
    
    with path.open(encoding='utf-8') as file:
        reader = csv.reader(file)
        for _ in range(3):
            next(reader, None)
        for i, row in enumerate(reader, start=4):
            c0, c1, c2 = _clean(row[0]), _clean(row[1]), _clean(row[2])

            # Check for card terminator
            if _is_blank_row(c0, c1, c2):
                if title is not None and awaiting_subtitle_or_titleonly:
                    # Blank row directly after title
                    flush_title_only()
                else:
                    # End of current card
                    flush_current()
                continue
            
            # If card doesn't start with title
            if title is None:
                if c0 == '':
                    raise ParseError('Expected title in column 1', i, row)
                title = c0
                awaiting_subtitle_or_titleonly = True
                continue
            
            # Check for subtitle
            if awaiting_subtitle_or_titleonly:
                awaiting_subtitle_or_titleonly = False
                if c0 != '' and c1 == '' and c2 == '':
                    subtitle = c0
                    continue
        
            # Determine row shape (list vs credits)
            if c1 != '' and c2 == '':
                if mode is None:
                    mode = 'list'
                elif mode != 'list':
                    raise ParseError('Mixed list-only rows with role/name rows in same card', i, row)
                list_items.append(c1)
                continue
            
            if c2 != '':
                if mode is None:
                    mode = 'credits'
                elif mode != 'credits':
                    raise ParseError('Mixed role/name rows with list-only rows in same card', i, row)
            
                if c1 != '':
                    current_role = c1
                    if current_role not in role_to_names:
                        role_to_names[current_role] = []
                        role_order.append(current_role)
                    role_to_names[current_role].append(c2)
                else:
                    if current_role is None:
                        raise ParseError('Name encountered without role', i, row)
                    role_to_names[current_role].append(c2)
                continue

            # Non-blank row that doesn't match known patterns
            raise ParseError('Unrecognized row shape', i, row)
        
    # If file terminates without trailing blank row
    if title is not None:
        if awaiting_subtitle_or_titleonly:
            flush_title_only()
        else:
            flush_current()
    
    return cards
