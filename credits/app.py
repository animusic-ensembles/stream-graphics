from .parser import parse_cards_csv
from .layout import layout_card_with_fallback
from .renderer import render_card, save_card
import shutil
from pathlib import Path
from typing import Callable

output_folder = Path(__file__).parent.parent / 'output' / 'credits'

def clear_old_cards() -> None:
    shutil.rmtree(output_folder, ignore_errors=True)
    output_folder.mkdir(parents=True, exist_ok=True)
    print('Credits output folder cleared.')

def generate(filepath: Path, progress_callback: Callable[[int, int], None] | None = None) -> list[tuple[str, str]]:
    clear_old_cards()

    cards = parse_cards_csv(filepath)
    setlist = []
    total_cards = len(cards)

    for index, card in enumerate(cards, start=1):
        plan = layout_card_with_fallback(card)
        img = render_card(plan)
        if card.subtitle:
            setlist.append((card.title, card.subtitle))
        save_card(img, f'{output_folder}/{card.card_id}.png')
        if progress_callback:
            progress_callback(index, total_cards)
    
    print('All credits generated successfully.')

    return setlist
