"""
ContextMenuService - Detección + toggle del menú contextual de Windows
(Phase 3, Plan 03-01).

Extrae la lógica `winreg` + `register_context_menu` actualmente inline en
`WatermarkRemove/ui/watermark_tab.py` L146-180 (_is_context_menu_registered,
_toggle_context_menu) hacia un servicio para satisfacer ARCH-04
(WatermarkTab como coordinador puro).

CONSTRAINT (RESEARCH Runtime State L208): la clave del registro
HKEY_CURRENT_USER -> Software -> Classes -> Directory -> shell ->
SmartStitchWR NO cambia — solo se reubica el call-site. El guard `FileNotFoundError` se
preserva verbatim (Pitfall 3).

CONSTRAINT: el servicio NO contiene código Qt — el feedback visual
(diálogos modales, refresh del texto del botón) se queda en el widget.
"""
import os
import sys

# services/ esta UN nivel bajo WatermarkRemove/.
# Para importar `register_context_menu` (módulo top-level del repo)
# necesitamos el repo root, DOS niveles arriba de services/.
_current_dir = os.path.abspath(os.path.dirname(__file__))
_repo_root = os.path.dirname(os.path.dirname(_current_dir))
if _repo_root not in sys.path:
    sys.path.insert(0, _repo_root)


class ContextMenuService:
    """Servicio de integración con el menú contextual de Windows.

    Expone una API mínima:
    - `is_registered() -> bool`: consulta el registro de Windows.
    - `toggle() -> bool`: alterna registrado/desregistrado y retorna el
      nuevo estado.

    El servicio NO toca código Qt: el widget consume el booleano para
    actualizar la UI (texto del botón, diálogos modales, etc.).
    """

    KEY = r"Software\Classes\Directory\shell\SmartStitchWR"

    def is_registered(self) -> bool:
        """Comprueba si el menú contextual está registrado en el registro de Windows.

        Preserva verbatim el guard `FileNotFoundError` del widget original
        (`watermark_tab.py` L146-153, RESEARCH Pitfall 3): si la clave no
        existe, `winreg.OpenKey` lanza `FileNotFoundError` y el servicio
        retorna False — cualquier otra excepción se propaga (el widget la
        atrapa para mostrar un diálogo modal de error).

        Returns:
            True si la clave existe en `HKEY_CURRENT_USER`, False si no.
        """
        import winreg
        try:
            winreg.OpenKey(winreg.HKEY_CURRENT_USER, self.KEY)
            return True
        except FileNotFoundError:
            return False

    def toggle(self) -> bool:
        """Alterna el estado del menú contextual y retorna el NUEVO estado.

        Si actualmente está registrado → llama a
        `register_context_menu.unregister()` y retorna False (nuevo estado:
        no registrado).
        Si actualmente NO está registrado → llama a
        `register_context_menu.register()` y retorna True (nuevo estado:
        registrado).

        El widget consume el booleano para refrescar el texto del botón
        y mostrar un diálogo modal confirmatorio.

        Returns:
            bool: nuevo estado tras el toggle. True = registrado ahora,
            False = no registrado ahora.
        """
        import register_context_menu
        if self.is_registered():
            register_context_menu.unregister()
            return False
        else:
            register_context_menu.register()
            return True
