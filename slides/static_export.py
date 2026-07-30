from __future__ import annotations

from pathlib import Path
import shutil
import subprocess
import tempfile
import xml.etree.ElementTree as ET
import zipfile
from typing import Callable

from PIL import Image
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.util import Length

from font_setup import download_google_fonts_for_pptx, ensure_project_fonts_available


OUTPUT_WIDTH = 1920
OUTPUT_HEIGHT = 1080


def _find_libreoffice() -> str:
    for name in ('soffice', 'libreoffice'):
        executable = shutil.which(name)
        if executable:
            return executable

    windows_candidates = [
        Path('C:/Program Files/LibreOffice/program/soffice.exe'),
        Path('C:/Program Files (x86)/LibreOffice/program/soffice.exe'),
    ]
    macos_candidates = [
        Path('/Applications/LibreOffice.app/Contents/MacOS/soffice'),
    ]
    for candidate in windows_candidates + macos_candidates:
        if candidate.exists():
            return str(candidate)

    raise FileNotFoundError(
        'LibreOffice was not found. Install LibreOffice and make sure soffice/libreoffice is available on PATH.'
    )


def _convert_pptx_to_pdf(pptx_path: Path, output_dir: Path) -> Path:
    executable = _find_libreoffice()
    result = subprocess.run(
        [
            executable,
            '--headless',
            '--nologo',
            '--nofirststartwizard',
            '--norestore',
            '--nodefault',
            '--convert-to',
            'pdf',
            '--outdir',
            str(output_dir),
            str(pptx_path),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        raise RuntimeError(
            'LibreOffice failed to convert the presentation to PDF.\n'
            f'stdout: {result.stdout}\n'
            f'stderr: {result.stderr}'
        )

    pdf_path = output_dir / f'{pptx_path.stem}.pdf'
    if pdf_path.exists():
        return pdf_path

    pdfs = sorted(output_dir.glob('*.pdf'))
    if not pdfs:
        raise FileNotFoundError('LibreOffice did not produce a PDF output file.')
    return pdfs[0]


def _save_shape_filtered_pptx(
        pptx_path: Path,
        output_path: Path,
        shape_ids_by_slide: list[set[int]],
        keep_shape_ids_by_slide: list[set[int] | None] | None = None,
        background_color_by_slide: dict[int, tuple[int, int, int]] | None = None,
) -> None:
    presentation = Presentation(str(pptx_path))
    background_color_by_slide = background_color_by_slide or {}
    if presentation.slide_width is None or presentation.slide_height is None:
        raise RuntimeError('Presentation slide dimensions could not be read.')

    for slide_index, slide in enumerate(presentation.slides):
        remove_shape_ids = shape_ids_by_slide[slide_index] if slide_index < len(shape_ids_by_slide) else set()
        keep_shape_ids = (
            keep_shape_ids_by_slide[slide_index]
            if keep_shape_ids_by_slide is not None and slide_index < len(keep_shape_ids_by_slide)
            else None
        )

        for shape in reversed(list(slide.shapes)):
            shape_id = int(shape.shape_id)
            if keep_shape_ids is not None:
                should_remove = shape_id not in keep_shape_ids
            else:
                should_remove = shape_id in remove_shape_ids

            if not should_remove:
                continue
            element = shape.element
            element.getparent().remove(element)

        if slide_index in background_color_by_slide:
            background = slide.shapes.add_shape(
                MSO_SHAPE.RECTANGLE,
                Length(0),
                Length(0),
                Length(presentation.slide_width),
                Length(presentation.slide_height),
            )
            background.fill.solid()
            background.fill.fore_color.rgb = RGBColor(*background_color_by_slide[slide_index])
            background.line.fill.background()
            element = background.element
            element.getparent().remove(element)
            slide.shapes._spTree.insert(2, element)

    presentation.save(str(output_path))


def _image_background_slide_indexes(pptx_path: Path, skipped_slide_indexes: set[int]) -> set[int]:
    image_backgrounds: set[int] = set()
    presentation = Presentation(str(pptx_path))
    namespaces = {
        'p': 'http://schemas.openxmlformats.org/presentationml/2006/main',
        'a': 'http://schemas.openxmlformats.org/drawingml/2006/main',
    }

    with zipfile.ZipFile(pptx_path) as archive:
        for slide_index, slide in enumerate(presentation.slides):
            if slide_index in skipped_slide_indexes:
                continue

            slide_name = str(slide.part.partname).lstrip('/')
            root = ET.fromstring(archive.read(slide_name))
            background = root.find('p:cSld/p:bg', namespaces)
            if background is not None and background.find('.//a:blip', namespaces) is not None:
                image_backgrounds.add(slide_index)

    return image_backgrounds


def _render_pdf_to_slide_pngs(
        pdf_path: Path,
        output_folder: Path,
        slide_count: int,
        skipped_slide_indexes: set[int],
        progress_callback: Callable[[], None] | None = None,
        suffix: str = '',
        log_saved_outputs: bool = False,
        layered_static_slide_indexes: set[int] | None = None,
) -> None:
    try:
        import pymupdf
    except ModuleNotFoundError as error:
        raise RuntimeError('PyMuPDF is required to render LibreOffice PDF output. Run the launcher to install dependencies.') from error

    document = pymupdf.open(str(pdf_path))
    try:
        if document.page_count != slide_count:
            raise RuntimeError(
                f'LibreOffice produced {document.page_count} PDF page(s), but the presentation has {slide_count} slide(s).'
            )

        for page_index in range(slide_count):
            if page_index in skipped_slide_indexes:
                continue

            page: pymupdf.Page = document.load_page(page_index)
            pixmap: pymupdf.Pixmap = page.get_pixmap(  # pyright: ignore[reportAttributeAccessIssue]
                matrix=pymupdf.Matrix(OUTPUT_WIDTH / page.rect.width, OUTPUT_HEIGHT / page.rect.height),
                alpha=False,
            )
            layered_static_slide_indexes = layered_static_slide_indexes or set()
            output_stem = (
                f'{page_index:02d}_layer1'
                if not suffix and page_index in layered_static_slide_indexes
                else f'{page_index:02d}{suffix}'
            )
            static_path = output_folder / f'{output_stem}.png'
            pixmap.save(str(static_path))

            if pixmap.width != OUTPUT_WIDTH or pixmap.height != OUTPUT_HEIGHT:
                raise RuntimeError(f'{static_path} was rendered at {pixmap.width}x{pixmap.height}, expected 1920x1080.')

            if log_saved_outputs:
                print(f'Slide {page_index + 1}/{slide_count} saved: {static_path.name}', flush=True)

            if progress_callback:
                progress_callback()
    finally:
        document.close()


def _render_static_pngs_with_alpha(
        black_pdf_path: Path,
        white_pdf_path: Path,
        output_folder: Path,
        slide_count: int,
        skipped_slide_indexes: set[int],
        layered_static_slide_indexes: set[int],
        progress_callback: Callable[[], None] | None = None,
) -> None:
    with tempfile.TemporaryDirectory(prefix='stream_graphics_static_alpha_') as temp_dir:
        temp_path = Path(temp_dir)
        _render_pdf_to_slide_pngs(black_pdf_path, temp_path, slide_count, skipped_slide_indexes, suffix='_black')
        _render_pdf_to_slide_pngs(white_pdf_path, temp_path, slide_count, skipped_slide_indexes, suffix='_white')

        for slide_index in range(slide_count):
            if slide_index in skipped_slide_indexes:
                continue

            output_filename = (
                f'{slide_index:02d}_layer1.png'
                if slide_index in layered_static_slide_indexes
                else f'{slide_index:02d}.png'
            )
            _alpha_from_black_white_renders(
                temp_path / f'{slide_index:02d}_black.png',
                temp_path / f'{slide_index:02d}_white.png',
                output_folder / output_filename,
            )
            print(f'Slide {slide_index + 1}/{slide_count} saved: {output_filename}', flush=True)
            if progress_callback:
                progress_callback()


def _render_pdf_page_to_png(pdf_path: Path, page_index: int, output_path: Path) -> None:
    try:
        import pymupdf
    except ModuleNotFoundError as error:
        raise RuntimeError('PyMuPDF is required to render LibreOffice PDF output. Run the launcher to install dependencies.') from error

    document = pymupdf.open(str(pdf_path))
    try:
        page: pymupdf.Page = document.load_page(page_index)
        pixmap: pymupdf.Pixmap = page.get_pixmap(  # pyright: ignore[reportAttributeAccessIssue]
            matrix=pymupdf.Matrix(OUTPUT_WIDTH / page.rect.width, OUTPUT_HEIGHT / page.rect.height),
            alpha=False,
        )
        pixmap.save(str(output_path))

        if pixmap.width != OUTPUT_WIDTH or pixmap.height != OUTPUT_HEIGHT:
            raise RuntimeError(f'{output_path} was rendered at {pixmap.width}x{pixmap.height}, expected 1920x1080.')
    finally:
        document.close()


def _alpha_from_black_white_renders(black_path: Path, white_path: Path, output_path: Path) -> None:
    black = Image.open(black_path).convert('RGB')
    white = Image.open(white_path).convert('RGB')
    output = Image.new('RGBA', black.size)

    black_pixels = black.load()
    white_pixels = white.load()
    output_pixels = output.load()
    assert black_pixels is not None
    assert white_pixels is not None
    assert output_pixels is not None

    for y in range(black.height):
        for x in range(black.width):
            black_rgb = black_pixels[x, y]
            white_rgb = white_pixels[x, y]
            channel_alpha = [
                255 - max(0, min(255, white_rgb[channel] - black_rgb[channel]))
                for channel in range(3)
            ]
            alpha = max(channel_alpha)

            if alpha <= 2:
                output_pixels[x, y] = (0, 0, 0, 0)
                continue

            rgb = tuple(
                max(0, min(255, round(black_rgb[channel] * 255 / alpha)))
                for channel in range(3)
            )
            output_pixels[x, y] = (*rgb, alpha)

    output.save(output_path)


def _export_transparent_static_overlay(
        pptx_path: Path,
        output_folder: Path,
        slide_count: int,
        slide_index: int,
        keep_shape_ids: set[int],
        output_filename: str,
        temp_path: Path,
        progress_callback: Callable[[], None] | None = None,
) -> None:
    keep_shape_ids_by_slide: list[set[int] | None] = [None] * slide_count
    keep_shape_ids_by_slide[slide_index] = keep_shape_ids
    black_pptx_path = temp_path / f'black_{slide_index:02d}_{pptx_path.name}'
    _save_shape_filtered_pptx(
        pptx_path,
        black_pptx_path,
        [set()] * slide_count,
        keep_shape_ids_by_slide,
        {slide_index: (0, 0, 0)},
    )
    black_pdf_path = _convert_pptx_to_pdf(black_pptx_path, temp_path)
    black_png_path = temp_path / f'black_{slide_index:02d}.png'
    _render_pdf_page_to_png(black_pdf_path, slide_index, black_png_path)

    white_pptx_path = temp_path / f'white_{slide_index:02d}_{pptx_path.name}'
    _save_shape_filtered_pptx(
        pptx_path,
        white_pptx_path,
        [set()] * slide_count,
        keep_shape_ids_by_slide,
        {slide_index: (255, 255, 255)},
    )
    white_pdf_path = _convert_pptx_to_pdf(white_pptx_path, temp_path)
    white_png_path = temp_path / f'white_{slide_index:02d}.png'
    _render_pdf_page_to_png(white_pdf_path, slide_index, white_png_path)

    _alpha_from_black_white_renders(
        black_png_path,
        white_png_path,
        output_folder / output_filename,
    )
    print(f'Slide {slide_index + 1}/{slide_count} saved: {output_filename}', flush=True)
    if progress_callback:
        progress_callback()


def export_static_pngs(
        pptx_path: Path,
        output_folder: Path,
        slide_count: int,
        shape_ids_by_slide: list[set[int]],
        skipped_slide_indexes: set[int] | None = None,
        layered_static_slide_indexes: set[int] | None = None,
        transparent_static_layers_by_slide: dict[int, list[tuple[set[int], str]]] | None = None,
        progress_callback: Callable[[], None] | None = None,
) -> None:
    skipped_slide_indexes = skipped_slide_indexes or set()
    layered_static_slide_indexes = layered_static_slide_indexes or set()
    transparent_static_layers_by_slide = transparent_static_layers_by_slide or {}

    with tempfile.TemporaryDirectory(prefix='stream_graphics_slides_pdf_') as temp_dir:
        temp_path = Path(temp_dir)
        google_font_dir = temp_path / 'google_fonts'
        google_fonts = download_google_fonts_for_pptx(pptx_path, google_font_dir)
        ensure_project_fonts_available(google_fonts)
        image_background_slide_indexes = _image_background_slide_indexes(pptx_path, skipped_slide_indexes)
        transparent_slide_indexes = {
            slide_index
            for slide_index in range(slide_count)
            if slide_index not in skipped_slide_indexes and slide_index not in image_background_slide_indexes
        }
        black_backgrounds = {slide_index: (0, 0, 0) for slide_index in transparent_slide_indexes}
        white_backgrounds = {slide_index: (255, 255, 255) for slide_index in transparent_slide_indexes}
        transparent_skipped_slide_indexes = set(range(slide_count)) - transparent_slide_indexes
        image_background_skipped_slide_indexes = set(range(slide_count)) - image_background_slide_indexes

        if image_background_slide_indexes:
            print(
                'Preserving slide image background(s): '
                + ', '.join(f'{slide_index:02d}' for slide_index in sorted(image_background_slide_indexes)),
                flush=True,
            )
        if transparent_slide_indexes:
            print(
                'Rendering transparent slide background(s): '
                + ', '.join(f'{slide_index:02d}' for slide_index in sorted(transparent_slide_indexes)),
                flush=True,
            )

        black_cleaned_pptx_path = temp_path / f'black_{pptx_path.name}'
        _save_shape_filtered_pptx(
            pptx_path,
            black_cleaned_pptx_path,
            shape_ids_by_slide,
            background_color_by_slide=black_backgrounds,
        )
        black_pdf_path = _convert_pptx_to_pdf(black_cleaned_pptx_path, temp_path)

        white_cleaned_pptx_path = temp_path / f'white_{pptx_path.name}'
        _save_shape_filtered_pptx(
            pptx_path,
            white_cleaned_pptx_path,
            shape_ids_by_slide,
            background_color_by_slide=white_backgrounds,
        )
        white_pdf_path = _convert_pptx_to_pdf(white_cleaned_pptx_path, temp_path)

        _render_static_pngs_with_alpha(
            black_pdf_path,
            white_pdf_path,
            output_folder,
            slide_count,
            transparent_skipped_slide_indexes,
            layered_static_slide_indexes,
            progress_callback,
        )

        if image_background_slide_indexes:
            image_background_pptx_path = temp_path / f'image_bg_{pptx_path.name}'
            _save_shape_filtered_pptx(pptx_path, image_background_pptx_path, shape_ids_by_slide)
            image_background_pdf_path = _convert_pptx_to_pdf(image_background_pptx_path, temp_path)
            _render_pdf_to_slide_pngs(
                image_background_pdf_path,
                output_folder,
                slide_count,
                image_background_skipped_slide_indexes,
                progress_callback,
                log_saved_outputs=True,
                layered_static_slide_indexes=layered_static_slide_indexes,
            )

        for slide_index, static_layers in transparent_static_layers_by_slide.items():
            for keep_shape_ids, output_filename in static_layers:
                _export_transparent_static_overlay(
                    pptx_path,
                    output_folder,
                    slide_count,
                    slide_index,
                    keep_shape_ids,
                    output_filename,
                    temp_path,
                    progress_callback,
                )
