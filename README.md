# Stream Graphics Generator

Generate credit cards and lower-third section videos from a CSV file.

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

## Output

When generation finishes, the app opens the `output` folder.

Credit card PNGs are saved in `output/credits`.

Lower-third section videos are saved in `output/lower_thirds`.
