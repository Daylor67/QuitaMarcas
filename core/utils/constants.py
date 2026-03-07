import os
import sys
from enum import IntEnum

# Directorio base de la app (funciona tanto en .py como en .exe compilado)
if getattr(sys, 'frozen', False):
    _BASE_DIR = os.path.dirname(sys.executable)
else:
    _BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Static Variables
LOG_REL_DIR = os.path.join(_BASE_DIR, '__logs__')
SETTINGS_REL_DIR = os.path.join(_BASE_DIR, '__settings__')
OUTPUT_SUFFIX = ' [stitched]'
POSTPROCESS_SUFFIX = ' [processed]'
SUPPORTED_IMG_TYPES = (
    '.png',
    '.webp',
    '.jpg',
    '.jpeg',
    '.jfif',
    '.bmp',
    '.tiff',
    '.tga',
    '.psd',
    '.psb',
)

PHOTOSHOP_FILE_TYPES = (
    ".psd",
    ".psb"
)

# Static Enums
class WIDTH_ENFORCEMENT(IntEnum):
    NONE = 0
    AUTOMATIC = 1
    MANUAL = 2


class DETECTION_TYPE(IntEnum):
    NO_DETECTION = 0
    PIXEL_COMPARISON = 1
