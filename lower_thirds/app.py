from manim import Scene, Line, Text, Rectangle, MoveToTarget, register_font, WHITE, BLACK, config as manim_config
from manim.constants import LEFT
from manim.mobject.mobject import Mobject
from manim.typing import Point3DLike
from pathlib import Path
import shutil
import re
from typing import Any, Callable, TypeVar, cast

T = TypeVar("T", bound=Mobject)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
FONTS_DIR = PROJECT_ROOT / 'fonts'

REGULAR_FONT_PATH = FONTS_DIR / 'InterDisplay-Regular.ttf'
LIGHT_FONT_PATH = FONTS_DIR / 'InterDisplay-Light.ttf'
FONT_NAME = "Inter Display"

output_folder = PROJECT_ROOT / 'output' / 'lower_thirds'
temp_folder = PROJECT_ROOT / 'media'


def _to_file_safe(s: str) -> str:
    return re.sub(r'[^\w.-]', '_', s)


def _section_output_name(path: Path) -> str:
    match = re.match(r'^.+?_(\d{4})_(.+)\.mp4$', path.name)
    if not match:
        return path.name

    index = int(match.group(1))
    section_name = _to_file_safe(match.group(2)).lower()
    return f'{index:02d}_{section_name}.mp4'


def _convert(x: float, y: float) -> Point3DLike:
    x1 = (x - 960) / 135
    y1 = (540 - y) / 135
    return (x1, y1, 0)


def _abs_convert(x: float) -> float:
    return x / 135


def _make_target(mobject: T) -> T:
    mobject.generate_target()
    return cast(T, cast(Any, mobject).target)


def _clear_old_videos() -> None:
    shutil.rmtree(temp_folder, ignore_errors=True)
    temp_folder.mkdir(parents=True, exist_ok=True)
    print('Lower thirds temp folder cleared.')

    shutil.rmtree(output_folder, ignore_errors=True)
    output_folder.mkdir(parents=True, exist_ok=True)
    print('Lower thirds output folder cleared.')


def _configure_manim_output() -> None:
    manim_config.save_sections = True
    manim_config.quality = 'high_quality'
    manim_config.media_dir = str(temp_folder)
    manim_config.verbosity = 'ERROR'
    manim_config.progress_bar = 'none'


def _copy_sections_to_output() -> None:
    section_folder = temp_folder / 'videos' / '1080p60' / 'sections'
    if not section_folder.exists():
        raise FileNotFoundError(f'No Manim sections folder was generated at {section_folder}.')

    for item in section_folder.iterdir():
        destination_name = _section_output_name(item) if item.suffix == '.mp4' else item.name
        destination = output_folder / destination_name
        if item.is_dir():
            shutil.copytree(item, destination, dirs_exist_ok=True)
        else:
            shutil.copy2(item, destination)


class LowerThird(Scene):
    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.setlist: list[tuple[str, str]] = []
        self.progress_callback: Callable[[int, int], None] | None = None
        self.progress_current = 0
        self.progress_total = 0


    def initialize(
            self,
            setlist: list[tuple[str, str]],
            progress_callback: Callable[[int, int], None] | None = None
    ) -> None:
        self.setlist = setlist
        self.progress_callback = progress_callback
        self.progress_current = 0
        self.progress_total = len(setlist) * 5 + 1


    def _mark_progress(self) -> None:
        if not self.progress_callback:
            return

        self.progress_current += 1
        self.progress_callback(self.progress_current, self.progress_total)


    def construct(self) -> None:
        for title, subtitle in self.setlist:
            self.next_section(_to_file_safe(title))
            self.render_lower_third(title, subtitle)

    def render_lower_third(self, title_text: str, subtitle_text: str) -> None:
        line = Line(start=_convert(100, 900), end=_convert(100, 900))
        line.set_stroke(color=WHITE, width=10)
        line_target = _make_target(line)
        line_target.put_start_and_end_on(_convert(100, 820), _convert(100, 980))
        with register_font(str(REGULAR_FONT_PATH)):
            title = Text(title_text, font=FONT_NAME, height=_abs_convert(60), fill_opacity=0).move_to(_convert(-80, 900-30), aligned_edge=LEFT)

        with register_font(str(LIGHT_FONT_PATH)):
            subtitle = Text(subtitle_text, font=FONT_NAME, height=_abs_convert(40), fill_opacity=0).move_to(_convert(-80, 900+40), aligned_edge=LEFT)
                
        overlay = Rectangle(color=BLACK, height=_abs_convert(160), width=_abs_convert(100)).move_to(_convert(40, 900))
        overlay.set_fill(color=BLACK, opacity=1)

        title_target = _make_target(title)
        title_target.set_fill(opacity=1)
        title_target.move_to(_convert(150, 900-30), aligned_edge=LEFT)
        subtitle_target = _make_target(subtitle)
        subtitle_target.set_fill(opacity=1)
        subtitle_target.move_to(_convert(150, 900+40), aligned_edge=LEFT)

        self.add(line)
        self.play(MoveToTarget(line))
        self._mark_progress()
        self.add(title)
        self.add(subtitle)
        self.add(overlay)
        self.play(MoveToTarget(title), MoveToTarget(subtitle))
        self._mark_progress()
        self.wait(2)
        self._mark_progress()

        title_target = _make_target(title)
        title_target.set_fill(opacity=0)
        title_target.move_to(_convert(-80, 900-30), aligned_edge=LEFT)
        subtitle_target = _make_target(subtitle)
        subtitle_target.set_fill(opacity=0)
        subtitle_target.move_to(_convert(-80, 900+40), aligned_edge=LEFT)
        line_target = _make_target(line)
        line_target.put_start_and_end_on(_convert(100, 900), _convert(100, 900))
        self.play(MoveToTarget(title), MoveToTarget(subtitle))
        self._mark_progress()
        self.play(MoveToTarget(line))
        self._mark_progress()


def generate(setlist: list[tuple[str, str]], progress_callback: Callable[[int, int], None] | None = None) -> None:
    _configure_manim_output()
    _clear_old_videos()
    lower_thirds = LowerThird()
    lower_thirds.initialize(setlist, progress_callback)
    lower_thirds.render()
    if progress_callback:
        progress_callback(lower_thirds.progress_total, lower_thirds.progress_total)
    _copy_sections_to_output()

    print('All lower thirds generated successfully.')
