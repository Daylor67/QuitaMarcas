"""
folder_scan_service - Funciones puras de escaneo de carpetas (Phase 3, Plan 03-01).

Consolida el patrón repetido `natsorted(folder.iterdir()) + filtro de
extensiones` que aparece en 3 lugares del módulo WatermarkRemove:
- `NavigationController._load_image_list` (navigation_controller.py:234-247)
- `ImageViewer._load_images` (image_viewer.py:93-101)
- `PositionEditor._load_images` (position_editor.py:401-412)
- `PositionEditor._load_watermark_folders` (position_editor.py:374-387, dir scan)
- `PositionEditor._load_watermarks_into_combo` (position_editor.py:414-427, .png filter)

Funciones puras: sin Qt, sin estado mutable. Cada llamada recibe un Path
+ una tupla de formatos y retorna una lista nueva. La elección de qué tupla
de formatos pasar la conserva cada widget (image_viewer incluye `.psd/.psb`,
editor/nav no — RESEARCH PATTERNS L104).
"""
from pathlib import Path

from natsort import natsorted


def scan_images(folder: Path, formats: tuple) -> list[Path]:
    """Lista archivos de imagen en `folder` filtrados por extensión.

    Si `folder` apunta a un archivo (no a un directorio), reasigna a su
    carpeta padre — preserva el comportamiento de
    `NavigationController._load_image_list` L235-236.

    Args:
        folder: Path a una carpeta (o a un archivo dentro de la carpeta).
        formats: tupla de extensiones en minúsculas, incluido el punto
            (ej. ('.png', '.jpg', '.jpeg', '.webp')).

    Returns:
        Lista de Paths ordenada con `natsorted`, solo archivos cuya
        extensión (lowercase) pertenezca a `formats`.
    """
    if folder.is_file():
        folder = folder.parent
    return [
        f for f in natsorted(folder.iterdir())
        if f.is_file() and f.suffix.lower() in formats
    ]


def scan_pngs(folder: Path) -> list[Path]:
    """Lista exclusivamente los `.png` de `folder` (para el combo de marcas).

    Equivalente especializado de `scan_images` con el filtro fijo a `.png`.
    Reemplaza el bloque inline de `PositionEditor._load_watermarks_into_combo`
    L414-427.

    Args:
        folder: Path a la carpeta a escanear (o a un archivo dentro).

    Returns:
        Lista de Paths `.png` ordenada con `natsorted`.
    """
    if folder.is_file():
        folder = folder.parent
    return [
        f for f in natsorted(folder.iterdir())
        if f.is_file() and f.suffix.lower() == '.png'
    ]


def scan_subfolders(base: Path) -> list[Path]:
    """Lista las subcarpetas inmediatas de `base`, ordenadas en reverse.

    Reemplaza el bloque inline de `PositionEditor._load_watermark_folders`
    L382-383, preservando el orden reverse (más recientes primero, por
    nombre alfabético descendente).

    Args:
        base: Path a la carpeta raíz cuyas subcarpetas se listarán.

    Returns:
        Lista de Paths de subdirectorios, ordenada en reverse.

    Raises:
        PermissionError: si el sistema no permite listar el directorio.
        OSError: si el path no es accesible.
    """
    folders = [f for f in base.iterdir() if f.is_dir()]
    folders.sort(reverse=True)
    return folders
