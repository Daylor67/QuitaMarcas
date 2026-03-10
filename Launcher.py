"""
Launcher independiente para SmartStitch WR.
Verifica actualizaciones ANTES de lanzar la app principal.
No importa nada de la app principal para evitar sus errores de inicio.
"""
import os
import sys
import json
import zipfile
import tempfile
import subprocess
from urllib.request import urlopen, Request

from PySide6.QtWidgets import QApplication, QMessageBox, QProgressDialog
from PySide6.QtCore import Qt
from packaging import version as pkg_version


GITHUB_API_URL = "https://api.github.com/repos/Daylor67/QuitaMarcas/releases/latest"
APP_EXE = "main.exe"
VERSION_FILE = "version.txt"


def get_app_dir():
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def get_current_version(app_dir):
    try:
        with open(os.path.join(app_dir, VERSION_FILE), encoding='utf-8') as f:
            return f.read().strip()
    except Exception:
        return "0.0.0"


def check_updates(current_version):
    try:
        req = Request(GITHUB_API_URL)
        req.add_header('Accept', 'application/vnd.github.v3+json')
        with urlopen(req, timeout=5) as response:
            data = json.loads(response.read().decode())

        latest_version = data['tag_name'].lstrip('vV')

        download_url = None
        for asset in data.get('assets', []):
            if asset['name'].endswith('-win64.zip'):
                download_url = asset['browser_download_url']
                break

        if not download_url:
            return False, None, None

        has_update = pkg_version.parse(latest_version) > pkg_version.parse(current_version)
        return has_update, latest_version, download_url

    except Exception:
        return False, None, None


def download_and_apply(download_url, app_dir):
    progress = QProgressDialog("Descargando actualización...", "Cancelar", 0, 100)
    progress.setWindowTitle("Actualizando SmartStitch WR")
    progress.setWindowModality(Qt.WindowModality.ApplicationModal)
    progress.show()

    try:
        req = Request(download_url)
        req.add_header('Accept', 'application/octet-stream')

        temp_zip = tempfile.NamedTemporaryFile(delete=False, suffix='.zip')
        temp_path = temp_zip.name
        temp_zip.close()

        with urlopen(req, timeout=60) as response:
            total = int(response.headers.get('content-length', 0))
            downloaded = 0

            with open(temp_path, 'wb') as f:
                while True:
                    if progress.wasCanceled():
                        return False
                    chunk = response.read(8192)
                    if not chunk:
                        break
                    f.write(chunk)
                    downloaded += len(chunk)
                    if total:
                        progress.setValue(int(downloaded / total * 90))

        progress.setLabelText("Extrayendo...")
        progress.setValue(95)

        temp_extract = tempfile.mkdtemp()
        with zipfile.ZipFile(temp_path, 'r') as zf:
            zf.extractall(temp_extract)

        progress.setValue(100)
        progress.close()

        # Script bat que reemplaza archivos y relanza via SmartStitch.exe
        launcher_exe = os.path.join(app_dir, "SmartStitch.exe")
        script_path = os.path.join(tempfile.gettempdir(), 'update_smartstitch.bat')
        script = f'''@echo off
echo Aplicando actualizacion...
timeout /t 2 /nobreak >nul
xcopy /E /I /Y "{temp_extract}\\*" "{app_dir}\\"
rmdir /S /Q "{temp_extract}"
del /F /Q "{temp_path}"
start "" "{launcher_exe}"
del "%~f0"
'''
        with open(script_path, 'w') as f:
            f.write(script)

        subprocess.Popen(['cmd', '/c', script_path], creationflags=subprocess.CREATE_NO_WINDOW)
        return True

    except Exception as e:
        progress.close()
        QMessageBox.critical(None, "Error", f"No se pudo descargar la actualización:\n{e}")
        return False


def launch_app(app_dir):
    exe_path = os.path.join(app_dir, APP_EXE)
    args = [exe_path] + sys.argv[1:]  # Pasar argumentos (ej. ruta desde menú contextual)
    subprocess.Popen(args)


def main():
    app = QApplication(sys.argv)
    app_dir = get_app_dir()
    current_version = get_current_version(app_dir)

    has_update, latest_version, download_url = check_updates(current_version)

    if has_update and download_url:
        reply = QMessageBox.question(
            None,
            "Actualización disponible",
            f"Nueva versión disponible: v{latest_version}\n"
            f"Versión actual: v{current_version}\n\n"
            "¿Deseas actualizar ahora?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            updated = download_and_apply(download_url, app_dir)
            if updated:
                sys.exit(0)  # El bat relanza SmartStitch.exe tras actualizar

    launch_app(app_dir)


if __name__ == "__main__":
    main()
