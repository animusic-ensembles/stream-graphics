from .parser import parse_cards_csv
from .layout import layout_card_with_fallback
from .renderer import render_card, save_card
import shutil
from pathlib import Path

output_folder = Path(__file__).parent.parent / 'output' / 'credits'

def clear_old_cards() -> None:
    shutil.rmtree(output_folder, ignore_errors=True)
    output_folder.mkdir(parents=True, exist_ok=True)
    print('Credits output folder cleared.')

def generate(filepath: Path) -> list[tuple[str, str]]:
    clear_old_cards()

    cards = parse_cards_csv(filepath)
    setlist = []

    for card in cards:
        plan = layout_card_with_fallback(card)
        img = render_card(plan)
        if card.subtitle:
            setlist.append((card.title, card.subtitle))
        save_card(img, f'{output_folder}/{card.card_id}.png')
    
    print('All credits generated successfully.')

    return setlist
