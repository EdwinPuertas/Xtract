"""Carga del NRC Valence-Arousal-Dominance (VAD) Lexicon v2.

El léxico NRC VAD no se distribuye con este repositorio: la licencia de NRC
(uso libre para investigación, con solicitud previa) no permite redistribuirlo.
Para activar el análisis de emociones con datos reales:

1. Solicita/descarga el NRC VAD Lexicon v2 desde
   https://saifmohammad.com/WebPages/nrc-vad.html
2. Coloca el archivo de palabras (formato `palabra<TAB>valence<TAB>arousal<TAB>dominance`,
   valores entre 0 y 1) en `nlp/resources/NRC-VAD-Lexicon-v2.txt`, o define la
   variable de entorno `NRC_VAD_LEXICON_PATH` apuntando a su ubicación.

Si el archivo no está presente, `load_lexicon` devuelve un diccionario vacío y
`nlp/vad_emotion.py` usa un léxico propio de respaldo (menos preciso, ver ese
módulo) en vez de fallar.
"""

import os

_DEFAULT_PATH = os.path.join(os.path.dirname(__file__), "resources", "NRC-VAD-Lexicon-v2.txt")

_CACHE: dict[str, dict[str, tuple[float, float, float]]] = {}


def lexicon_path() -> str:
    return os.environ.get("NRC_VAD_LEXICON_PATH", _DEFAULT_PATH)


def load_lexicon(path: str | None = None) -> dict[str, tuple[float, float, float]]:
    path = path or lexicon_path()
    if path in _CACHE:
        return _CACHE[path]

    lexicon: dict[str, tuple[float, float, float]] = {}
    try:
        with open(path, "r", encoding="utf-8") as fh:
            for line in fh:
                parts = line.strip().split("\t")
                if len(parts) < 4:
                    parts = line.strip().split()
                if len(parts) < 4:
                    continue
                word, valence, arousal, dominance = parts[0], parts[1], parts[2], parts[3]
                try:
                    lexicon[word.lower()] = (float(valence), float(arousal), float(dominance))
                except ValueError:
                    continue  # encabezado u otra línea no numérica
    except (FileNotFoundError, OSError):
        lexicon = {}

    _CACHE[path] = lexicon
    return lexicon


def is_lexicon_available(path: str | None = None) -> bool:
    return len(load_lexicon(path)) > 0
