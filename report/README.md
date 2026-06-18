# AWDS Report Sources

This folder contains two LaTeX variants of the prototype report:

- `main_ro.tex` - Romanian version
- `main_en.tex` - English version

The results section is intentionally a skeleton. Fill it after running the final scenarios and exporting figures from the AWDS dashboard.

## Build

From this folder, run the platform script:

```bat
build.bat
```

```bash
./build.sh
```

Both scripts compile `main_ro.tex` and `main_en.tex` with XeLaTeX, run a second pass for the table of contents, and remove auxiliary files after a successful build.

You can also upload the folder to Overleaf and compile either `.tex` file there. Use XeLaTeX because the reports use Unicode text and `fontspec`.

## Figures

Put exported PNG charts from the application in `figures/`, then replace the placeholder figure blocks in the results section with `\includegraphics` commands.
