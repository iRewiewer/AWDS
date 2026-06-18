#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

if ! command -v xelatex >/dev/null 2>&1; then
    echo "ERROR: xelatex was not found on PATH." >&2
    exit 1
fi

tex_flags=(-interaction=nonstopmode -halt-on-error)

for tex_file in main_ro.tex main_en.tex; do
    echo "Building ${tex_file}..."
    xelatex "${tex_flags[@]}" "${tex_file}"
    xelatex "${tex_flags[@]}" "${tex_file}"
done

rm -f main_ro.aux main_ro.log main_ro.out main_ro.toc
rm -f main_en.aux main_en.log main_en.out main_en.toc

echo "Done. Generated main_ro.pdf and main_en.pdf."
