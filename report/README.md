# AWDS Report Sources

This folder contains two LaTeX variants of the prototype report:

- `main_ro.tex` - Romanian version
- `main_en.tex` - English version

The results section is intentionally a skeleton. Fill it after running the final scenarios and exporting figures from the AWDS dashboard.

## Suggested Build Commands

Tectonic is the recommended local compiler for this report because it is smaller than a full TeX distribution and fetches required packages automatically:

```bash
tectonic main_ro.tex
```

```bash
tectonic main_en.tex
```

You can also upload the folder to Overleaf and compile either `.tex` file there. If using a traditional LaTeX distribution, compile each file with XeLaTeX because the reports use Unicode text and `fontspec`.

## Figures

Put exported PNG charts from the application in `figures/`, then replace the placeholder figure blocks in the results section with `\includegraphics` commands.
