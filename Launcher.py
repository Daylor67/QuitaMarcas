"""
Launcher independiente para SmartStitch WR.
Verifica actualizaciones ANTES de lanzar la app principal.

Imports permitidos: solo módulos auto-contenidos (UpdateChecker, UpdateDialog).
SettingsHandler queda desacoplado — UpdateDialog lo carga defensivamente.
"""
import os
import sys
import subprocess

from PySide6.QtWidgets import QApplication

from core.services.update_checker import UpdateChecker
from gui.update_dialog import UpdateDialog


APP_EXE = "main.exe"


def get_app_dir():
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def launch_app(app_dir):
    exe_path = os.path.join(app_dir, APP_EXE)
    args = [exe_path] + sys.argv[1:]  # Pasar argumentos (ej. ruta desde menú contextual)
    subprocess.Popen(args)


def main():
    app = QApplication(sys.argv)
    app_dir = get_app_dir()

    updater = UpdateChecker()
    has_update, latest_version, download_url, release_notes = updater.check_for_updates()

    if has_update and download_url:
        dialog = UpdateDialog(
            None,
            updater.current_version,
            latest_version,
            download_url,
            release_notes or "",
        )
        # Si el usuario acepta y la actualización se aplica, UpdateDialog hace sys.exit(0)
        # y el .bat relanza SmartStitch.exe tras copiar archivos.
        dialog.exec()

    launch_app(app_dir)


if __name__ == "__main__":
    main()
