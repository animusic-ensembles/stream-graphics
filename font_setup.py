from __future__ import annotations

from pathlib import Path
import ctypes
import platform
import re
import shutil
import subprocess
import zipfile
from urllib.error import HTTPError, URLError
from urllib.parse import quote_plus
from urllib.request import Request, urlopen


PROJECT_ROOT = Path(__file__).resolve().parent
FONTS_DIR = PROJECT_ROOT / 'fonts'
FONT_EXTENSIONS = {'.ttf', '.otf', '.woff', '.woff2'}
SYSTEM_FONT_EXTENSIONS = {'.ttf', '.otf'}
_FONTS_READY = False
HWND_BROADCAST = 0xFFFF
WM_FONTCHANGE = 0x001D
FONT_ATTR_PATTERN = re.compile(r'typeface="([^"]+)"')
FONT_URL_PATTERN = re.compile(r'url\((https://[^)]+)\)')
FONT_STYLE_SUFFIXES = (
    'Thin',
    'Extra Light',
    'ExtraLight',
    'Light',
    'Regular',
    'Medium',
    'Semi Bold',
    'SemiBold',
    'Demi Bold',
    'DemiBold',
    'Bold',
    'Extra Bold',
    'ExtraBold',
    'Black',
    'Italic',
)
IGNORED_TYPEFACES = {
    '',
    '+mj-cs',
    '+mj-ea',
    '+mj-lt',
    '+mn-cs',
    '+mn-ea',
    '+mn-lt',
    'majorBidi',
    'majorEastAsia',
    'majorHAnsi',
    'minorBidi',
    'minorEastAsia',
    'minorHAnsi',
}
USER_AGENT = 'Mozilla/5.0 stream-graphics-generator'


def _project_font_files() -> list[Path]:
    if not FONTS_DIR.exists():
        return []

    return sorted(
        path
        for path in FONTS_DIR.iterdir()
        if path.is_file() and path.suffix.lower() in FONT_EXTENSIONS
    )


def _download(url: str, timeout: int = 30) -> bytes:
    request = Request(url, headers={'User-Agent': USER_AGENT})
    with urlopen(request, timeout=timeout) as response:
        return response.read()


def _font_family_names_from_pptx(pptx_path: Path) -> set[str]:
    families: set[str] = set()
    with zipfile.ZipFile(pptx_path) as archive:
        for name in archive.namelist():
            if not name.startswith('ppt/') or not name.endswith('.xml'):
                continue
            xml = archive.read(name).decode('utf-8', errors='ignore')
            for match in FONT_ATTR_PATTERN.finditer(xml):
                family = match.group(1).strip()
                if family not in IGNORED_TYPEFACES:
                    families.add(family)
    return families


def _google_font_family_candidates(family: str) -> list[str]:
    candidates = [family]
    for suffix in FONT_STYLE_SUFFIXES:
        style_suffix = f' {suffix}'
        if family.endswith(style_suffix):
            candidates.append(family[:-len(style_suffix)])
            break
    return list(dict.fromkeys(candidates))


def _download_google_font_family_css(family: str) -> tuple[str, str] | None:
    css_urls = [
        (
            'https://fonts.googleapis.com/css2'
            f'?family={quote_plus(family)}:wght@100;200;300;400;500;600;700;800;900'
            '&display=swap'
        ),
        (
            'https://fonts.googleapis.com/css2'
            f'?family={quote_plus(family)}'
            '&display=swap'
        ),
    ]

    for css_url in css_urls:
        try:
            css = _download(css_url).decode('utf-8', errors='ignore')
            return css, css_url
        except (HTTPError, URLError, TimeoutError, OSError):
            continue

    return None


def _download_google_font_family(family: str, output_dir: Path) -> list[Path]:
    css = ''
    resolved_family = family
    for family_candidate in _google_font_family_candidates(family):
        downloaded_css = _download_google_font_family_css(family_candidate)
        if downloaded_css is None:
            continue
        resolved_family = family_candidate
        css, _css_url = downloaded_css
        break

    if not css:
        return []

    downloaded: list[Path] = []
    for index, font_url in enumerate(dict.fromkeys(FONT_URL_PATTERN.findall(css)), start=1):
        try:
            data = _download(font_url)
        except (HTTPError, URLError, TimeoutError, OSError):
            continue

        suffix = Path(font_url.split('?', 1)[0]).suffix or '.woff2'
        output_path = output_dir / f'{resolved_family.replace(" ", "_")}_{index}{suffix}'
        output_path.write_bytes(data)
        downloaded.append(output_path)

    return downloaded


def _convert_web_font_to_ttf(font_path: Path) -> Path | None:
    if font_path.suffix.lower() not in {'.woff', '.woff2'}:
        return font_path

    try:
        from fontTools.ttLib import TTFont
    except ModuleNotFoundError:
        print(f'Could not convert {font_path.name}: fonttools is not installed.', flush=True)
        return None

    output_path = font_path.with_suffix('.ttf')
    try:
        font = TTFont(str(font_path))
        font.flavor = None
        font.save(str(output_path))
    except Exception as error:
        print(f'Could not convert {font_path.name} to TTF: {error}', flush=True)
        return None

    return output_path


def _convert_web_fonts_to_system_fonts(fonts: list[Path]) -> list[Path]:
    system_fonts: list[Path] = []
    for font in fonts:
        converted = _convert_web_font_to_ttf(font)
        if converted is not None and converted.suffix.lower() in SYSTEM_FONT_EXTENSIONS:
            system_fonts.append(converted)
    return system_fonts


def download_google_fonts_for_pptx(pptx_path: Path, output_dir: Path) -> list[Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    downloaded: list[Path] = []
    for family in sorted(_font_family_names_from_pptx(pptx_path)):
        family_fonts = _download_google_font_family(family, output_dir)
        if family_fonts:
            print(f'Downloaded Google Font family: {family}', flush=True)
            downloaded.extend(_convert_web_fonts_to_system_fonts(family_fonts))

    if downloaded:
        extensions = ', '.join(sorted({path.suffix.lower() for path in downloaded}))
        print(f'Prepared {len(downloaded)} Google Font file(s) for slide rendering ({extensions}).', flush=True)
    return downloaded


def _install_windows_session_fonts(fonts: list[Path]) -> None:
    registered = 0
    for font in fonts:
        added = ctypes.windll.gdi32.AddFontResourceExW(str(font), 0, 0)
        if added:
            registered += 1
            ctypes.windll.user32.SendMessageW(HWND_BROADCAST, WM_FONTCHANGE, 0, 0)

    if registered:
        print(f'Registered {registered} project font file(s) for this Windows session.', flush=True)
    else:
        print('Could not register project fonts with Windows.', flush=True)


def _install_linux_user_fonts(fonts: list[Path], destination_dir: Path | None = None) -> None:
    destination_dir = destination_dir or Path.home() / '.local' / 'share' / 'fonts' / 'stream-graphics'
    destination_dir.mkdir(parents=True, exist_ok=True)
    changed = False

    for font in fonts:
        destination = destination_dir / font.name
        if not destination.exists() or destination.stat().st_size != font.stat().st_size:
            shutil.copy2(font, destination)
            changed = True

    fc_cache = shutil.which('fc-cache')
    if fc_cache:
        subprocess.run([fc_cache, '-f', str(destination_dir)], check=False, capture_output=True, text=True)
    elif changed:
        print('Installed project fonts, but fc-cache was not found. LibreOffice may need fontconfig refresh.', flush=True)


def ensure_project_fonts_available(extra_fonts: list[Path] | None = None, linux_font_dir: Path | None = None) -> None:
    global _FONTS_READY
    extra_fonts = extra_fonts or []
    if _FONTS_READY and not extra_fonts:
        return

    fonts = _project_font_files() + extra_fonts
    if not fonts:
        print(f'No project fonts found in {FONTS_DIR}.', flush=True)
        return

    system = platform.system()
    if system == 'Windows':
        _install_windows_session_fonts(fonts)
    elif system == 'Linux':
        _install_linux_user_fonts(fonts, linux_font_dir)
    else:
        print(f'Automatic font installation is not supported on {system}.', flush=True)

    if not extra_fonts:
        _FONTS_READY = True
