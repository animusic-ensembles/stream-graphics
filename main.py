from pathlib import Path
import argparse
import contextlib
import importlib
import os
import platform
import queue
import re
import subprocess
import sys
import threading
import time
from typing import Callable, Iterator

import credits.app as Credits
import lower_thirds.app as LowerThirds


PROJECT_ROOT = Path(__file__).resolve().parent
OUTPUT_FOLDER = PROJECT_ROOT / 'output'
CREDITS_OUTPUT_FOLDER = OUTPUT_FOLDER / 'credits'
LOWER_THIRDS_OUTPUT_FOLDER = OUTPUT_FOLDER / 'lower_thirds'
BAR_WIDTH = 36
BOX_WIDTH = 78
LOG_LINES = 8
PROGRESS_PREFIX = '__PROGRESS__'

BAR_FILLED = '\u2588'
BAR_EMPTY = '\u2591'
ASCII_BAR_FILLED = '='
ASCII_BAR_EMPTY = '-'

COLOR_RESET = '\033[0m'
COLOR_DIM = '\033[2m'
COLOR_CYAN = '\033[36m'
COLOR_GREEN = '\033[32m'
COLOR_YELLOW = '\033[33m'
ANSI_RE = re.compile(r'\033\[[0-9;?]*[A-Za-z]')

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
    parser.add_argument('--worker', action='store_true', help=argparse.SUPPRESS)
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


def _output_folder_for_tasks(selected_tasks: set[str]) -> Path:
    if selected_tasks == {TASK_CREDITS}:
        return CREDITS_OUTPUT_FOLDER
    if selected_tasks == {TASK_LOWER_THIRDS}:
        return LOWER_THIRDS_OUTPUT_FOLDER
    return OUTPUT_FOLDER


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
    if not sys.stdout.isatty():
        return
    print('\033[2J\033[H', end='', flush=True)


def _move_cursor_home() -> None:
    if not sys.stdout.isatty():
        return
    print('\033[H', end='', flush=True)


def _hide_cursor() -> None:
    if sys.stdout.isatty():
        print('\033[?25l', end='', flush=True)


def _show_cursor() -> None:
    if sys.stdout.isatty():
        print('\033[?25h', end='', flush=True)


def _bar(current: int, total: int) -> tuple[str, int]:
    filled_char = BAR_FILLED if _supports_unicode() else ASCII_BAR_FILLED
    empty_char = BAR_EMPTY if _supports_unicode() else ASCII_BAR_EMPTY
    percent = 100 if total == 0 else round((current / total) * 100)
    filled = BAR_WIDTH if total == 0 else round((current / total) * BAR_WIDTH)
    bar = filled_char * filled + empty_char * (BAR_WIDTH - filled)
    return bar, percent


def _color_bar(bar: str, percent: int) -> str:
    if not _supports_color():
        return f'{bar} {percent:3d}%'

    filled_char = BAR_FILLED if _supports_unicode() else ASCII_BAR_FILLED
    filled_count = bar.count(filled_char)
    filled = bar[:filled_count]
    empty = bar[filled_count:]
    bar_text = f'{COLOR_GREEN}{filled}{COLOR_DIM}{empty}{COLOR_RESET}'
    percent_text = f'{COLOR_YELLOW}{percent:3d}%{COLOR_RESET}'
    return f'{bar_text} {percent_text}'


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
        if key == '\x1b':
            return 'esc'
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
            return 'esc'
        if key in ('\r', '\n'):
            return 'enter'
        if key == ' ':
            return 'space'
        return key.lower()
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)


def _poll_key() -> str | None:
    if platform.system() == 'Windows':
        msvcrt = importlib.import_module('msvcrt')
        if not msvcrt.kbhit():
            return None
        key = msvcrt.getwch()
        if key == '\x1b':
            return 'esc'
        return key.lower()

    select = importlib.import_module('select')
    readable, _, _ = select.select([sys.stdin], [], [], 0)
    if not readable:
        return None
    key = sys.stdin.read(1)
    if key == '\x1b':
        return 'esc'
    return key.lower()


@contextlib.contextmanager
def _raw_terminal() -> Iterator[None]:
    if platform.system() == 'Windows' or not sys.stdin.isatty():
        yield
        return

    termios = importlib.import_module('termios')
    tty = importlib.import_module('tty')
    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)
    try:
        tty.setcbreak(fd)
        yield
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
        up_down = '\u2191/\u2193' if _supports_unicode() else 'up/down'

        print(_color('Select what to generate', COLOR_CYAN))
        print()
        for index, (task_id, label) in enumerate(TASKS):
            pointer = pointer_symbol if index == cursor else ' '
            checkbox = selected_symbol if task_id in selected else unselected_symbol
            pointer_text = _color(pointer, COLOR_YELLOW) if index == cursor else pointer
            checkbox_color = COLOR_GREEN if task_id in selected else COLOR_DIM
            checkbox_text = _color(checkbox, checkbox_color)
            label_text = _color(label, COLOR_GREEN) if task_id in selected else label
            print(f'{pointer_text} {checkbox_text} {label_text}')
        print()
        print(_color(f'{up_down} move', COLOR_DIM), end='  ')
        print(_color('[space]', COLOR_YELLOW), 'select/deselect', end='  ')
        print(_color('[a]', COLOR_YELLOW), 'all', end='  ')
        print(_color('[n]', COLOR_YELLOW), 'none', end='  ')
        print(_color('[q]', COLOR_YELLOW), 'cancel', end='  ')
        print(_color('[enter]', COLOR_YELLOW), 'generate', end='  ')
        print(_color('[?]', COLOR_YELLOW), 'help')
        if show_help:
            print()
            print(_color('Help', COLOR_CYAN))
            print(_color(f'  {up_down}     Move between options', COLOR_DIM))
            print(_color('  [space] Select or deselect the focused option', COLOR_DIM))
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


def _worker_progress(label: str) -> Callable[[int, int], None]:
    def update(current: int, total: int) -> None:
        print(f'{PROGRESS_PREFIX}|{label}|{current}|{total}', flush=True)

    return update


def _run_worker_generation(filename: Path, selected_tasks: set[str]) -> None:
    if not filename.exists():
        raise FileNotFoundError(f'CSV file not found: {filename}')

    print(f'Using CSV: {filename}', flush=True)

    if TASK_CREDITS in selected_tasks:
        setlist = Credits.generate(filename, progress_callback=_worker_progress('Credits'))
    else:
        setlist = Credits.generate(filename, render_cards=False)

    if TASK_LOWER_THIRDS in selected_tasks:
        LowerThirds.generate(setlist, progress_callback=_worker_progress('Lower thirds'))


def _worker_args(filename: Path, selected_tasks: set[str]) -> list[str]:
    args = [sys.executable, str(Path(__file__).resolve()), str(filename), '--worker']
    if selected_tasks == {TASK_CREDITS, TASK_LOWER_THIRDS}:
        args.append('--all')
    else:
        if TASK_CREDITS in selected_tasks:
            args.append('--credits')
        if TASK_LOWER_THIRDS in selected_tasks:
            args.append('--lowerthirds')
    return args


def _reader_thread(stream, output: queue.Queue[str]) -> None:
    try:
        for line in stream:
            output.put(line.rstrip())
    finally:
        output.put(PROGRESS_PREFIX + '|__EOF__|0|0')


def _visible_len(text: str) -> int:
    return len(ANSI_RE.sub('', text))


def _fit_line(text: str, width: int) -> str:
    visible_len = _visible_len(text)
    if visible_len > width:
        suffix = '\u2026' if _supports_unicode() else '.'
        plain_text = ANSI_RE.sub('', text)
        return plain_text[:max(0, width - 1)] + suffix
    return text + ' ' * (width - visible_len)


def _box_line(text: str = '') -> str:
    inner_width = BOX_WIDTH - 4
    edge = '\u2551' if _supports_unicode() else '|'
    edge = _color(edge, COLOR_CYAN)
    return f'{edge} {_fit_line(text, inner_width)} {edge}'


def _render_run_screen(
        selected_tasks: set[str],
        progress: dict[str, tuple[int, int]],
        logs: list[str],
        status: str
) -> None:
    _move_cursor_home()
    top = '╔' + '═' * (BOX_WIDTH - 2) + '╗'
    mid = '╠' + '═' * (BOX_WIDTH - 2) + '╣'
    bottom = '╚' + '═' * (BOX_WIDTH - 2) + '╝'

    if not _supports_unicode():
        top = '+' + '=' * (BOX_WIDTH - 2) + '+'
        mid = '+' + '=' * (BOX_WIDTH - 2) + '+'
        bottom = '+' + '=' * (BOX_WIDTH - 2) + '+'

    print(_color(top, COLOR_CYAN))
    print(_box_line(_color('Generating Stream Graphics', COLOR_CYAN)))
    print(_box_line(status))
    print(_color(mid, COLOR_CYAN))

    for task_id, label in TASKS:
        if task_id not in selected_tasks:
            continue
        current, total = progress.get(label, (0, 0))
        if total:
            bar, percent = _bar(current, total)
            line = f'{label:<13} {_color_bar(bar, percent)}'
        else:
            line = f'{label:<13} waiting...'
        print(_box_line(line))

    print(_color(mid, COLOR_CYAN))
    recent_logs = logs[-LOG_LINES:]
    if not recent_logs:
        recent_logs = ['Waiting for renderer output...']

    for log in recent_logs:
        print(_box_line(log))

    for _ in range(LOG_LINES - len(recent_logs)):
        print(_box_line())
    print(_color(bottom, COLOR_CYAN))
    print()
    print(_color('[esc]', COLOR_YELLOW), 'cancel and return to menu', end='    ')
    print(_color('[q]', COLOR_YELLOW), 'quit')
    print('\033[J', end='', flush=True)


def _run_generation_controller(filename: Path, selected_tasks: set[str], return_to_menu: bool) -> str:
    output: queue.Queue[str] = queue.Queue()
    env = os.environ.copy()
    env['PYTHONUNBUFFERED'] = '1'
    process = subprocess.Popen(
        _worker_args(filename, selected_tasks),
        cwd=PROJECT_ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        env=env
    )
    assert process.stdout is not None
    thread = threading.Thread(target=_reader_thread, args=(process.stdout, output), daemon=True)
    thread.start()

    progress: dict[str, tuple[int, int]] = {}
    logs: list[str] = []
    status = 'Running...'
    dirty = True

    with _raw_terminal():
        _clear_terminal()
        _hide_cursor()
        try:
            while True:
                while True:
                    try:
                        line = output.get_nowait()
                    except queue.Empty:
                        break

                    if line.startswith(PROGRESS_PREFIX):
                        _, label, current, total = line.split('|', 3)
                        if label != '__EOF__':
                            progress[label] = (int(current), int(total))
                            dirty = True
                    elif line:
                        logs.append(line)
                        dirty = True

                key = _poll_key()
                if key == 'esc':
                    process.terminate()
                    try:
                        process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        process.kill()
                    return 'menu' if return_to_menu else 'cancelled'
                if key == 'q':
                    process.terminate()
                    try:
                        process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        process.kill()
                    raise SystemExit(0)

                return_code = process.poll()
                if return_code is not None:
                    while True:
                        try:
                            line = output.get_nowait()
                        except queue.Empty:
                            break
                        if line.startswith(PROGRESS_PREFIX):
                            _, label, current, total = line.split('|', 3)
                            if label != '__EOF__':
                                progress[label] = (int(current), int(total))
                        elif line:
                            logs.append(line)
                    status = 'Complete.' if return_code == 0 else f'Failed with exit code {return_code}.'
                _render_run_screen(selected_tasks, progress, logs, status)
                if return_code == 0:
                    _open_folder(_output_folder_for_tasks(selected_tasks))
                    return 'done'
                    raise SystemExit(return_code)

                if dirty:
                    _render_run_screen(selected_tasks, progress, logs, status)
                    dirty = False
                time.sleep(0.05)
        finally:
            _show_cursor()


def main() -> None:
    try:
        args = _parse_args()
        filename = _get_csv_path(args)
        selected_tasks = _get_selected_tasks(args)

        if args.worker:
            _run_worker_generation(filename, selected_tasks)
            return

        has_direct_flags = args.all or args.credits or args.lower_thirds
        while True:
            result = _run_generation_controller(filename, selected_tasks, return_to_menu=not has_direct_flags)
            if result != 'menu':
                return
            selected_tasks = _choose_tasks_from_menu()
    except Exception as error:
        print(f'Error: {error}')
        raise


if __name__ == '__main__':
    main()
