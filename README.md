# Stream Graphics Generator

Generate credit cards and lower-third section videos from a CSV file.

Requires Python 3.11, 3.12, or 3.13.

## Windows

Drag your CSV file onto `start.bat`.

If you run `start.bat` directly, it will ask you to drag or paste the CSV path into the terminal.

## macOS / Linux

Run:

```sh
sh start.sh
```

Then drag or paste the CSV path into the terminal.

You can also pass the CSV path directly:

```sh
sh start.sh path/to/credits.csv
```

## Options

If you do not pass an option, the app shows a menu where you can choose what to generate.

Use these options to skip the menu:

Windows:

```bat
start.bat path\to\credits.csv --all
start.bat path\to\credits.csv --credits
start.bat path\to\credits.csv --lowerthirds
```

macOS / Linux:

```sh
sh start.sh path/to/credits.csv --all
sh start.sh path/to/credits.csv --credits
sh start.sh path/to/credits.csv --lowerthirds
```

## Output

When generation finishes, the app opens the `output` folder.

Credit card PNGs are saved in `output/credits`.

Lower-third section videos are saved in `output/lower_thirds`.
