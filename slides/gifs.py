from __future__ import annotations

from collections.abc import Generator
from hashlib import blake2b
from io import BytesIO
from math import gcd
from pathlib import Path

from PIL import Image, ImageEnhance, ImageFile, ImageSequence
from pptx.enum.shapes import MSO_SHAPE_TYPE
from pptx.shapes.base import BaseShape

from .inventory import OUTPUT_HEIGHT, OUTPUT_WIDTH
from .models import Placement, SlideLayer
from .mp4_export import save_background_mp4


ImageFile.LOAD_TRUNCATED_IMAGES = True

OOXML_PERCENT = 100000


def _is_animated_gif(blob: bytes) -> bool:
    try:
        with Image.open(BytesIO(blob)) as image:
            return image.format == 'GIF' and getattr(image, 'n_frames', 1) > 1
    except (OSError, ValueError):
        return False


def _placement(shape: BaseShape, slide_width: int, slide_height: int) -> Placement:
    return Placement(
        x=round(int(shape.left) / slide_width * OUTPUT_WIDTH),
        y=round(int(shape.top) / slide_height * OUTPUT_HEIGHT),
        width=round(int(shape.width) / slide_width * OUTPUT_WIDTH),
        height=round(int(shape.height) / slide_height * OUTPUT_HEIGHT),
    )


def _xml_bool(value: str | None) -> bool:
    return value in {'1', 'true', 'True'}


def _shape_transform_bool(shape: BaseShape, attribute: str) -> bool:
    for element in shape.element.iter():
        if element.tag.endswith('}xfrm'):
            return _xml_bool(element.get(attribute))
    return False


def _shape_crop(shape: BaseShape) -> tuple[float, float, float, float]:
    left = max(0.0, min(0.99, float(getattr(shape, 'crop_left', 0.0))))
    top = max(0.0, min(0.99, float(getattr(shape, 'crop_top', 0.0))))
    right = max(0.0, min(0.99, float(getattr(shape, 'crop_right', 0.0))))
    bottom = max(0.0, min(0.99, float(getattr(shape, 'crop_bottom', 0.0))))
    return (left, top, right, bottom)


def _xml_adjustment(shape: BaseShape, tag_name: str, attribute: str, default: int) -> int:
    for element in shape.element.iter():
        if element.tag.endswith(f'}}{tag_name}'):
            value = element.get(attribute)
            if value is not None:
                try:
                    return int(value)
                except ValueError:
                    return default
    return default


def _has_xml_tag(shape: BaseShape, tag_name: str) -> bool:
    return any(element.tag.endswith(f'}}{tag_name}') for element in shape.element.iter())


def _shape_opacity(shape: BaseShape) -> float:
    alpha = _xml_adjustment(shape, 'alphaModFix', 'amt', OOXML_PERCENT)
    alpha = _xml_adjustment(shape, 'alphaMod', 'amt', alpha)
    return max(0.0, min(1.0, alpha / OOXML_PERCENT))


def _shape_luminance(shape: BaseShape) -> tuple[float, float]:
    brightness = max(-1.0, min(1.0, _xml_adjustment(shape, 'lum', 'bright', 0) / OOXML_PERCENT))
    contrast = max(-1.0, min(1.0, _xml_adjustment(shape, 'lum', 'contrast', 0) / OOXML_PERCENT))
    return brightness, contrast


def _shape_color_adjustments(shape: BaseShape) -> tuple[float, bool]:
    saturation = max(0.0, _xml_adjustment(shape, 'satMod', 'val', OOXML_PERCENT) / OOXML_PERCENT)
    grayscale = _has_xml_tag(shape, 'grayscl')
    return saturation, grayscale


def _validate_full_canvas_animation(path: Path) -> None:
    with Image.open(path) as image:
        frame_count = getattr(image, 'n_frames', 1)
        if frame_count <= 1:
            raise RuntimeError(f'{path.name} is not animated after full-canvas rendering.')

        if image.size != (OUTPUT_WIDTH, OUTPUT_HEIGHT):
            raise RuntimeError(
                f'{path.name} is {image.size[0]}x{image.size[1]}, '
                f'expected {OUTPUT_WIDTH}x{OUTPUT_HEIGHT}.'
            )


def _transformed_frame(
        frame: Image.Image,
        width: int,
        height: int,
        rotation: float,
        flip_h: bool,
        flip_v: bool,
        crop: tuple[float, float, float, float],
        opacity: float,
        brightness: float,
        contrast: float,
        saturation: float,
        grayscale: bool
) -> Image.Image:
    transformed = frame.convert('RGBA')
    crop_left, crop_top, crop_right, crop_bottom = crop
    source_width, source_height = transformed.size
    crop_box = (
        round(source_width * crop_left),
        round(source_height * crop_top),
        round(source_width * (1 - crop_right)),
        round(source_height * (1 - crop_bottom)),
    )
    if crop_box[2] > crop_box[0] and crop_box[3] > crop_box[1]:
        transformed = transformed.crop(crop_box)

    if brightness:
        transformed = ImageEnhance.Brightness(transformed).enhance(max(0.0, 1.0 + brightness))
    if contrast:
        transformed = ImageEnhance.Contrast(transformed).enhance(max(0.0, 1.0 + contrast))
    if grayscale:
        transformed = ImageEnhance.Color(transformed).enhance(0.0)
    elif saturation != 1.0:
        transformed = ImageEnhance.Color(transformed).enhance(saturation)

    if opacity < 1.0:
        # Use a lookup table to avoid passing a callable with ambiguous typing to point()
        # and to ensure values are integers in 0-255.
        lut = [round(i * opacity) for i in range(256)]
        alpha = transformed.getchannel('A').point(lut)
        transformed.putalpha(alpha)

    transformed = transformed.resize((width, height), Image.Resampling.LANCZOS)

    if flip_h:
        transformed = transformed.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
    if flip_v:
        transformed = transformed.transpose(Image.Transpose.FLIP_TOP_BOTTOM)
    if rotation:
        # PowerPoint positive rotation is clockwise; Pillow positive rotation is counter-clockwise.
        transformed = transformed.rotate(
            -rotation,
            expand=True,
            resample=Image.Resampling.BICUBIC,
            fillcolor=(0, 0, 0, 0),
        )

    return transformed


def _frame_digest(frame: Image.Image, x: int, y: int) -> bytes:
    digest = blake2b(digest_size=16)
    digest.update(str((x, y, frame.size)).encode('ascii'))
    digest.update(frame.tobytes())
    return digest.digest()


def _source_frame_digest(frame: Image.Image) -> bytes:
    digest = blake2b(digest_size=16)
    digest.update(str((frame.mode, frame.size)).encode('ascii'))
    digest.update(frame.tobytes())
    return digest.digest()


def _save_animation(
        frames: list[Image.Image],
        durations: list[int],
        output_path: Path,
        loop: int,
) -> None:
    frames[0].save(
        output_path,
        save_all=True,
        append_images=frames[1:],
        duration=durations,
        loop=loop,
        disposal=[2] * len(frames),
        compress_level=1,
        optimize=False,
    )

    _validate_full_canvas_animation(output_path)


def _iter_full_canvas_frames(
        blob: bytes,
        output_path: Path,
        placement: Placement,
        rotation: float,
        flip_h: bool,
        flip_v: bool,
        crop: tuple[float, float, float, float],
        opacity: float,
        brightness: float,
        contrast: float,
        saturation: float,
        grayscale: bool,
) -> Generator[tuple[Image.Image, int], None, None]:
    width = max(1, placement.width)
    height = max(1, placement.height)
    rotation = rotation % 360
    center_x = placement.x + width / 2
    center_y = placement.y + height / 2

    pending_frame: Image.Image | None = None
    pending_duration = 0
    rendered_frame_count = 0
    previous_source_digest: bytes | None = None
    previous_digest: bytes | None = None
    source_frame_count = 0
    with Image.open(BytesIO(blob)) as image:
        default_duration = int(image.info.get('duration', 100))
        source_frame_count = getattr(image, 'n_frames', 1)
        print(
            f'Rendering animated overlay {output_path.name}: '
            f'source {image.size[0]}x{image.size[1]}, placement {width}x{height}, crop {crop}.',
            flush=True,
        )
        if source_frame_count >= 100 and output_path.suffix.lower() == '.png':
            print(
                f'Rendering large APNG overlay {output_path.name}: '
                f'{source_frame_count} frame(s) at {width}x{height}.',
                flush=True,
            )

        for source_frame in ImageSequence.Iterator(image):
            duration = max(10, int(source_frame.info.get('duration', default_duration)))
            source_digest = _source_frame_digest(source_frame)
            if pending_frame is not None and source_digest == previous_source_digest:
                pending_duration += duration
                continue

            transformed = _transformed_frame(
                source_frame,
                width,
                height,
                rotation,
                flip_h,
                flip_v,
                crop,
                opacity,
                brightness,
                contrast,
                saturation,
                grayscale,
            )
            rotated_width, rotated_height = transformed.size
            x = round(center_x - rotated_width / 2)
            y = round(center_y - rotated_height / 2)
            digest = _frame_digest(transformed, x, y)
            if pending_frame is not None and digest == previous_digest:
                pending_duration += duration
                previous_source_digest = source_digest
                continue

            if pending_frame is not None:
                yield pending_frame, pending_duration
            canvas = Image.new('RGBA', (OUTPUT_WIDTH, OUTPUT_HEIGHT), (0, 0, 0, 0))
            canvas.alpha_composite(transformed, (x, y))
            pending_frame = canvas
            pending_duration = duration
            rendered_frame_count += 1
            previous_source_digest = source_digest
            previous_digest = digest

    if pending_frame is None:
        raise RuntimeError(f'{output_path.name} had no source GIF frames to render.')
    yield pending_frame, pending_duration
    if rendered_frame_count < source_frame_count:
        print(
            f'Optimized animated overlay {output_path.name}: '
            f'{source_frame_count} source frame(s) collapsed to {rendered_frame_count} frame(s).',
            flush=True,
        )


def _render_full_canvas_animation(
        blob: bytes,
        output_path: Path,
        placement: Placement,
        rotation: float,
        flip_h: bool,
        flip_v: bool,
        crop: tuple[float, float, float, float],
        opacity: float,
        brightness: float,
        contrast: float,
        saturation: float,
        grayscale: bool,
        as_mp4: bool,
) -> None:
    with Image.open(BytesIO(blob)) as image:
        loop = int(image.info.get('loop', 0))
        frame_duration_ms = 0
        if as_mp4:
            default_duration = int(image.info.get('duration', 100))
            for frame in ImageSequence.Iterator(image):
                duration = max(10, int(frame.info.get('duration', default_duration)))
                frame_duration_ms = gcd(frame_duration_ms, duration)

    rendered_frames = _iter_full_canvas_frames(
        blob, output_path, placement, rotation, flip_h, flip_v, crop,
        opacity, brightness, contrast, saturation, grayscale,
    )
    if as_mp4:
        try:
            save_background_mp4(rendered_frames, output_path, frame_duration_ms)
        finally:
            rendered_frames.close()
        return

    frames: list[Image.Image] = []
    durations: list[int] = []
    for frame, duration in rendered_frames:
        frames.append(frame)
        durations.append(duration)
    _save_animation(frames, durations, output_path, loop)


def _is_background_gif(placement: Placement) -> bool:
    width_ratio = placement.width / OUTPUT_WIDTH
    height_ratio = placement.height / OUTPUT_HEIGHT
    area_ratio = (placement.width * placement.height) / (OUTPUT_WIDTH * OUTPUT_HEIGHT)
    return (width_ratio >= 0.9 and height_ratio >= 0.9) or area_ratio >= 0.85


def extract_animated_gifs(
        shapes: list[BaseShape],
        output_folder: Path,
        slide_stem: str,
        slide_width: int,
        slide_height: int
) -> list[SlideLayer]:
    layers: list[SlideLayer] = []
    animated_shapes: list[tuple[int, BaseShape, bytes, Placement, bool]] = []

    for z_index, shape in enumerate(shapes, start=1):
        if shape.shape_type != MSO_SHAPE_TYPE.PICTURE:
            continue

        image = getattr(shape, 'image', None)
        if image is None:
            continue

        blob = image.blob
        if not _is_animated_gif(blob):
            continue

        placement = _placement(shape, slide_width, slide_height)
        export_as_mp4 = _is_background_gif(placement)
        animated_shapes.append((z_index, shape, blob, placement, export_as_mp4))

    has_background_animation = any(
        export_as_mp4
        for _z_index, _shape, _blob, _placement_value, export_as_mp4 in animated_shapes
    )
    layer_index = 1 if has_background_animation else 2

    for z_index, shape, blob, placement, export_as_mp4 in animated_shapes:
        extension = 'mp4' if export_as_mp4 else 'png'
        full_canvas_filename = f'{slide_stem}_layer{layer_index}.{extension}'
        rotation = float(shape.rotation or 0.0)
        flip_h = _shape_transform_bool(shape, 'flipH')
        flip_v = _shape_transform_bool(shape, 'flipV')
        crop = _shape_crop(shape)
        opacity = _shape_opacity(shape)
        brightness, contrast = _shape_luminance(shape)
        saturation, grayscale = _shape_color_adjustments(shape)
        if export_as_mp4:
            print(
                f'{full_canvas_filename}: background-sized animation detected; '
                'exporting as H.264 MP4 with transparency composited over white.',
                flush=True,
            )

        _render_full_canvas_animation(
            blob,
            output_folder / full_canvas_filename,
            placement,
            rotation,
            flip_h,
            flip_v,
            crop,
            opacity,
            brightness,
            contrast,
            saturation,
            grayscale,
            export_as_mp4,
        )
        layers.append(
            SlideLayer(
                type='gif',
                shape_id=int(shape.shape_id),
                z_index=z_index,
                source_file=full_canvas_filename,
                placement=placement,
                rotation=rotation,
                flip_h=flip_h,
                flip_v=flip_v,
                full_canvas_file=full_canvas_filename,
            )
        )
        layer_index += 1

    return layers
