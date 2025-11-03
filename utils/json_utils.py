import json
from pathlib import Path
from typing import Any, Optional, Union


class UtilJson:
    """
    Clase para facilitar operaciones con archivos JSON.

    Args:
        path: Ruta al archivo JSON (str o Path)
        encoding: Codificación del archivo (default: 'utf-8')
        indent: Espacios de indentación para el formato (default: 4)
        ensure_ascii: Si False, permite caracteres Unicode (default: False)

    Ejemplo:
        >>> json_file = UtilJson('datos.json')
        >>> json_file.write({'nombre': 'Ana', 'edad': 25})
        >>> json_file.read()
        {'nombre': 'Ana', 'edad': 25}
        >>> json_file.update({'ciudad': 'Madrid'})
        >>> json_file.get('ciudad')
        'Madrid'
    """

    def __init__(
        self,
        path: Union[str, Path],
        encoding: str = 'utf-8',
        indent: int = 4,
        ensure_ascii: bool = False
    ):
        self.path = Path(path) if isinstance(path, str) else path
        self.encoding = encoding
        self.indent = indent
        self.ensure_ascii = ensure_ascii

    def read(self) -> dict:
        """
        Lee y retorna el contenido del archivo JSON.

        Returns:
            dict: Contenido del archivo. Si el archivo no existe o está vacío, retorna {}.
        """
        try:
            with open(self.path, 'r', encoding=self.encoding) as archivo:
                return json.load(archivo)
        except (FileNotFoundError, json.JSONDecodeError):
            return {}

    def write(self, data: dict) -> 'UtilJson':
        """
        Escribe un diccionario completo en el archivo JSON (sobrescribe el contenido).

        Args:
            data: Diccionario a guardar

        Returns:
            self: Para permitir encadenamiento de métodos
        """
        with open(self.path, 'w', encoding=self.encoding) as archivo:
            json.dump(data, archivo, indent=self.indent, ensure_ascii=self.ensure_ascii)
        return self

    def update(self, data: dict) -> 'UtilJson':
        """
        Actualiza el archivo JSON con los datos proporcionados (merge).

        Args:
            data: Diccionario con los datos a actualizar/agregar

        Returns:
            self: Para permitir encadenamiento de métodos
        """
        current_data = self.read()
        current_data.update(data)
        self.write(current_data)
        return self

    def get(self, key: str, default: Any = None) -> Any:
        """
        Obtiene el valor de una clave específica.

        Args:
            key: Clave a buscar
            default: Valor por defecto si la clave no existe

        Returns:
            El valor asociado a la clave o el valor por defecto
        """
        data = self.read()
        return data.get(str(key), default)

    def set(self, key: str, value: Any) -> 'UtilJson':
        """
        Establece o modifica el valor de una clave específica.

        Args:
            key: Clave a establecer
            value: Valor a asignar

        Returns:
            self: Para permitir encadenamiento de métodos
        """
        data = self.read()
        data[str(key)] = value
        self.write(data)
        return self

    def delete(self, key: str) -> 'UtilJson':
        """
        Elimina una clave del archivo JSON.

        Args:
            key: Clave a eliminar

        Returns:
            self: Para permitir encadenamiento de métodos
        """
        data = self.read()
        data.pop(str(key), None)
        self.write(data)
        return self

    def exists(self, key: Optional[str] = None) -> bool:
        """
        Verifica si el archivo existe o si una clave específica existe.

        Args:
            key: Clave a verificar (opcional). Si es None, verifica si el archivo existe.

        Returns:
            bool: True si existe, False en caso contrario
        """
        if key is None:
            return self.path.exists()
        data = self.read()
        return str(key) in data

    def clear(self) -> 'UtilJson':
        """
        Vacía el contenido del archivo JSON (lo deja como {}).

        Returns:
            self: Para permitir encadenamiento de métodos
        """
        self.write({})
        return self

    def keys(self) -> list:
        """
        Retorna una lista con todas las claves del JSON.

        Returns:
            list: Lista de claves
        """
        return list(self.read().keys())

    def values(self) -> list:
        """
        Retorna una lista con todos los valores del JSON.

        Returns:
            list: Lista de valores
        """
        return list(self.read().values())

    def items(self) -> list:
        """
        Retorna una lista de tuplas (clave, valor) del JSON.

        Returns:
            list: Lista de tuplas (clave, valor)
        """
        return list(self.read().items())

    def __str__(self) -> str:
        """Representación en string del objeto."""
        return f"UtilJson(path='{self.path}')"

    def __repr__(self) -> str:
        """Representación detallada del objeto."""
        return f"UtilJson(path='{self.path}', encoding='{self.encoding}', indent={self.indent})"
