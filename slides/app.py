from __future__ import annotations

from pathlib import Path
import argparse
import shutil
from typing import Callable

from input import resolve_pptx_input
from .inventory import inventory_presentation
from .gifs import extract_animated_gifs
from .static_export import export_static_pngs
from .videos import extract_videos, slide_video_reason
from pptx import Presentation


PROJECT_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_FOLDER = PROJECT_ROOT / 'output' / 'slides'


def clear_output() -> None:
    shutil.rmtree(OUTPUT_FOLDER, ignore_errors=True)
    OUTPUT_FOLDER.mkdir(parents=True, exist_ok=True)


def write_inventory(pptx_path: Path, progress_callback: Callable[[int, int], None] | None = None) -> None:
    clear_output()
    inventories = inventory_presentation(pptx_path)
    presentation = Presentation(str(pptx_path))
    removed_shape_ids_by_slide: list[set[int]] = []
    skipped_static_slide_indexes: set[int] = set()
    transparent_overlay_shape_ids_by_slide: dict[int, tuple[set[int], str]] = {}
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

    for inventory, slide in zip(inventories, presentation.slides):
        slide_shapes = list(slide.shapes)
        video_reason = slide_video_reason(slide_shapes)
        slide_label = f'slide {inventory.slide_number:02d} / output {inventory.slide_number - 1:02d}'
        if video_reason:
            print(f'{slide_label}: video detected ({video_reason}); downloading/extracting.', flush=True)
            inventory.layers = extract_videos(
                slide_shapes,
                OUTPUT_FOLDER,
                inventory.slide_number - 1,
                inventory.slide_width,
                inventory.slide_height,
            )
            if not inventory.layers:
                raise RuntimeError(f'{slide_label}: video detected, but no video file could be downloaded or extracted.')
            skipped_static_slide_indexes.add(inventory.slide_number - 1)
            removed_shape_ids_by_slide.append(set())
            mark_progress()
            continue
        print(f'{slide_label}: no video detected.', flush=True)

        inventory.layers = extract_animated_gifs(
            slide_shapes,
            OUTPUT_FOLDER,
            inventory.slide_number - 1,
            inventory.slide_width,
            inventory.slide_height,
        )
        animated_shape_ids = {layer.shape_id for layer in inventory.layers if layer.type == 'gif'}
        removed_shape_ids_by_slide.append(animated_shape_ids)
        if animated_shape_ids:
            lowest_animated_z_index = min(layer.z_index for layer in inventory.layers if layer.type == 'gif')
            static_shape_ids_above_animation = {
                int(shape.shape_id)
                for z_index, shape in enumerate(slide_shapes, start=1)
                if z_index > lowest_animated_z_index and int(shape.shape_id) not in animated_shape_ids
            }
            if static_shape_ids_above_animation:
                output_index = inventory.slide_number - 1
                static_layer_index = len(inventory.layers) + 1
                transparent_overlay_shape_ids_by_slide[output_index] = (
                    static_shape_ids_above_animation,
                    f'{output_index:02d}_layer{static_layer_index}.png',
                )
                skipped_static_slide_indexes.add(output_index)
        mark_progress()

    total_progress = (
        len(inventories)
        + (len(inventories) - len(skipped_static_slide_indexes))
        + len(transparent_overlay_shape_ids_by_slide)
    )
    if progress_callback:
        progress_callback(current_progress, total_progress)

    export_static_pngs(
        pptx_path,
        OUTPUT_FOLDER,
        len(inventories),
        removed_shape_ids_by_slide,
        skipped_static_slide_indexes,
        transparent_overlay_shape_ids_by_slide,
        mark_progress,
    )
    print(f'Wrote slide assets to {OUTPUT_FOLDER}.')


def generate(input_value: str, progress_callback: Callable[[int, int], None] | None = None) -> None:
    pptx_path = resolve_pptx_input(input_value)
    write_inventory(pptx_path, progress_callback)
