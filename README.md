# Stream Graphics Generator

Generate credit cards, lower-third section videos, and slide assets.

Requires Python 3.11, 3.12, 3.13, or 3.14.

## Windows

Drag your CSV file onto `start.bat`.

If you run `start.bat` directly, it will ask what to generate, then ask for the required input files or public Google links.

## macOS / Linux

Run:

```sh
sh start.sh
```

Then choose what to generate and provide the requested input files or public Google links.

You can also pass input paths directly:

```sh
sh start.sh path/to/credits.csv
```

Google Sheets and Google Slides links must be public. Private links fail before generation starts.

## Options

If you do not pass an option, the app shows a menu where you can choose what to generate.

Use these options to skip the menu:

Windows:

```bat
start.bat path\to\credits.csv --all
start.bat path\to\credits.csv --credits
start.bat path\to\credits.csv --lowerthirds
start.bat path\to\slides.pptx --slides
start.bat path\to\credits.csv --all --slides-input path\to\slides.pptx
```

macOS / Linux:

```sh
sh start.sh path/to/credits.csv --all
sh start.sh path/to/credits.csv --credits
sh start.sh path/to/credits.csv --lowerthirds
sh start.sh path/to/slides.pptx --slides
sh start.sh path/to/credits.csv --all --slides-input path/to/slides.pptx
```

## Output

When generation finishes, the app opens the `output` folder.

Credit card PNGs are saved in `output/credits`.

Lower-third section videos are saved in `output/lower_thirds`.

Slide assets are saved in `output/slides`.
