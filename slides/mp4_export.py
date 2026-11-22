from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path
import shutil
import subprocess
import tempfile

from PIL import Image

from .inventory import OUTPUT_HEIGHT, OUTPUT_WIDTH


def save_background_mp4(
        frames: Iterable[tuple[Image.Image, int]],
        output_path: Path,
        frame_duration_ms: int,
) -> None:
    """Stream one animation cycle to H.264 MP4, compositing transparency over white."""
    executable = shutil.which('ffmpeg')
    if not executable:
        raise FileNotFoundError('FFmpeg is required to export animated backgrounds as MP4. Run the launcher to install it.')

    if frame_duration_ms <= 0:
        raise ValueError('Video frame duration must be positive.')

    # Keep diagnostics off a pipe so FFmpeg cannot block while we write frames.
    # Stage beside the destination so a failed encode never replaces a good file.
    with tempfile.TemporaryDirectory(prefix='stream_graphics_mp4_', dir=output_path.parent) as temp_dir:
        temporary_path = Path(temp_dir) / output_path.name
        with tempfile.TemporaryFile() as error_output:
            process = subprocess.Popen(
                [
                    executable, '-hide_banner', '-loglevel', 'error', '-y',
                    '-f', 'rawvideo', '-pixel_format', 'rgb24',
                    '-video_size', f'{OUTPUT_WIDTH}x{OUTPUT_HEIGHT}',
                    '-framerate', f'1000/{frame_duration_ms}', '-i', 'pipe:0',
                    '-an', '-c:v', 'libx264', '-preset', 'medium', '-crf', '18',
                    '-pix_fmt', 'yuv420p', '-movflags', '+faststart',
                    str(temporary_path),
                ],
                stdin=subprocess.PIPE,
                stdout=subprocess.DEVNULL,
                stderr=error_output,
            )
            assert process.stdin is not None
            frame_count = 0
            try:
                for frame, duration in frames:
                    if frame.size != (OUTPUT_WIDTH, OUTPUT_HEIGHT):
                        raise ValueError(f'{output_path.name}: video frames must be 1920x1080.')
                    if duration <= 0 or duration % frame_duration_ms:
                        raise ValueError('Animation duration must be a positive multiple of the video frame duration.')

                    rgba = frame.convert('RGBA')
                    opaque = Image.new('RGB', rgba.size, (255, 255, 255))
                    opaque.paste(rgba, mask=rgba.getchannel('A'))
                    pixels = opaque.tobytes()
                    # The common divisor of GIF delays gives exact timing without
                    # forcing every animation to an unnecessarily high frame rate.
                    for _ in range(duration // frame_duration_ms):
                        process.stdin.write(pixels)
                        frame_count += 1

                process.stdin.close()
                returncode = process.wait()
            except BaseException as error:
                # Closing input lets FFmpeg exit cleanly, including installations
                # launched through a wrapper such as a Windows Chocolatey shim.
                try:
                    process.stdin.close()
                except BrokenPipeError:
                    pass
                process.wait()
                if isinstance(error, BrokenPipeError):
                    error_output.seek(0)
                    details = error_output.read().decode('utf-8', errors='replace').strip()
                    raise RuntimeError(f'FFmpeg failed to encode {output_path.name}: {details}') from error
                raise
            finally:
                if not process.stdin.closed:
                    try:
                        process.stdin.close()
                    except BrokenPipeError:
                        pass

            if returncode != 0:
                error_output.seek(0)
                details = error_output.read().decode('utf-8', errors='replace').strip()
                raise RuntimeError(f'FFmpeg failed to encode {output_path.name}: {details}')
            if not frame_count or not temporary_path.is_file() or temporary_path.stat().st_size == 0:
                raise RuntimeError(f'{output_path.name} had no animation frames to encode.')

        temporary_path.replace(output_path)
