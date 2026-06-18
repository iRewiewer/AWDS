@echo off
setlocal

pushd "%~dp0" || exit /b 1

where xelatex >nul 2>nul
if errorlevel 1 (
    echo ERROR: xelatex was not found on PATH.
    popd
    exit /b 1
)

set "TEX_FLAGS=-interaction=nonstopmode -halt-on-error"

for %%F in (main_ro.tex main_en.tex) do (
    echo Building %%F...
    xelatex %TEX_FLAGS% "%%F"
    if errorlevel 1 (
        echo ERROR: Build failed for %%F.
        popd
        exit /b 1
    )

    xelatex %TEX_FLAGS% "%%F"
    if errorlevel 1 (
        echo ERROR: Build failed for %%F on the second pass.
        popd
        exit /b 1
    )
)

for %%F in (main_ro main_en) do (
    for %%E in (aux log out toc) do (
        if exist "%%F.%%E" del /q "%%F.%%E"
    )
)

echo Done. Generated main_ro.pdf and main_en.pdf.
popd
endlocal
