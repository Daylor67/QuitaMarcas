from qdarktheme import load_stylesheet

LIGHT_STYLE_SHEET = """
QPushButton {
    color: rgb(40, 83, 65);
    background: rgba(38, 238, 159, 1);
}
QPushButton:!window {
    color: rgb(40, 83, 65);
    background: rgba(38, 238, 159, 1);
}
QWidget {
    background: #ffffff;
    color: #000000;
    selection-background-color: rgb(38, 120, 65);
    selection-color: #ffffff;
}
QWidget:item:selected,
QWidget:item:checked
{
    background: rgb(38, 120, 65);
    color: #ffffff;
}
QPushButton:default {
    color: #ffffff;
    background: #43e689;
}
QPushButton:hover,
QPushButton:flat:hover {
    background: rgba(38, 238, 159, 0.666);
}
QPushButton:pressed,
QPushButton:flat:pressed,
QPushButton:checked:pressed,
QPushButton:flat:checked:pressed {
    background: rgba(38, 238, 159, 0.333);
}
QPushButton:checked,
QPushButton:flat:checked {
    background: rgba(38, 238, 159, 0.933);
}
QPushButton:default:hover {
    background: rgba(38, 238, 159, 0.666);
}
QPushButton:default:pressed {
    background: rgba(38, 238, 159, 0.333);
}
QPushButton:default:disabled {
    background: #dbe1de;
}

QTabBar::tab:hover {
    background: rgba(38, 238, 159, 0.666);
}
QTabBar::tab:selected {
    color: rgb(40, 83, 65);
    background: rgba(38, 238, 159, 0.333);
}
QTabBar::tab:selected:disabled {
    background: #dbe1de;
    color: #babdc2;
}
QTabBar::tab:top:selected {
    border-bottom: 2px solid rgba(38, 238, 159, 1);
}
QTabBar::tab:top:hover {
    border-color: rgba(38, 238, 159, 1);
}
QTabBar::tab:top:selected:disabled {
    border-color: #dbe1de;
}
QTabBar::tab:selected:hover:enabled{
    color: rgb(40, 83, 65);
    background: rgba(38, 238, 159, 0.333);
}
QTabBar::tab:selected:enabled {
    color: rgb(40, 83, 65);
    background: rgba(38, 238, 159, 0.333);
}
QTabBar::tab:bottom {
    border-top: 2px solid #dbe1de;
}
QTabBar::tab:bottom:selected {
    border-top: 2px solid rgba(38, 238, 159, 1);
}
QTabBar::tab:bottom:hover {
    border-color: rgba(38, 238, 159, 1);
}
QTabBar::tab:bottom:selected:disabled {
    border-color: #dbe1de;
}
QTabBar::tab:left {
    border-right: 2px solid #dbe1de;
}
QTabBar::tab:left:selected {
    border-right: 2px solid rgba(38, 238, 159, 1);
}
QTabBar::tab:left:hover {
    border-color: rgba(38, 238, 159, 1);
}
QTabBar::tab:left:selected:disabled {
    border-color: #dbe1de;
}
QTabBar::tab:right {
    border-left: 2px solid #dbe1de;
}
QTabBar::tab:right:selected {
    border-left: 2px solid rgba(38, 238, 159, 1);
}
QTabBar::tab:right:hover {
    border-color: rgba(38, 238, 159, 1);
}
QTabBar::tab:right:selected:disabled {
    border-color: #dbe1de;
}
QGroupBox {
    border: 1px solid #dbe1de;
}
QLineEdit,
QAbstractSpinBox {
    border: 1px solid #dbe1de;
}
QLineEdit:focus,
QAbstractSpinBox:focus {
    border: 1px solid rgba(38, 238, 159, 1);
}
QComboBox {
    border: 1px solid #dbe1de;
    background: rgba(255.000, 255.000, 255.000, 0.000);
}
QComboBox:focus,
QComboBox:open {
    border: 1px solid rgba(38, 238, 159, 1);
}
QComboBox::drop-down {
    border: none;
    padding-right: 4px;
}
QComboBox::item:selected {
    border: none;
    background: rgb(38, 120, 65);
    color: #ffffff;
}
QComboBox QAbstractItemView {
    background: #ffffff;
    border: 1px solid #dbe1de;
    selection-background-color: rgb(38, 120, 65);
    selection-color: #ffffff;
}
QTextEdit:focus,
QTextEdit:selected,
QPlainTextEdit:focus,
QPlainTextEdit:selected {
    border: 1px solid rgba(38, 238, 159, 1);
    selection-background-color: rgb(38, 120, 65);
}
QProgressBar::chunk {
    background: rgba(38, 238, 159, 1);
}
QCheckBox,
QRadioButton {
    border-top: 2px solid transparent;
    border-bottom: 2px solid transparent;
}
QCheckBox:!window,
QRadioButton:!window {
    background: transparent;
}
QCheckBox:hover,
QRadioButton:hover {
    border-bottom: 2px solid transparent;
}
QCheckBox::indicator:checked,
QGroupBox::indicator:checked,
QAbstractItemView::indicator:checked {
    image: url(./assets/CheckboxHighlight.svg);
}

"""

WM_STYLE_SHEET = """
/* ================================================================
   WatermarkRemove — SlideshowViewer specific styles (Phase 4)
   Aplicados via setObjectName() en los componentes. No usar
   setStyleSheet() inline en los componentes — todo va aquí (D-12).
   ================================================================ */

/* Contador de imagen: acento teal (reemplaza #2196F3 hardcodeado) */
QLabel#wm-counter {
    font-size: 15px;
    font-weight: bold;
    color: #26EE9F;
    padding: 5px;
}

/* Nombre de archivo: fondo oscuro sutil */
QLabel#wm-filename {
    font-size: 12px;
    color: #888888;
    padding: 8px;
    background-color: #1e1e1e;
    border-radius: 5px;
}

/* Scroll area del visor de imagen */
QScrollArea#wm-image-scroll {
    border: 2px solid #444444;
    background-color: #2b2b2b;
}

QLabel#wm-image-label {
    background-color: #2b2b2b;
}

/* Label de conteo de training data */
QLabel#wm-training-counts {
    color: #aaaaaa;
    font-size: 10px;
    font-family: monospace;
}

/* Botones del selector de modo (checkables, estilo tab) */
QPushButton#wm-mode-btn {
    border: 1px solid #444444;
    border-radius: 0px;
    padding: 4px 8px;
}
QPushButton#wm-mode-btn:checked {
    background-color: rgba(38, 238, 159, 0.2);
    border-bottom: 2px solid #26EE9F;
    color: #26EE9F;
}
QPushButton#wm-mode-btn:disabled {
    color: #666666;
    background-color: transparent;
}
QPushButton#wm-mode-btn:hover:!checked:!disabled {
    background-color: rgba(38, 238, 159, 0.08);
}

/* Aceptar / Guardar (verde semántico — acción positiva) */
QPushButton#wm-accept-btn {
    background-color: #4CAF50;
    color: white;
    font-weight: bold;
}
QPushButton#wm-accept-btn:hover {
    background-color: #66BB6A;
}
QPushButton#wm-accept-btn:pressed {
    background-color: #388E3C;
}

/* Revertir / Cancelar (rojo semántico — acción destructiva) */
QPushButton#wm-revert-btn,
QPushButton#wm-cancel-btn {
    background-color: #f44336;
    color: white;
}
QPushButton#wm-revert-btn:hover,
QPushButton#wm-cancel-btn:hover {
    background-color: #ef5350;
}
QPushButton#wm-revert-btn:pressed,
QPushButton#wm-cancel-btn:pressed {
    background-color: #c62828;
}

/* Finalizar y Procesar (acento teal — acción principal positiva) */
QPushButton#wm-finish-btn {
    background-color: #26EE9F;
    color: #1a3d31;
    font-weight: bold;
}
QPushButton#wm-finish-btn:hover {
    background-color: rgba(38, 238, 159, 0.85);
}
QPushButton#wm-finish-btn:pressed {
    background-color: rgba(38, 238, 159, 0.65);
}

/* Reset imagen (naranja neutro — acción reversible pero de riesgo) */
QPushButton#wm-reset-btn {
    background-color: #FF9800;
    color: white;
    font-weight: bold;
}
QPushButton#wm-reset-btn:hover {
    background-color: #FFA726;
}

/* Aplicar recorte y Guardar y Siguiente (teal — acción de avance) */
QPushButton#wm-crop-apply-btn,
QPushButton#wm-save-next-btn {
    background-color: #26EE9F;
    color: #1a3d31;
    font-weight: bold;
}
QPushButton#wm-crop-apply-btn:hover,
QPushButton#wm-save-next-btn:hover {
    background-color: rgba(38, 238, 159, 0.85);
}
"""


def load_styling():
    main_styles = load_stylesheet('dark')
    return main_styles + WM_STYLE_SHEET
