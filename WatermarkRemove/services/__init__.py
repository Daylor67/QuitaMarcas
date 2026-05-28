"""
Servicios del módulo WatermarkRemove.

Barrel de exportación de servicios de dominio. Patrón: cada servicio
exporta su clase + (si es stateless-singleton) una instancia a nivel
módulo para que los consumers la importen directamente.
"""
from .wm_persistence import WmPersistenceService
from .position_editor_service import PositionEditorService
from .folder_scan_service import scan_images, scan_pngs, scan_subfolders
from .wm_positions_persistence import WmPositionsPersistenceService
from .context_menu_service import ContextMenuService

# Singletons stateless (siguiendo el patrón de wm_persistence de Phase 1).
wm_persistence = WmPersistenceService()
position_editor_service = PositionEditorService()
wm_positions_persistence = WmPositionsPersistenceService()
context_menu_service = ContextMenuService()

__all__ = [
    # Phase 1
    'wm_persistence',
    'WmPersistenceService',
    # Phase 3 - Plan 03-01 (Wave 0 services)
    'PositionEditorService',
    'position_editor_service',
    'scan_images',
    'scan_pngs',
    'scan_subfolders',
    'WmPositionsPersistenceService',
    'wm_positions_persistence',
    'ContextMenuService',
    'context_menu_service',
]
