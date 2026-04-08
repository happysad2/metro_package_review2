@echo off
:: ============================================================
::  Metro Package Review — Build Script
:: ============================================================
::  Produces:  dist\MetroPackageReview.exe
::
::  Prerequisites:
::    pip install pyinstaller PySide6 openpyxl Pillow
::
::  Usage:
::    build.bat
:: ============================================================

echo.
echo  ========================================
echo   Building Metro Package Review
echo  ========================================
echo.

:: Clean previous build artifacts
if exist build rmdir /s /q build
if exist dist  rmdir /s /q dist

:: Run PyInstaller
pyinstaller build.spec --noconfirm --clean

echo.
if exist "dist\MetroPackageReview.exe" (
    echo  BUILD SUCCESSFUL
    echo  Output: dist\MetroPackageReview.exe
    echo.
    echo  To distribute:
    echo    1. Copy dist\MetroPackageReview.exe to the target machine
    echo    2. Create an "inputs" folder next to the exe
    echo    3. Drop deliverable files into inputs\
    echo    4. Run MetroPackageReview.exe
    echo.
    echo  The exe creates "inputs" and "outputs" folders automatically
    echo  if they don't exist. Reference docs are bundled inside.
) else (
    echo  BUILD FAILED — check errors above
)
echo.
pause
