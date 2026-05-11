import os
import sys
import cv2
import numpy as np
from pathlib import Path
from typing import List, Union, Literal, Optional, Tuple
from natsort import natsorted

# Agregar el directorio padre al path para poder importar utils
current_dir = os.path.abspath(os.path.dirname(__file__))
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

from utils import UtilJson


def cargar_lotes_imagenes(carpeta: str, subcarpetas=True) -> List[Path]:
    """Retorna una lista con las rutas completas de todos los archivos dentro de una carpeta."""
    directorio = Path(carpeta)
    archivos = []

    if subcarpetas:    
        archivos = natsorted(
            directorio.iterdir() 
            )
    else:
        archivos = natsorted(
            [f for f in directorio.iterdir() if f.is_file()]
            )
    return archivos


def load_images_cv2(image_path: Union[str, Path]) -> np.ndarray:
    """Carga la imagen principal y la marca de agua."""
    if isinstance(image_path, Path):
        image_path = str(image_path)
    img_array = np.fromfile(image_path, dtype=np.uint8)
    img = cv2.imdecode(img_array, cv2.IMREAD_UNCHANGED)
    if img is None:
        raise ValueError(f"No se pudo cargar la imagen: {image_path}")

    return img


def align_watermark(
    image: np.ndarray,
    watermark: np.ndarray,
    offset_x: int=0,
    offset_y: int=0,
    side_x: str=Literal['left', 'center', 'right'],
    side_y: str=Literal['top', 'center', 'bottom']
):
    """
    Alinea la marca de agua en la imagen con un offset dado.

    Ahora soporta posiciones parcialmente fuera de la imagen.
    La función siempre retorna coordenadas, incluso si están fuera de los bordes.

    Args:
        image (np.ndarray): Imagen original.
        watermark (np.ndarray): Marca de agua (debe incluir canal alfa).
        offset_x (int): Desplazamiento horizontal en píxeles.
        offset_y (int): Desplazamiento vertical en píxeles.
        side_x (str): 'left', 'center' o 'right' para alinear horizontalmente.
        side_y (str): 'top', 'center' o 'bottom' para alinear verticalmente.

    Returns:
        tuple[int, int]: Coordenadas (x, y) donde posicionar la marca de agua.
        Las coordenadas pueden ser negativas o fuera de la imagen.
    """
    h_img, w_img, _ = image.shape
    h_wm, w_wm, _ = watermark.shape

    # Coordenadas X (pueden ser negativas o mayores que el ancho)
    if side_x == 'left':
        x = offset_x
    elif side_x == 'center':
        x = (w_img - w_wm) // 2 + offset_x
    elif side_x == 'right':
        x = w_img - w_wm - offset_x

    # Coordenadas Y (pueden ser negativas o mayores que el alto)
    if side_y == 'top':
        y = offset_y
    elif side_y == 'center':
        y = (h_img - h_wm) // 2 + offset_y
    elif side_y == 'bottom':
        y = h_img - h_wm - offset_y

    return x, y


def get_content_bounds(image: np.ndarray, alpha_threshold: int = 0):
    """
    Bounding box del contenido visible (píxeles con alpha > threshold).
    Devuelve (x_min, y_min, x_max, y_max, width, height) o None si todo es transparente.
    """
    alpha = image[..., 3]
    mask = alpha > alpha_threshold
    if not np.any(mask):
        return None
    ys, xs = np.where(mask)
    x_min, x_max = int(xs.min()), int(xs.max())
    y_min, y_max = int(ys.min()), int(ys.max())
    return x_min, y_min, x_max, y_max, x_max - x_min + 1, y_max - y_min + 1


def find_wm_gpu(
    image: np.ndarray,
    watermark: np.ndarray,
    radio=140,
    center_x=None,
    center_y=None
    ):
    """
    Versión optimizada con GPU (OpenCL) para encontrar la marca de agua.
    Mucho más rápido que la versión CPU.

    Args:
        image: Imagen donde buscar (RGB o RGBA)
        watermark: Marca de agua con canal alpha
        radio: Radio de búsqueda desde el centro
        center_x: Coordenada X del centro (None = centro de imagen)
        center_y: Coordenada Y del centro (None = centro de imagen)

    Returns:
        tuple: (best_x, best_y) o None si falla
    """
    search_region = None
    try:
        h_img, w_img = image.shape[:2]

        # Recortar watermark al contenido visible para que el template matching
        # no dependa del tamaño del canvas completo (que puede salir de la imagen)
        bounds = get_content_bounds(watermark)
        if bounds is None:
            return None
        cx_min, cy_min, cx_max, cy_max, w_content, h_content = bounds
        wm_content = watermark[cy_min:cy_max + 1, cx_min:cx_max + 1]

        # Usar coordenadas especificadas o el centro
        centro_x = center_x if center_x is not None else w_img // 2
        centro_y = center_y if center_y is not None else h_img // 2

        # El search debe cubrir al menos el contenido visible de la marca
        half_w = (w_content // 2 + radio)
        half_h = (h_content // 2 + radio)

        # Extraer región de búsqueda de la imagen
        search_x_start = max(0, centro_x - half_w)
        search_x_end = min(w_img, centro_x + half_w)
        search_y_start = max(0, centro_y - half_h)
        search_y_end = min(h_img, centro_y + half_h)

        search_region = image[search_y_start:search_y_end, search_x_start:search_x_end]

        if search_region.shape[0] < h_content or search_region.shape[1] < w_content:
            print(
                f"find_wm_gpu: search ({search_region.shape[1]}x{search_region.shape[0]}) "
                f"menor que contenido visible ({w_content}x{h_content}); abortando."
            )
            return None

        # Preparar template (solo contenido visible) + máscara
        wm_rgb = wm_content[:, :, :3]
        wm_alpha = wm_content[:, :, 3]
        mask = (wm_alpha > 25).astype(np.uint8) * 255

        # Template matching en GPU
        search_region_gpu = cv2.UMat(search_region)
        wm_rgb_gpu = cv2.UMat(wm_rgb)
        mask_gpu = cv2.UMat(mask)

        result = cv2.matchTemplate(search_region_gpu, wm_rgb_gpu, cv2.TM_SQDIFF, mask=mask_gpu)
        result_cpu = result.get()
        _, _, min_loc, _ = cv2.minMaxLoc(result_cpu)

        # min_loc es la posición del contenido recortado dentro de search_region.
        # Restamos el offset del recorte para obtener la posición del PNG completo.
        best_x = search_x_start + min_loc[0] - cx_min
        best_y = search_y_start + min_loc[1] - cy_min

        return best_x, best_y

    except Exception as e:
        search_shape = search_region.shape if search_region is not None else None
        print(
            f"Error en find_wm_gpu: {e} | search={search_shape} wm={watermark.shape}"
        )
        return None


def find_wm(
    image:np.ndarray,
    watermark:np.ndarray,
    radio=140,
    center_x=None,
    center_y=None,
    use_gpu=True
    ):
    """
    Encuentra la mejor alineación de la marca de agua.

    Intenta usar GPU (OpenCL) primero para mayor velocidad. Si falla o no está
    disponible, usa implementación CPU.

    Args:
        image: Imagen donde buscar la marca de agua
        watermark: Marca de agua a buscar (debe tener canal alpha)
        radio: Radio de búsqueda desde el centro (define el área: centro±radio)
        center_x: Coordenada X del centro de búsqueda (None = centro de imagen)
        center_y: Coordenada Y del centro de búsqueda (None = centro de imagen)
        use_gpu: Intentar usar GPU si está disponible (default: True)

    Returns:
        tuple: (best_x, best_y) coordenadas donde se encontró la mejor coincidencia
    """
    # Intentar versión GPU primero si está habilitado
    if use_gpu and cv2.ocl.haveOpenCL():
        result = find_wm_gpu(image, watermark, radio, center_x, center_y)
        if result is not None:
            return result
        # Si falla, continuar con CPU

    # Versión CPU (fallback)
    h_img, w_img, _ = image.shape
    h_wm, w_wm, _ = watermark.shape

    best_x, best_y = 0, 0
    min_diff = float("inf")

    # Usar coordenadas especificadas o el centro de la imagen
    centro_x = center_x if center_x is not None else w_img // 2
    centro_y = center_y if center_y is not None else h_img // 2

    # Calcular límites del área de búsqueda (cuadrado alrededor del centro)
    search_x_start = centro_x - radio
    search_x_end = centro_x + radio
    search_y_start = centro_y - radio
    search_y_end = centro_y + radio

    # Buscar pixel por pixel: de arriba a abajo, de izquierda a derecha
    for y in range(search_y_start, search_y_end):
        for x in range(search_x_start, search_x_end):
            # Calcular la región de la marca de agua que se superpone con la imagen
            wm_y_start = max(0, -y)
            wm_x_start = max(0, -x)
            wm_y_end = min(h_wm, h_img - y)
            wm_x_end = min(w_wm, w_img - x)

            # Calcular la región de la imagen correspondiente
            img_y_start = max(0, y)
            img_x_start = max(0, x)
            img_y_end = min(h_img, y + h_wm)
            img_x_end = min(w_img, x + w_wm)

            # Verificar que haya superposición válida
            if wm_y_end <= wm_y_start or wm_x_end <= wm_x_start:
                continue
            if img_y_end <= img_y_start or img_x_end <= img_x_start:
                continue

            # Extraer regiones superpuestas
            roi = image[img_y_start:img_y_end, img_x_start:img_x_end, :3]
            wm_region = watermark[wm_y_start:wm_y_end, wm_x_start:wm_x_end, :3]
            wm_alpha = watermark[wm_y_start:wm_y_end, wm_x_start:wm_x_end, 3] / 255.0

            visible_mask = wm_alpha > 0.1
            num_visible_pixels = np.sum(visible_mask)

            # Requerir al menos 30% de la marca visible para considerar válida
            if num_visible_pixels < (0.3 * visible_mask.size):
                continue

            diff = np.abs(roi.astype(np.int16) - wm_region.astype(np.int16))
            total_diff = np.sum(diff[visible_mask])

            # Normalizar por cantidad de píxeles para evitar que áreas pequeñas ganen
            avg_diff = total_diff / num_visible_pixels if num_visible_pixels > 0 else float('inf')

            if avg_diff < min_diff:
                min_diff = avg_diff
                best_x, best_y = x, y

    return best_x, best_y


def generar_mascara_watermark(watermark: np.ndarray) -> np.ndarray:
    """Genera una máscara binaria de la marca de agua usando su canal alfa."""
    alpha = watermark[:, :, 3]
    mask = np.where(alpha > 10, 255, 0).astype(np.uint8)
    return mask


def remove_watermark(
    image: np.ndarray,
    watermark: np.ndarray,
    x: float,
    y: float,
    transparency_threshold: int = 6,
    opaque_threshold: int = 240,
    alpha_adjust: float = 1.0,
    apply_jpeg_filter: bool = True,
    jpeg_filter_strength: int = 3,
    jpeg_filter_threshold: int = 4
) -> np.ndarray:
    """
    Elimina la marca de agua de la imagen usando la fórmula de Fire.
    
    Args:
        image: Imagen BGR con marca de agua (uint8)
        watermark: Marca de agua BGRA con canal alfa (uint8)
        x, y: Posición de la marca de agua en la imagen (puede ser float para subpíxel)
        transparency_threshold: Umbral mínimo de opacidad para procesar (0-255)
        opaque_threshold: Umbral para suavizado de píxeles muy opacos (0-255)
        alpha_adjust: Ajuste de opacidad de la marca (0.5-1.5)
        apply_jpeg_filter: Aplicar filtro de ruido JPEG
        jpeg_filter_strength: Intensidad del blur del filtro JPEG
        jpeg_filter_threshold: Umbral de detección de bordes para JPEG filter
    
    Returns:
        Imagen sin marca de agua (uint8)
    """
    # Separar parte entera y subpíxel
    x_int = int(np.floor(x))
    y_int = int(np.floor(y))
    x_sub = x % 1
    y_sub = y % 1
    
    h_img, w_img = image.shape[:2]
    h_wm, w_wm = watermark.shape[:2]
    
    # Si hay desplazamiento subpíxel, trasladar la marca de agua
    wm_translated = watermark.copy()
    if x_sub != 0 or y_sub != 0:
        M = np.float32([[1, 0, x_sub], [0, 1, y_sub]])
        wm_translated = cv2.warpAffine(
            watermark, M, (w_wm, h_wm),
            flags=cv2.INTER_LINEAR,
            borderMode=cv2.BORDER_CONSTANT,
            borderValue=0
        )
    
    # Calcular región de superposición
    x_start_img = max(0, x_int)
    y_start_img = max(0, y_int)
    x_end_img = min(w_img, x_int + w_wm)
    y_end_img = min(h_img, y_int + h_wm)
    
    x_start_wm = max(0, -x_int)
    y_start_wm = max(0, -y_int)
    x_end_wm = x_start_wm + (x_end_img - x_start_img)
    y_end_wm = y_start_wm + (y_end_img - y_start_img)
    
    if x_start_img >= x_end_img or y_start_img >= y_end_img:
        return image
    
    # Copiar imagen para no modificar el original
    result = image.copy().astype(np.float32)
    
    # Extraer región de interés
    roi = result[y_start_img:y_end_img, x_start_img:x_end_img]
    wm_cropped = wm_translated[y_start_wm:y_end_wm, x_start_wm:x_end_wm].astype(np.float32)
    
    # Extraer canal alfa y aplicar ajuste
    alpha = wm_cropped[:, :, 3].copy()
    alpha = np.clip(alpha * alpha_adjust, 0, 255)
    
    h, w = roi.shape[:2]
    
    # Aplicar la fórmula de Fire píxel por píxel (como en JS)
    for i in range(h):
        for j in range(w):
            alpha_val = alpha[i, j]
            
            # Solo procesar si supera el umbral de transparencia
            if alpha_val > transparency_threshold:
                # Fórmula de Fire
                alpha_img = 255.0 / (255.0 - alpha_val)
                alpha_wm = -alpha_val / (255.0 - alpha_val)
                
                # Aplicar a cada canal
                for c in range(3):
                    new_val = alpha_img * roi[i, j, c] + alpha_wm * wm_cropped[i, j, c]
                    roi[i, j, c] = new_val
                
                # Suavizado de píxeles muy opacos
                if alpha_val > opaque_threshold and j > 0:
                    factor = (alpha_val - opaque_threshold) / (255.0 - opaque_threshold)
                    for c in range(3):
                        roi[i, j, c] = factor * roi[i, j-1, c] + (1 - factor) * roi[i, j, c]
    
    # Clip values
    roi = np.clip(roi, 0, 255)
    result[y_start_img:y_end_img, x_start_img:x_end_img] = roi
    
    # Aplicar filtro JPEG si está habilitado
    if apply_jpeg_filter:
        result = apply_jpeg_noise_filter(
            result.astype(np.uint8),
            alpha,
            (x_start_img, y_start_img, x_end_img, y_end_img),
            jpeg_filter_strength,
            jpeg_filter_threshold,
            transparency_threshold
        )
        return result
    
    return result.astype(np.uint8)


def quick_align_preview(
    image: np.ndarray,
    watermark: np.ndarray,
    x: float,
    y: float,
    alpha_adjust: float = 1.0,
) -> np.ndarray:
    """
    Preview vectorizado para feedback rápido de alineación.

    Calcula `image - watermark * alpha` (sin la división por (1-alpha) que hace
    remove_watermark). Visualmente: si está bien alineado se ve un parche
    oscurecido limpio; si está mal alineado, se ve un "fantasma" de la marca.

    No es el resultado final — solo sirve para evaluar alineación a alta
    velocidad mientras se ajustan offset/alpha en vivo.
    """
    x_int = int(np.floor(x))
    y_int = int(np.floor(y))

    h_img, w_img = image.shape[:2]
    h_wm, w_wm = watermark.shape[:2]

    # Región de superposición
    x0_i = max(0, x_int)
    y0_i = max(0, y_int)
    x1_i = min(w_img, x_int + w_wm)
    y1_i = min(h_img, y_int + h_wm)

    x0_w = max(0, -x_int)
    y0_w = max(0, -y_int)
    x1_w = x0_w + (x1_i - x0_i)
    y1_w = y0_w + (y1_i - y0_i)

    if x0_i >= x1_i or y0_i >= y1_i:
        return image.copy()

    result = image.astype(np.int16, copy=True)
    wm_rgb = watermark[y0_w:y1_w, x0_w:x1_w, :3].astype(np.float32)
    alpha = watermark[y0_w:y1_w, x0_w:x1_w, 3].astype(np.float32) * (alpha_adjust / 255.0)

    subtraction = (wm_rgb * alpha[..., None]).astype(np.int16)
    result[y0_i:y1_i, x0_i:x1_i] -= subtraction

    return np.clip(result, 0, 255).astype(np.uint8)


def apply_jpeg_noise_filter(
    image: np.ndarray,
    watermark_alpha: np.ndarray,
    roi_coords: Tuple[int, int, int, int],
    strength: int = 3,
    edge_threshold: int = 4,
    transparency_threshold: int = 3
) -> np.ndarray:
    """
    Aplica el filtro de ruido JPEG exactamente como en el JS.
    
    Este filtro:
    1. Aplica blur a la región procesada
    2. Solo en el área donde había marca de agua
    3. Opcionalmente aplica surface blur para preservar bordes
    """
    x_start, y_start, x_end, y_end = roi_coords
    result = image.copy()
    
    h = y_end - y_start
    w = x_end - x_start
    
    # Extraer la región procesada
    roi = result[y_start:y_end, x_start:x_end].copy().astype(np.float32)
    
    # 1. Crear máscara donde había marca de agua (alpha > threshold)
    watermark_mask = (watermark_alpha > transparency_threshold).astype(np.uint8) * 255
    
    # 2. Aplicar blur
    ksize = max(3, strength * 2 + 1)
    if ksize % 2 == 0:
        ksize += 1
    blurred = cv2.GaussianBlur(roi, (ksize, ksize), strength)
    
    # 3. Crear canvas para el resultado del blur
    blur_canvas = roi.copy()
    
    # 4. Aplicar la máscara: solo donde había marca de agua
    for i in range(h):
        for j in range(w):
            if watermark_mask[i, j] > 0:
                blur_canvas[i, j] = blurred[i, j]
    
    # 5. Mezclar usando composite operation 'color' (mantener luminosidad original)
    # Convertir a HSV para separar luminosidad de color
    roi_hsv = cv2.cvtColor(roi.astype(np.uint8), cv2.COLOR_BGR2HSV).astype(np.float32)
    blur_hsv = cv2.cvtColor(blur_canvas.astype(np.uint8), cv2.COLOR_BGR2HSV).astype(np.float32)
    
    # Mantener V (Value/luminosidad) del original, tomar H y S del blur
    roi_hsv[:, :, 0] = blur_hsv[:, :, 0]  # Hue del blur
    roi_hsv[:, :, 1] = blur_hsv[:, :, 1]  # Saturation del blur
    # V se mantiene del original (roi_hsv[:, :, 2] no cambia)
    
    result_with_color = cv2.cvtColor(roi_hsv.astype(np.uint8), cv2.COLOR_HSV2BGR).astype(np.float32)
    
    # 6. Aplicar surface blur si el threshold > 0
    if edge_threshold > 0:
        result_with_color = surface_blur(
            result_with_color.astype(np.uint8),
            edge_threshold,
            strength,
            watermark_mask
        ).astype(np.float32)
    
    # 7. Escribir resultado de vuelta
    result[y_start:y_end, x_start:x_end] = np.clip(result_with_color, 0, 255).astype(np.uint8)
    
    return result


def surface_blur(
    image: np.ndarray,
    threshold: int,
    strength: int,
    mask: np.ndarray
) -> np.ndarray:
    """
    Surface blur: difumina áreas planas pero preserva bordes.
    
    Algoritmo:
    1. Detectar bordes mediante diferencia de blurs
    2. Crear máscara de áreas planas (no-bordes)
    3. Aplicar blur solo en áreas planas
    """
    h, w = image.shape[:2]
    
    # 1. Detección de bordes - dos niveles de blur
    blur1 = cv2.GaussianBlur(image, (3, 3), 1)
    blur2 = cv2.GaussianBlur(image, (7, 7), 3)
    
    # 2. Diferencia = detecta bordes
    edge_detect = cv2.absdiff(blur1, blur2)
    edge_gray = cv2.cvtColor(edge_detect, cv2.COLOR_BGR2GRAY)
    
    # 3. Crear máscara: alpha = 255 donde NO hay bordes (áreas planas)
    # alpha = 0 donde hay bordes
    flat_mask = np.zeros((h, w), dtype=np.uint8)
    flat_mask[edge_gray <= threshold] = 255
    
    # 4. Aplicar máscara de watermark (solo procesar donde había marca)
    flat_mask = cv2.bitwise_and(flat_mask, mask)
    
    # 5. Aplicar blur a la imagen
    ksize = max(3, strength * 2 + 1)
    if ksize % 2 == 0:
        ksize += 1
    blurred = cv2.GaussianBlur(image, (ksize, ksize), strength)
    
    # 6. Combinar: blur donde flat_mask = 255, original donde flat_mask = 0
    result = image.copy()
    result[flat_mask > 0] = blurred[flat_mask > 0]
    
    return result

def guardar(image_path: Path, result: np.ndarray, output_folder: Path):
    """Guarda la imagen procesada en la misma estructura dentro la carpeta de salida."""
    if not isinstance(image_path, Path):
        image_path = Path(image_path)
    output_folder.mkdir(parents=True, exist_ok=True)

    output_image = output_folder / image_path.name
    
    # Codificar la imagen en memoria
    ext = output_image.suffix  # Obtener la extensión del archivo (.png, .jpg, etc.)
    success, encoded_image = cv2.imencode(ext, result)

    if not success:
        raise ValueError(f"No se pudo codificar la imagen para guardarla en: {output_image}")

    # Guardar usando numpy para evitar problemas con caracteres especiales
    output_image.with_suffix(ext).write_bytes(encoded_image.tobytes())

    return output_image


def load_positions(site_name: str = 'newtoki', position: str = 'pos_1') -> dict:
    """
    Carga las posiciones de marcas de agua desde el archivo JSON.

    Args:
        site_name: Nombre del sitio web (ej: 'newtoki', 'manganelo')
        position: Nombre de la posición (ej: 'pos_1', 'pos_2', etc.)

    Returns:
        dict: Diccionario con los parámetros de posición (offset_x, offset_y, side_x, side_y)

    Ejemplo:
        >>> pos = load_positions('newtoki', 'pos_4')
        >>> coords = align_watermark(img, wm, **pos)
    """
    positions_path = Path(current_dir) / 'wm_positions.json'
    positions_file = UtilJson(positions_path)

    site_positions = positions_file.get(site_name, {})
    if not site_positions:
        raise ValueError(f"No se encontraron posiciones para el sitio: {site_name}")

    position_data = site_positions.get(position)
    if not position_data:
        raise ValueError(f"No se encontró la posición '{position}' para el sitio '{site_name}'")

    return position_data


if __name__ == "__main__":
    import time
    inicio = time.time()
    def mostrar(img):
        cv2.imshow('Mi Imagen', img)
        cv2.waitKey(0)  # Espera hasta que presiones una tecla
        cv2.destroyAllWindows()

    #marca al 90%
    img = load_images_cv2(r'c:\Users\Felix\Downloads\Image Picka\20 Ilegitimo [sin marca]\14 - 2rFp4RkcByVx.jpg')
    wm = load_images_cv2(r'c:\Users\Felix\Desktop\Newtoki469grisOscuro.png')
    elapsed = time.time() - inicio
    print(f"Imagen cargada en: {elapsed:.2f}s")
    
    coor = find_wm(img, wm, center_x=580, center_y=310)
    elapsed = time.time() - inicio
    print(f"Marca encontrada en {coor}: {elapsed:.2f}s")
 
    img_wmr = remove_watermark(img, wm, *coor, apply_jpeg_filter=False)
    elapsed = time.time() - inicio
    print(f"Marca removida en: {elapsed:.2f}s")
    mostrar(img_wmr)