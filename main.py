from pathlib import Path
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
BAR_FILLED = '█'
BAR_EMPTY = '░'
ASCII_BAR_FILLED = '='
ASCII_BAR_EMPTY = '-'


def _clean_dropped_path(value: str) -> Path:
    return Path(value.strip().strip('"').strip("'")).expanduser()


def _get_csv_path() -> Path:
    if len(sys.argv) > 1:
        return _clean_dropped_path(sys.argv[1])

    raw_path = input('Drag your CSV file here, then press Enter: ')
    return _clean_dropped_path(raw_path)


def _open_folder(path: Path) -> None:
    path = path.resolve()
    system = platform.system()

    if system == 'Windows':
        os.startfile(path)
    elif system == 'Darwin':
        subprocess.run(['open', str(path)], check=False)
    else:
        subprocess.run(['xdg-open', str(path)], check=False)


def _make_progress_bar(label: str) -> Callable[[int, int], None]:
    encoding = sys.stdout.encoding or ''
    filled_char = BAR_FILLED if encoding.lower().startswith('utf') else ASCII_BAR_FILLED
    empty_char = BAR_EMPTY if encoding.lower().startswith('utf') else ASCII_BAR_EMPTY

    def update(current: int, total: int) -> None:
        percent = 100 if total == 0 else round((current / total) * 100)
        filled = BAR_WIDTH if total == 0 else round((current / total) * BAR_WIDTH)
        bar = filled_char * filled + empty_char * (BAR_WIDTH - filled)
        end = '\n' if current >= total else ''
        print(f'\r{label:<13} {bar} {percent:3d}%', end=end, flush=True)

    return update


def generate_all(filename: Path) -> None:
    if not filename.exists():
        raise FileNotFoundError(f'CSV file not found: {filename}')

    print(f'Using CSV: {filename}')
    setlist = Credits.generate(filename, progress_callback=_make_progress_bar('Credits'))
    LowerThirds.generate(setlist, progress_callback=_make_progress_bar('Lower thirds'))
    _open_folder(OUTPUT_FOLDER)


def main() -> None:
    try:
        generate_all(_get_csv_path())
    except Exception as error:
        print(f'Error: {error}')
        raise


if __name__ == '__main__':
    main()
