from __future__ import annotations

from pathlib import Path
import tempfile
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlencode, urlparse
from urllib.request import Request, urlopen


USER_AGENT = 'stream-graphics-generator'


def clean_input(value: str) -> str:
    return value.strip().strip('"').strip("'")


def clean_path(value: str) -> Path:
    return Path(clean_input(value)).expanduser()


def is_url(value: str) -> bool:
    parsed = urlparse(value)
    return parsed.scheme in {'http', 'https'} and bool(parsed.netloc)


def google_sheets_csv_url(value: str) -> str:
    parsed = urlparse(value)
    if parsed.netloc.lower() != 'docs.google.com':
        raise ValueError('Only Google Sheets links are supported for CSV input.')

    path_parts = [part for part in parsed.path.split('/') if part]
    if len(path_parts) < 3 or path_parts[0] != 'spreadsheets' or path_parts[1] != 'd':
        raise ValueError('That does not look like a Google Sheets link.')

    query = parse_qs(parsed.query)
    fragment = parse_qs(parsed.fragment)
    gid = (fragment.get('gid') or query.get('gid') or ['0'])[0]

    if path_parts[2] == 'e' and len(path_parts) >= 4:
        published_id = path_parts[3]
        params = urlencode({'output': 'csv', 'gid': gid})
        return f'https://docs.google.com/spreadsheets/d/e/{published_id}/pub?{params}'

    sheet_id = path_parts[2]
    params = urlencode({'format': 'csv', 'gid': gid})
    return f'https://docs.google.com/spreadsheets/d/{sheet_id}/export?{params}'


def google_slides_pptx_url(value: str) -> str:
    parsed = urlparse(value)
    if parsed.netloc.lower() != 'docs.google.com':
        raise ValueError('Only Google Slides links are supported for PPTX input.')

    path_parts = [part for part in parsed.path.split('/') if part]
    if len(path_parts) < 3 or path_parts[0] != 'presentation' or path_parts[1] != 'd':
        raise ValueError('That does not look like a Google Slides link.')

    if path_parts[2] == 'e':
        raise ValueError('Published Google Slides links are not supported for PPTX export. Use a public share link.')

    presentation_id = path_parts[2]
    return f'https://docs.google.com/presentation/d/{presentation_id}/export/pptx'


def _download(url: str, timeout: int) -> tuple[bytes, str]:
    request = Request(url, headers={'User-Agent': USER_AGENT})

    try:
        with urlopen(request, timeout=timeout) as response:
            return response.read(), response.headers.get('content-type', '')
    except HTTPError as error:
        raise RuntimeError('Could not download the file. Make sure the link is public.') from error
    except URLError as error:
        raise RuntimeError(f'Could not reach the download URL: {error.reason}') from error


def _write_temp_file(data: bytes, suffix: str, prefix: str) -> Path:
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=suffix, prefix=prefix)
    with temp_file:
        temp_file.write(data)
    return Path(temp_file.name)


def download_google_sheet_csv(value: str) -> Path:
    data, content_type = _download(google_sheets_csv_url(value), timeout=30)

    preview = data[:256].lstrip().lower()
    if not data or preview.startswith(b'<!doctype html') or preview.startswith(b'<html'):
        raise RuntimeError('Google Sheets returned a web page instead of CSV. Make sure the link is public.')

    if 'text/csv' not in content_type and b',' not in data[:4096] and b'\n' not in data[:4096]:
        raise RuntimeError('Downloaded data does not look like a CSV file.')

    return _write_temp_file(data, suffix='.csv', prefix='stream_graphics_')


def download_google_slides_pptx(value: str) -> Path:
    data, content_type = _download(google_slides_pptx_url(value), timeout=60)

    preview = data[:256].lstrip().lower()
    if not data or preview.startswith(b'<!doctype html') or preview.startswith(b'<html'):
        raise RuntimeError('Google Slides returned a web page instead of PPTX. Make sure the link is public.')

    if 'presentation' not in content_type and not data.startswith(b'PK'):
        raise RuntimeError('Downloaded data does not look like a PPTX file.')

    return _write_temp_file(data, suffix='.pptx', prefix='stream_graphics_slides_')


def resolve_csv_input(value: str) -> Path:
    clean_value = clean_input(value)
    if is_url(clean_value):
        return download_google_sheet_csv(clean_value)

    path = clean_path(clean_value)
    if path.suffix.lower() != '.csv':
        raise ValueError('Credits input must be a .csv file or a public Google Sheets link.')
    if not path.exists():
        raise FileNotFoundError(f'CSV file not found: {path}')
    return path


def resolve_pptx_input(value: str) -> Path:
    clean_value = clean_input(value)
    if is_url(clean_value):
        return download_google_slides_pptx(clean_value)

    path = clean_path(clean_value)
    if path.suffix.lower() != '.pptx':
        raise ValueError('Slides input must be a .pptx file or a public Google Slides link.')
    if not path.exists():
        raise FileNotFoundError(f'PPTX file not found: {path}')
    return path
