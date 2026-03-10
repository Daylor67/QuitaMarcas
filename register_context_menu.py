"""
Registra/desregistra SmartStitch WR en el menú contextual de carpetas de Windows.
Ejecutar como administrador o usar la rama de usuario (no requiere admin).
"""
import os
import sys
import winreg

APP_NAME = "SmartStitch WR"
MENU_KEY = r"Software\Classes\Directory\shell\SmartStitchWR"
COMMAND_KEY = MENU_KEY + r"\command"


def get_exe_path():
    if getattr(sys, 'frozen', False):
        return sys.executable  # Launcher.exe / SmartStitch.exe
    # En desarrollo, apuntar al SmartStitchGUI.py
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "SmartStitchGUI.py")


def register():
    exe_path = get_exe_path()
    command = f'"{exe_path}" "%1"'

    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, MENU_KEY) as key:
        winreg.SetValueEx(key, "", 0, winreg.REG_SZ, f"Abrir con {APP_NAME}")
        winreg.SetValueEx(key, "Icon", 0, winreg.REG_SZ, exe_path)

    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, COMMAND_KEY) as key:
        winreg.SetValueEx(key, "", 0, winreg.REG_SZ, command)

    print(f"✅ Menú contextual registrado: '{exe_path}'")


def unregister():
    try:
        winreg.DeleteKey(winreg.HKEY_CURRENT_USER, COMMAND_KEY)
        winreg.DeleteKey(winreg.HKEY_CURRENT_USER, MENU_KEY)
        print("✅ Menú contextual eliminado.")
    except FileNotFoundError:
        print("ℹ️ El menú contextual no estaba registrado.")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "unregister":
        unregister()
    else:
        register()
