"""
Script para compilar y empaquetar SmartStitch WR en un ZIP para distribución
"""
import os
import sys
import shutil
import zipfile
import subprocess
from pathlib import Path
from core.utils.version import APP_VERSION, APP_NAME

def main():
    print(f"=== Compilando {APP_NAME} v{APP_VERSION} ===\n")
    
    # 1. Limpiar la carpeta de build
    build_dir = Path("build")
    if  build_dir.exists():
        shutil.rmtree(build_dir, ignore_errors=True)

    # 2. Ejecutar build
    print("Paso 1: Ejecutando python setup.py build...")
    result = subprocess.run([sys.executable, "setup.py", "build"], capture_output=True, text=True)

    if result.returncode != 0:
        print(f"❌ Error durante el build:")
        print(result.stderr)
        return False

    print("✅ Build completado exitosamente\n")


    # Buscar la carpeta exe.win-amd64-x.x
    exe_folders = list(build_dir.glob("exe.win-*"))
    if not exe_folders:
        print("❌ No se encontró ninguna carpeta de ejecutable en 'build'")
        return False

    original_folder = exe_folders[0]
    print(f"Paso 2: Carpeta de build encontrada: {original_folder.name}")

    # 3. Renombrar la carpeta
    new_folder_name = f"{APP_NAME} {APP_VERSION}"
    new_folder_path = build_dir / new_folder_name

    # Si ya existe la carpeta con el nuevo nombre, eliminarla
    if new_folder_path.exists():
        print(f"Eliminando carpeta existente: {new_folder_name}")
        shutil.rmtree(new_folder_path)

    print(f"Renombrando carpeta a: {new_folder_name}")
    shutil.move(str(original_folder), str(new_folder_path))
    print("✅ Carpeta renombrada exitosamente\n")

    # 4. Crear el ZIP
    zip_name = f"{APP_NAME}-{APP_VERSION}-win64.zip"
    zip_path = Path(zip_name)

    # Eliminar ZIP anterior si existe
    if zip_path.exists():
        print(f"Eliminando ZIP anterior: {zip_name}")
        zip_path.unlink()

    print(f"Paso 3: Creando archivo ZIP: {zip_name}")

    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        # Recorrer todos los archivos en la carpeta
        for root, dirs, files in os.walk(new_folder_path):
            for file in files:
                file_path = Path(root) / file
                # Calcular ruta relativa dentro del ZIP
                arcname = file_path.relative_to(build_dir)
                zipf.write(file_path, arcname)

    file_size_mb = zip_path.stat().st_size / (1024 * 1024)
    print(f"✅ ZIP creado exitosamente: {zip_name} ({file_size_mb:.2f} MB)\n")

    # 5. Resumen
    print("=" * 60)
    print(f"✅ COMPILACIÓN Y EMPAQUETADO COMPLETADO")
    print("=" * 60)
    print(f"Versión:        {APP_VERSION}")
    print(f"Carpeta build:  {new_folder_path}")
    print(f"Archivo ZIP:    {zip_path.absolute()}")
    print(f"Tamaño:         {file_size_mb:.2f} MB")
    print("\n¡Listo para subir a GitHub Releases!")

    return True

if __name__ == "__main__":
    try:
        success = main()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n❌ Error inesperado: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
