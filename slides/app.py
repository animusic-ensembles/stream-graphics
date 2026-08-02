from __future__ import annotations

from pathlib import Path
import argparse
import re
import shutil
from typing import Callable, Sequence

from input import resolve_pptx_input
from .inventory import inventory_presentation
from .gifs import extract_animated_gifs
from .models import Placement, SlideLayer
from .notes import slide_output_stems_from_notes
from .static_export import export_static_pngs
from .videos import extract_videos, slide_video_reason
from pptx import Presentation
from pptx.shapes.base import BaseShape


PROJECT_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_FOLDER = PROJECT_ROOT / 'output' / 'slides'
LAYER_FILENAME_PATTERN = re.compile(r'_layer(\d+)\.')


def clear_output() -> None:
    shutil.rmtree(OUTPUT_FOLDER, ignore_errors=True)
    OUTPUT_FOLDER.mkdir(parents=True, exist_ok=True)


def _next_layer_index(layers: Sequence[object]) -> int:
    layer_indexes = []
    for layer in layers:
        source_file = getattr(layer, 'source_file', '')
        match = LAYER_FILENAME_PATTERN.match(str(source_file))
        if match:
            layer_indexes.append(int(match.group(1)))
    return (max(layer_indexes) + 1) if layer_indexes else 1


def _shape_placement(shape: BaseShape, slide_width: int, slide_height: int) -> Placement:
    return Placement(
        x=round(int(shape.left) / slide_width * 1920),
        y=round(int(shape.top) / slide_height * 1080),
        width=round(int(shape.width) / slide_width * 1920),
        height=round(int(shape.height) / slide_height * 1080),
    )


def _placements_overlap(first: Placement, second: Placement) -> bool:
    first_right = first.x + first.width
    first_bottom = first.y + first.height
    second_right = second.x + second.width
    second_bottom = second.y + second.height

    return (
        first.x < second_right
        and first_right > second.x
        and first.y < second_bottom
        and first_bottom > second.y
    )


def _shape_overlaps_lower_animation(
        shape: BaseShape,
        z_index: int,
        animated_layers: list[SlideLayer],
        slide_width: int,
        slide_height: int,
) -> bool:
    placement = _shape_placement(shape, slide_width, slide_height)
    return any(
        layer.z_index < z_index and _placements_overlap(placement, layer.placement)
        for layer in animated_layers
    )


def write_inventory(pptx_path: Path, progress_callback: Callable[[int, int], None] | None = None) -> None:
    clear_output()
    inventories = inventory_presentation(pptx_path)
    presentation = Presentation(str(pptx_path))
    slide_stems = slide_output_stems_from_notes(pptx_path, len(inventories))
    removed_shape_ids_by_slide: list[set[int]] = []
    skipped_static_slide_indexes: set[int] = set()
    layered_static_slide_indexes: set[int] = set()
    transparent_static_layers_by_slide: dict[int, list[tuple[set[int], str]]] = {}
    current_progress = 0
    total_progress = len(inventories) * 2

    def mark_progress() -> None:
        nonlocal current_progress
        if not progress_callback:
            return

        current_progress += 1
        progress_callback(current_progress, total_progress)

    if progress_callback:
        progress_callback(0, total_progress)

    total_slides = len(inventories)
    for inventory, slide in zip(inventories, presentation.slides):
        slide_shapes = list(slide.shapes)
        video_reason = slide_video_reason(slide_shapes)
        output_index = inventory.slide_number - 1
        slide_stem = slide_stems[output_index]
        slide_label = f'Slide {inventory.slide_number}/{total_slides}'
        print(f'{slide_label} processing: {slide_stem}', flush=True)
        if video_reason:
            print(f'{slide_label} video detected: {video_reason}', flush=True)
            inventory.layers = extract_videos(
                slide_shapes,
                OUTPUT_FOLDER,
                slide_stem,
                inventory.slide_width,
                inventory.slide_height,
            )
            if not inventory.layers:
                raise RuntimeError(f'{slide_label}: video detected, but no video file could be downloaded or extracted.')
            skipped_static_slide_indexes.add(output_index)
            removed_shape_ids_by_slide.append(set())
            print(f'{slide_label} processed: {slide_stem}', flush=True)
            mark_progress()
            continue

        inventory.layers = extract_animated_gifs(
            slide_shapes,
            OUTPUT_FOLDER,
            slide_stem,
            inventory.slide_width,
            inventory.slide_height,
        )
        animated_shape_ids = {layer.shape_id for layer in inventory.layers if layer.type == 'gif'}
        removed_shape_ids_by_slide.append(animated_shape_ids)
        if animated_shape_ids:
            animated_layers = [layer for layer in inventory.layers if layer.type == 'gif']
            has_background_animation = any(layer.source_file == f'{slide_stem}_layer1.gif' for layer in inventory.layers)
            if not has_background_animation:
                layered_static_slide_indexes.add(output_index)

            upper_static_shape_ids = {
                int(shape.shape_id)
                for z_index, shape in enumerate(slide_shapes, start=1)
                if (
                    int(shape.shape_id) not in animated_shape_ids
                    and _shape_overlaps_lower_animation(
                        shape,
                        z_index,
                        animated_layers,
                        inventory.slide_width,
                        inventory.slide_height,
                    )
                )
            }
            if upper_static_shape_ids:
                static_layers = transparent_static_layers_by_slide.setdefault(output_index, [])
                base_static_shape_ids = {
                    int(shape.shape_id)
                    for shape in slide_shapes
                    if int(shape.shape_id) not in animated_shape_ids
                    and int(shape.shape_id) not in upper_static_shape_ids
                }
                if base_static_shape_ids and not has_background_animation:
                    static_layers.append((base_static_shape_ids, f'{slide_stem}_layer1.png'))
                static_layer_index = _next_layer_index(inventory.layers)
                static_layers.append((
                    upper_static_shape_ids,
                    f'{slide_stem}_layer{static_layer_index}.png',
                ))
                skipped_static_slide_indexes.add(output_index)
                layered_static_slide_indexes.discard(output_index)
        print(f'{slide_label} processed: {slide_stem}', flush=True)
        mark_progress()

    total_progress = (
        len(inventories)
        + (len(inventories) - len(skipped_static_slide_indexes))
        + sum(len(layers) for layers in transparent_static_layers_by_slide.values())
    )
    if progress_callback:
        progress_callback(current_progress, total_progress)

    export_static_pngs(
        pptx_path,
        OUTPUT_FOLDER,
        len(inventories),
        removed_shape_ids_by_slide,
        slide_stems,
        skipped_static_slide_indexes,
        layered_static_slide_indexes=layered_static_slide_indexes,
        transparent_static_layers_by_slide=transparent_static_layers_by_slide,
        progress_callback=mark_progress,
    )
    print(f'Wrote slide assets to {OUTPUT_FOLDER}.')


def generate(input_value: str, progress_callback: Callable[[int, int], None] | None = None) -> None:
    pptx_path = resolve_pptx_input(input_value)
    write_inventory(pptx_path, progress_callback)
