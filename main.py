from pathlib import Path
import argparse
import importlib
import os
import platform
import subprocess
import sys
from typing import Callable

import credits.app as Credits
import lower_thirds.app as LowerThirds


PROJECT_ROOT = Path(__file__).resolve().parent
OUTPUT_FOLDER = PROJECT_ROOT / 'output'
BAR_WIDTH = 36
BAR_FILLED = '\u2588'
BAR_EMPTY = '\u2591'
ASCII_BAR_FILLED = '='
ASCII_BAR_EMPTY = '-'
COLOR_RESET = '\033[0m'
COLOR_DIM = '\033[2m'
COLOR_CYAN = '\033[36m'
COLOR_GREEN = '\033[32m'
COLOR_YELLOW = '\033[33m'

TASK_CREDITS = 'credits'
TASK_LOWER_THIRDS = 'lower_thirds'
TASKS = [
    (TASK_CREDITS, 'Credits'),
    (TASK_LOWER_THIRDS, 'Lower thirds'),
]


def _clean_dropped_path(value: str) -> Path:
    return Path(value.strip().strip('"').strip("'")).expanduser()


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='Generate stream graphics from a credits CSV.')
    parser.add_argument('csv_path', nargs='?', help='Path to the credits CSV file.')
    parser.add_argument('--all', action='store_true', help='Generate credits and lower thirds.')
    parser.add_argument('--credits', action='store_true', help='Generate credit card PNGs only.')
    parser.add_argument(
        '--lowerthirds',
        '--lower-thirds',
        dest='lower_thirds',
        action='store_true',
        help='Generate lower-third videos only.'
    )
    return parser.parse_args()


def _get_csv_path(args: argparse.Namespace) -> Path:
    if args.csv_path:
        return _clean_dropped_path(args.csv_path)

    raw_path = input('Drag your CSV file here, then press Enter: ')
    return _clean_dropped_path(raw_path)


def _open_folder(path: Path) -> None:
    path = path.resolve()
    system = platform.system()

    try:
        if system == 'Windows':
            subprocess.run(['explorer', str(path)], check=False)
        elif system == 'Darwin':
            subprocess.run(['open', str(path)], check=False)
        else:
            subprocess.run(['xdg-open', str(path)], check=False)
    except OSError as error:
        print(f'Could not open output folder automatically: {error}')
        print(f'Open it manually here: {path}')


def _make_progress_bar(label: str) -> Callable[[int, int], None]:
    filled_char = BAR_FILLED if _supports_unicode() else ASCII_BAR_FILLED
    empty_char = BAR_EMPTY if _supports_unicode() else ASCII_BAR_EMPTY

    def update(current: int, total: int) -> None:
        percent = 100 if total == 0 else round((current / total) * 100)
        filled = BAR_WIDTH if total == 0 else round((current / total) * BAR_WIDTH)
        bar = filled_char * filled + empty_char * (BAR_WIDTH - filled)
        end = '\n' if current >= total else ''
        if _supports_color():
            label_text = f'{COLOR_CYAN}{label:<13}{COLOR_RESET}'
            bar_text = f'{COLOR_GREEN}{filled_char * filled}{COLOR_DIM}{empty_char * (BAR_WIDTH - filled)}{COLOR_RESET}'
            percent_text = f'{COLOR_YELLOW}{percent:3d}%{COLOR_RESET}'
            print(f'\r{label_text} {bar_text} {percent_text}', end=end, flush=True)
        else:
            print(f'\r{label:<13} {bar} {percent:3d}%', end=end, flush=True)

    return update


def _supports_unicode() -> bool:
    encoding = sys.stdout.encoding or ''
    return encoding.lower().startswith('utf')


def _supports_color() -> bool:
    if os.environ.get('NO_COLOR'):
        return False
    if os.environ.get('TERM') == 'dumb':
        return False
    return sys.stdout.isatty()


def _color(text: str, color: str) -> str:
    if not _supports_color():
        return text
    return f'{color}{text}{COLOR_RESET}'


def _clear_terminal() -> None:
    os.system('cls' if platform.system() == 'Windows' else 'clear')


def _read_menu_key() -> str:
    if platform.system() == 'Windows':
        msvcrt = importlib.import_module('msvcrt')

        key = msvcrt.getwch()
        if key in ('\x00', '\xe0'):
            key = msvcrt.getwch()
            if key == 'H':
                return 'up'
            if key == 'P':
                return 'down'
            return ''
        if key == '\r':
            return 'enter'
        if key == ' ':
            return 'space'
        return key.lower()

    termios = importlib.import_module('termios')
    tty = importlib.import_module('tty')

    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        key = sys.stdin.read(1)
        if key == '\x1b':
            sequence = sys.stdin.read(2)
            if sequence == '[A':
                return 'up'
            if sequence == '[B':
                return 'down'
            return ''
        if key in ('\r', '\n'):
            return 'enter'
        if key == ' ':
            return 'space'
        return key.lower()
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)


def _choose_tasks_from_menu() -> set[str]:
    cursor = 0
    selected = {TASK_CREDITS, TASK_LOWER_THIRDS}
    message = ''
    show_help = False

    while True:
        _clear_terminal()
        selected_symbol = '\u25cf' if _supports_unicode() else 'x'
        unselected_symbol = '\u25cb' if _supports_unicode() else '-'
        pointer_symbol = '\u203a' if _supports_unicode() else '>'
        pointer_empty = ' '
        up_down = '\u2191/\u2193' if _supports_unicode() else 'up/down'

        print(_color('Select what to generate', COLOR_CYAN))
        print()
        for index, (task_id, label) in enumerate(TASKS):
            pointer = pointer_symbol if index == cursor else pointer_empty
            checkbox = selected_symbol if task_id in selected else unselected_symbol
            pointer_text = _color(pointer, COLOR_YELLOW) if index == cursor else pointer
            checkbox_color = COLOR_GREEN if task_id in selected else COLOR_DIM
            checkbox_text = _color(checkbox, checkbox_color)
            label_text = _color(label, COLOR_GREEN) if task_id in selected else label
            print(f'{pointer_text} {checkbox_text} {label_text}')
        print()
        print(_color(f'{up_down} move', COLOR_DIM), end='  ')
        print(_color('[space]', COLOR_YELLOW), 'toggle', end='  ')
        print(_color('[a]', COLOR_YELLOW), 'all', end='  ')
        print(_color('[n]', COLOR_YELLOW), 'none', end='  ')
        print(_color('[?]', COLOR_YELLOW), 'help', end='  ')
        print(_color('[q]', COLOR_YELLOW), 'cancel', end='  ')
        print(_color('[enter]', COLOR_YELLOW), 'generate')
        if show_help:
            print()
            print(_color('Help', COLOR_CYAN))
            print(_color(f'  {up_down}     Move between options', COLOR_DIM))
            print(_color('  [space] Toggle the selected option', COLOR_DIM))
            print(_color('  [a]     Select all options', COLOR_DIM))
            print(_color('  [n]     Clear all options', COLOR_DIM))
            print(_color('  [q]     Cancel without generating', COLOR_DIM))
            print(_color('  [enter] Generate the selected outputs', COLOR_DIM))
        if message:
            print(f'\n{message}')

        key = _read_menu_key()
        message = ''

        if key == 'up':
            cursor = (cursor - 1) % len(TASKS)
        elif key == 'down':
            cursor = (cursor + 1) % len(TASKS)
        elif key == 'space':
            task_id = TASKS[cursor][0]
            if task_id in selected:
                selected.remove(task_id)
            else:
                selected.add(task_id)
        elif key == 'a':
            selected = {task_id for task_id, _ in TASKS}
        elif key == 'n':
            selected = set()
        elif key == '?':
            show_help = not show_help
        elif key == 'q':
            raise SystemExit(0)
        elif key == 'enter':
            if selected:
                _clear_terminal()
                return selected
            message = 'Select at least one option.'


def _get_selected_tasks(args: argparse.Namespace) -> set[str]:
    has_flag = args.all or args.credits or args.lower_thirds
    if not has_flag:
        return _choose_tasks_from_menu()

    if args.all:
        return {TASK_CREDITS, TASK_LOWER_THIRDS}

    selected: set[str] = set()
    if args.credits:
        selected.add(TASK_CREDITS)
    if args.lower_thirds:
        selected.add(TASK_LOWER_THIRDS)
    return selected


def generate_selected(filename: Path, selected_tasks: set[str]) -> None:
    if not filename.exists():
        raise FileNotFoundError(f'CSV file not found: {filename}')

    print(f'Using CSV: {filename}')

    if TASK_CREDITS in selected_tasks:
        setlist = Credits.generate(filename, progress_callback=_make_progress_bar('Credits'))
    else:
        setlist = Credits.generate(filename, render_cards=False)

    if TASK_LOWER_THIRDS in selected_tasks:
        LowerThirds.generate(setlist, progress_callback=_make_progress_bar('Lower thirds'))

    _open_folder(OUTPUT_FOLDER)


def main() -> None:
    try:
        args = _parse_args()
        filename = _get_csv_path(args)
        selected_tasks = _get_selected_tasks(args)
        generate_selected(filename, selected_tasks)
    except Exception as error:
        print(f'Error: {error}')
        raise


if __name__ == '__main__':
    main()
