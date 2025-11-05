"""
Módulo para verificar y descargar actualizaciones desde GitHub Releases
"""

import os
import sys
import json
import shutil
import zipfile
import tempfile
import subprocess
from urllib.request import urlopen, Request
from urllib.error import URLError
from packaging import version

from core.utils.version import APP_VERSION, GITHUB_API_URL


class UpdateChecker:
    """Verifica y descarga actualizaciones desde GitHub Releases"""

    def __init__(self):
        self.current_version = APP_VERSION
        self.latest_release = None

    def check_for_updates(self):
        """
        Verifica si hay una nueva versión disponible

        Returns:
            tuple: (has_update: bool, latest_version: str, download_url: str, release_notes: str)
        """
        try:
            # Solo buscar actualizaciones en Windows (donde hay ejecutable compilado)
            if sys.platform != "win32":
                print("Auto-actualización solo disponible en Windows")
                return False, None, None, None

            # Hacer petición a la API de GitHub
            req = Request(GITHUB_API_URL)
            req.add_header('Accept', 'application/vnd.github.v3+json')

            with urlopen(req, timeout=5) as response:
                data = json.loads(response.read().decode())

            self.latest_release = data
            latest_version = data['tag_name'].replace('v', '')

            # Buscar el archivo ZIP de Windows
            download_url = None
            for asset in data.get('assets', []):
                if asset['name'].endswith('-win64.zip'):
                    download_url = asset['browser_download_url']
                    break

            if not download_url:
                return False, None, None, None

            # Comparar versiones
            has_update = self._compare_versions(latest_version, self.current_version)

            release_notes = data.get('body', 'No hay notas de la versión disponibles.')

            return has_update, latest_version, download_url, release_notes

        except (URLError, json.JSONDecodeError, KeyError) as e:
            print(f"Error al verificar actualizaciones: {e}")
            return False, None, None, None

    def _compare_versions(self, latest, current):
        """
        Compara dos versiones

        Args:
            latest (str): Versión más reciente
            current (str): Versión actual

        Returns:
            bool: True si latest > current
        """
        try:
            # Limpiar versiones (remover sufijos como -beta, -alpha)
            latest_clean = latest.split('-')[0]
            current_clean = current.split('-')[0]

            return version.parse(latest_clean) > version.parse(current_clean)
        except:
            # Si falla el parsing, comparar como strings
            return latest != current

    def download_update(self, download_url, progress_callback=None):
        """
        Descarga la actualización

        Args:
            download_url (str): URL del archivo a descargar
            progress_callback (callable): Función para reportar progreso (recibe bytes descargados y total)

        Returns:
            str: Ruta del archivo descargado o None si falló
        """
        try:
            # Crear archivo temporal
            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.zip')
            temp_path = temp_file.name
            temp_file.close()

            # Descargar archivo
            req = Request(download_url)
            req.add_header('Accept', 'application/octet-stream')

            with urlopen(req, timeout=30) as response:
                total_size = int(response.headers.get('content-length', 0))
                downloaded = 0
                chunk_size = 8192

                with open(temp_path, 'wb') as f:
                    while True:
                        chunk = response.read(chunk_size)
                        if not chunk:
                            break
                        f.write(chunk)
                        downloaded += len(chunk)

                        if progress_callback:
                            progress_callback(downloaded, total_size)

            return temp_path

        except Exception as e:
            print(f"Error al descargar actualización: {e}")
            return None

    def apply_update(self, zip_path):
        """
        Aplica la actualización

        Args:
            zip_path (str): Ruta del archivo ZIP descargado

        Returns:
            bool: True si se aplicó correctamente
        """
        try:
            # Obtener directorio de la aplicación
            if getattr(sys, 'frozen', False):
                app_dir = os.path.dirname(sys.executable)
            else:
                app_dir = os.path.dirname(os.path.abspath(__file__))

            # Crear carpeta temporal para extraer
            temp_extract_dir = tempfile.mkdtemp()

            # Extraer ZIP
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(temp_extract_dir)

            # Crear script de actualización
            update_script = self._create_update_script(temp_extract_dir, app_dir)

            # Ejecutar script y cerrar aplicación
            if sys.platform == 'win32':
                subprocess.Popen(['cmd', '/c', update_script],
                               creationflags=subprocess.CREATE_NO_WINDOW)
            else:
                subprocess.Popen(['sh', update_script])

            return True

        except Exception as e:
            print(f"Error al aplicar actualización: {e}")
            return False

    def _create_update_script(self, source_dir, target_dir):
        """
        Crea un script para aplicar la actualización después de cerrar la app

        Args:
            source_dir (str): Directorio con los nuevos archivos
            target_dir (str): Directorio de la aplicación

        Returns:
            str: Ruta del script creado
        """
        if sys.platform == 'win32':
            script_path = os.path.join(tempfile.gettempdir(), 'update_smartstitch.bat')

            script_content = f'''@echo off
echo Aplicando actualizacion...
timeout /t 2 /nobreak >nul

REM Eliminar archivos antiguos (excepto configuracion)
for %%F in ("{target_dir}\\*") do (
    if not "%%~nxF"=="__settings__" (
        if not "%%~nxF"=="__logs__" (
            del /F /Q "%%F" 2>nul
        )
    )
)

REM Copiar nuevos archivos
xcopy /E /I /Y "{source_dir}\\*" "{target_dir}\\"

REM Limpiar archivos temporales
rmdir /S /Q "{source_dir}"

REM Reiniciar aplicación
start "" "{target_dir}\\SmartStitch.exe"

REM Eliminar este script
del "%~f0"
'''
        else:
            script_path = os.path.join(tempfile.gettempdir(), 'update_smartstitch.sh')

            script_content = f'''#!/bin/bash
echo "Aplicando actualización..."
sleep 2

# Copiar nuevos archivos
cp -rf "{source_dir}"/* "{target_dir}/"

# Limpiar
rm -rf "{source_dir}"

# Reiniciar aplicación
"{target_dir}/SmartStitch" &

# Eliminar este script
rm "$0"
'''

        with open(script_path, 'w') as f:
            f.write(script_content)

        if sys.platform != 'win32':
            os.chmod(script_path, 0o755)

        return script_path
