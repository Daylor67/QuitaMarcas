import sys
from cx_Freeze import setup, Executable

# Versión de la aplicación
APP_VERSION = "3.1.0"
APP_NAME = "SmartStitch WR"
APP_AUTHOR = "Daylor67"
APP_DESCRIPTION = "SmartStitch con eliminación de marcas de agua"

# Archivos adicionales que deben incluirse
include_files = [
    ("assets", "lib/assets"),
    ("gui/layout.ui", "lib/gui/layout.ui"),
    ("WatermarkRemove/marcas", "lib/WatermarkRemove/marcas"),
]

# Paquetes que deben incluirse explícitamente
packages = [
    "natsort",
    "PIL",
    "cv2",
    "PySide6",
    "psd_tools",
    "numpy",
]

# Módulos que deben incluirse
includes = [
    "qdarktheme",
    "gui.launcher",
    "gui.controller",
    "gui.process",
    "gui.stylesheet",
    "core.detectors.pixel_comparison",
    "core.detectors.direct_slicing",
    "core.models.app_profiles",
    "core.models.app_settings",
    "core.models.work_directory",
    "core.services.settings_handler",
    "core.services.global_logger",
    "core.services.image_handler",
    "core.services.image_manipulator",
    "core.services.directory_explorer",
    "core.utils.constants",
    "WatermarkRemove",
    "WatermarkRemove.wm_remove",
    "WatermarkRemove.ui.position_editor",
    "WatermarkRemove.ui.slideshow_viewer",
    "utils.json_utils",
]

# Módulos que deben excluirse para reducir tamaño
excludes = [
    "tkinter",
    "matplotlib",
    "scipy",
    "pandas",
    "unittest",
    "test",
    "setuptools",
]

# Opciones de build
build_exe_options = {
    "packages": packages,
    "includes": includes,
    "excludes": excludes,
    "include_files": include_files,
    "optimize": 2,
    "include_msvcr": True,
}

# Opciones para crear el MSI
bdist_msi_options = {
    "upgrade_code": "{12345678-1234-1234-1234-123456789012}",  # Genera uno único para tu app
    "add_to_path": False,
    "initial_target_dir": f"[ProgramFilesFolder]\\{APP_NAME}",
    "install_icon": "assets/SmartStitchLogo.ico",
}

# Configuración base para Windows GUI
base = None
if sys.platform == "win32":
    base = "Win32GUI"  # Oculta la consola en Windows

# Ejecutable principal
executables = [
    Executable(
        "SmartStitchGUI.py",
        base=base,
        target_name="SmartStitch.exe",
        icon="assets/SmartStitchLogo.ico",
        shortcut_name=APP_NAME,
        shortcut_dir="DesktopFolder",
    )
]

# Setup
setup(
    name=APP_NAME,
    version=APP_VERSION,
    description=APP_DESCRIPTION,
    author=APP_AUTHOR,
    options={
        "build_exe": build_exe_options,
        "bdist_msi": bdist_msi_options,
    },
    executables=executables,
)
