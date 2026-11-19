from pathlib import Path


def cargar_palabras(ruta):
    archivo = Path(ruta)
    if not archivo.exists():
        return []
    lineas = archivo.read_text(encoding="utf-8").splitlines()
    return [l.strip() for l in lineas if l.strip() and not l.strip().startswith("#")]
