from __future__ import annotations

from pathlib import Path
import mimetypes
import re
import subprocess
import sys

from pptx.enum.shapes import MSO_SHAPE_TYPE
from pptx.shapes.base import BaseShape

from .models import Placement, SlideLayer


YOUTUBE_PATTERN = re.compile(
    r'(?:youtube(?:-nocookie)?\.com/(?:watch\?v=|embed/|shorts/|v/)|youtu\.be/)([A-Za-z0-9_-]{11})',
    re.IGNORECASE,
)
GOOGLE_DRIVE_FILE_PATTERN = re.compile(
    r'drive\.google\.com/(?:file/d/|open\?id=)[A-Za-z0-9_-]+',
    re.IGNORECASE,
)
VIDEO_EXTENSIONS = {'.mp4', '.webm', '.mov', '.avi', '.wmv', '.mpeg', '.mpg', '.m4v'}
VIDEO_CONTENT_TYPES = {
    'video/mp4': '.mp4',
    'video/webm': '.webm',
    'video/quicktime': '.mov',
    'video/x-msvideo': '.avi',
    'video/x-ms-wmv': '.wmv',
    'video/mpeg': '.mpeg',
}


def _placement(shape: BaseShape, slide_width: int, slide_height: int) -> Placement:
    from .inventory import OUTPUT_HEIGHT, OUTPUT_WIDTH

    return Placement(
        x=round(int(shape.left) / slide_width * OUTPUT_WIDTH),
        y=round(int(shape.top) / slide_height * OUTPUT_HEIGHT),
        width=round(int(shape.width) / slide_width * OUTPUT_WIDTH),
        height=round(int(shape.height) / slide_height * OUTPUT_HEIGHT),
    )


def _relationship_ids(shape: BaseShape) -> list[str]:
    relationship_ids: list[str] = []
    for element in shape.element.iter():
        for value in element.attrib.values():
            if isinstance(value, str) and value.startswith('rId'):
                relationship_ids.append(value)

    return list(dict.fromkeys(relationship_ids))


def _relationship_id_pairs(shape: BaseShape) -> list[tuple[str, object]]:
    pairs: list[tuple[str, object]] = []
    for rel_id in _relationship_ids(shape):
        rel = shape.part.rels.get(rel_id)
        if rel is not None:
            pairs.append((rel_id, rel))
    return pairs


def _target_part(rel: object) -> object | None:
    try:
        return getattr(rel, 'target_part', None)
    except ValueError:
        return None


def _relationship_video_reason(rel: object, rel_id: str | None = None) -> str | None:
    content_type = str(getattr(_target_part(rel), 'content_type', '') or '').lower()
    target_ref = str(getattr(rel, 'target_ref', '') or '')
    prefix = f'{rel_id} ' if rel_id else ''

    if content_type.startswith('video/'):
        return f'{prefix}content type {content_type}'
    if Path(target_ref.lower()).suffix in VIDEO_EXTENSIONS:
        return f'{prefix}target {target_ref}'
    if YOUTUBE_PATTERN.search(target_ref):
        return f'{prefix}YouTube URL {target_ref}'
    if GOOGLE_DRIVE_FILE_PATTERN.search(target_ref):
        return f'{prefix}Google Drive file link {target_ref}'
    return None


def _youtube_url(value: str) -> str | None:
    match = YOUTUBE_PATTERN.search(value)
    if not match:
        return None

    return f'https://www.youtube.com/watch?v={match.group(1)}'


def _google_drive_url(value: str) -> str | None:
    match = GOOGLE_DRIVE_FILE_PATTERN.search(value)
    if not match:
        return None
    url = match.group(0)
    return url if url.startswith('http') else f'https://{url}'


def _video_url(value: str) -> tuple[str, str] | None:
    youtube_url = _youtube_url(value)
    if youtube_url:
        return youtube_url, 'youtube'

    drive_url = _google_drive_url(value)
    if drive_url:
        return drive_url, 'google_drive'

    return None


def _relationship_is_video(rel: object) -> bool:
    return _relationship_video_reason(rel) is not None


def _relationship_extension(rel: object) -> str:
    content_type = str(getattr(_target_part(rel), 'content_type', '') or '').lower()
    if content_type in VIDEO_CONTENT_TYPES:
        return VIDEO_CONTENT_TYPES[content_type]

    suffix = Path(str(getattr(rel, 'target_ref', '') or '')).suffix
    if suffix:
        return suffix

    guessed = mimetypes.guess_extension(content_type)
    return guessed or '.mp4'


def _write_embedded_video(rel: object, output_template: Path) -> Path | None:
    target_part = _target_part(rel)
    blob = getattr(target_part, 'blob', None)
    if not blob:
        return None

    output_path = output_template.with_suffix(_relationship_extension(rel))
    output_path.write_bytes(blob)
    print(f'Extracted embedded video: {output_path.name}', flush=True)
    return output_path


def _download_video(url: str, source_type: str, output_template: Path) -> Path:
    output_pattern = str(output_template.with_suffix('.%(ext)s'))
    command = [
        sys.executable,
        '-m',
        'yt_dlp',
        '--no-playlist',
        '-o',
        output_pattern,
    ]
    if source_type == 'youtube':
        command.extend([
            '-f',
            'bestvideo[height<=1080]/bestvideo',
        ])
    command.append(url)

    result = subprocess.run(
        command,
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f'yt-dlp failed to download {url}.\n'
            f'stdout: {result.stdout}\n'
            f'stderr: {result.stderr}'
        )

    matches = sorted(output_template.parent.glob(f'{output_template.name}.*'))
    if not matches:
        raise FileNotFoundError(f'yt-dlp did not produce a video for {url}.')

    print(f'Downloaded video: {matches[0].name}', flush=True)
    return matches[0]


def _shape_relationships(shape: BaseShape) -> list[object]:
    return [rel for _rel_id, rel in _relationship_id_pairs(shape)]


def shape_video_reason(shape: BaseShape) -> str | None:
    if shape.shape_type == MSO_SHAPE_TYPE.MEDIA:
        return f'shape {shape.shape_id} is MEDIA'

    xml = shape.element.xml.lower()
    if 'video' in xml:
        return f'shape {shape.shape_id} XML contains video'
    if YOUTUBE_PATTERN.search(xml):
        return f'shape {shape.shape_id} XML contains YouTube URL'
    if GOOGLE_DRIVE_FILE_PATTERN.search(xml):
        return f'shape {shape.shape_id} XML contains Google Drive file link'

    for rel_id, rel in _relationship_id_pairs(shape):
        reason = _relationship_video_reason(rel, rel_id)
        if reason:
            return f'shape {shape.shape_id} relationship {reason}'

    return None


def shape_is_video(shape: BaseShape) -> bool:
    return shape_video_reason(shape) is not None


def slide_video_reason(shapes: list[BaseShape]) -> str | None:
    if not shapes:
        return None

    for shape in shapes:
        reason = shape_video_reason(shape)
        if reason:
            return reason

    for rel_id, rel in shapes[0].part.rels.items():
        reason = _relationship_video_reason(rel, rel_id)
        if reason:
            return f'slide relationship {reason}'

    return None


def slide_has_video(shapes: list[BaseShape]) -> bool:
    return slide_video_reason(shapes) is not None


def _shape_video_url(shape: BaseShape) -> tuple[str, str] | None:
    url = _video_url(shape.element.xml)
    if url:
        return url

    for _rel_id, rel in _relationship_id_pairs(shape):
        url = _video_url(str(getattr(rel, 'target_ref', '') or ''))
        if url:
            return url

    return None


def _slide_video_url(shapes: list[BaseShape]) -> tuple[str, str] | None:
    if not shapes:
        return None

    for rel in shapes[0].part.rels.values():
        url = _video_url(str(getattr(rel, 'target_ref', '') or ''))
        if url:
            return url

    return None


def extract_videos(
        shapes: list[BaseShape],
        output_folder: Path,
        slide_stem: str,
        slide_width: int,
        slide_height: int,
) -> list[SlideLayer]:
    layers: list[SlideLayer] = []
    video_index = 1

    for z_index, shape in enumerate(shapes, start=1):
        if not shape_video_reason(shape):
            continue

        output_stem = slide_stem if video_index == 1 else f'{slide_stem}_video_{video_index}'
        output_template = output_folder / output_stem
        output_path: Path | None = None

        for _rel_id, rel in _relationship_id_pairs(shape):
            if _relationship_is_video(rel) and not getattr(rel, 'is_external', False):
                output_path = _write_embedded_video(rel, output_template)
                if output_path:
                    break

        if output_path is None:
            video_url = _shape_video_url(shape)
            if video_url:
                url, source_type = video_url
                output_path = _download_video(url, source_type, output_template)

        if output_path is None:
            continue

        layers.append(
            SlideLayer(
                type='video',
                shape_id=int(shape.shape_id),
                z_index=z_index,
                source_file=output_path.name,
                placement=_placement(shape, slide_width, slide_height),
                rotation=float(shape.rotation or 0.0),
                full_canvas_file=output_path.name,
            )
        )
        video_index += 1

    if layers:
        return layers

    slide_url = _slide_video_url(shapes)
    if not slide_url or not shapes:
        return []

    url, source_type = slide_url
    output_path = _download_video(url, source_type, output_folder / slide_stem)
    fallback_shape = next((shape for shape in shapes if shape_video_reason(shape)), shapes[-1])
    return [
        SlideLayer(
            type='video',
            shape_id=int(fallback_shape.shape_id),
            z_index=len(shapes),
            source_file=output_path.name,
            placement=_placement(fallback_shape, slide_width, slide_height),
            rotation=float(fallback_shape.rotation or 0.0),
            full_canvas_file=output_path.name,
        )
    ]
