"""Carga del NRC Valence-Arousal-Dominance (VAD) Lexicon.

El léxico NRC VAD no se redistribuye normalmente junto con el código (la
licencia de NRC es de uso libre para investigación, con solicitud previa) —
por eso `nlp/resources/README.md` explica cómo obtenerlo aparte. Si de todas
formas se agrega un archivo al repo (como el `nlp/NRC-VAD-Lexicon-v2.1.txt`
que trae este proyecto), `load_lexicon` lo detecta automáticamente.

Formato esperado: texto separado por tabulador, una entrada por línea,
`término<TAB>valence<TAB>arousal<TAB>dominance` (con o sin fila de encabezado
— se descarta sola porque sus valores no son numéricos). El NRC VAD Lexicon
oficial (incluida la v2.1) publica esas tres dimensiones en escala **-1..1**
con 0 como neutro; el resto de Xtract (heurística de octantes en
`vad_emotion.py`, léxico de respaldo) trabaja en escala **0..1** con 0.5 como
neutro, así que `load_lexicon` remapea automáticamente si detecta valores
negativos — un archivo que ya venga en 0..1 se deja tal cual.

Si el archivo no está presente, `load_lexicon` devuelve un diccionario vacío y
`nlp/vad_emotion.py` usa un léxico propio de respaldo (menos preciso, ver ese
módulo) en vez de fallar.
"""

import os

_RESOURCES_DIR = os.path.join(os.path.dirname(__file__), "resources")

# Nombres/ubicaciones donde se busca el léxico si NRC_VAD_LEXICON_PATH no está
# definida, en orden de preferencia. Se incluye la ruta donde ya quedó el
# archivo real de este proyecto (nlp/NRC-VAD-Lexicon-v2.1.txt) además de las
# ubicaciones "canónicas" documentadas en nlp/resources/README.md.
_CANDIDATE_PATHS = [
    os.path.join(os.path.dirname(__file__), "NRC-VAD-Lexicon-v2.1.txt"),
    os.path.join(_RESOURCES_DIR, "NRC-VAD-Lexicon-v2.1.txt"),
    os.path.join(_RESOURCES_DIR, "NRC-VAD-Lexicon-v2.txt"),
]

_CACHE: dict[str, dict[str, tuple[float, float, float]]] = {}


def lexicon_path() -> str:
    env_path = os.environ.get("NRC_VAD_LEXICON_PATH")
    if env_path:
        return env_path
    for candidate in _CANDIDATE_PATHS:
        if os.path.isfile(candidate):
            return candidate
    return _CANDIDATE_PATHS[0]


def _normalize_to_unit_range(
    raw: dict[str, tuple[float, float, float]],
) -> dict[str, tuple[float, float, float]]:
    if not raw:
        return raw
    min_value = min(x for values in raw.values() for x in values)
    if min_value >= 0:
        return raw  # ya está en escala 0..1
    return {word: tuple((x + 1) / 2 for x in values) for word, values in raw.items()}


def load_lexicon(path: str | None = None) -> dict[str, tuple[float, float, float]]:
    path = path or lexicon_path()
    if path in _CACHE:
        return _CACHE[path]

    raw: dict[str, tuple[float, float, float]] = {}
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
                    raw[word.lower()] = (float(valence), float(arousal), float(dominance))
                except ValueError:
                    continue  # encabezado u otra línea no numérica
    except (FileNotFoundError, OSError):
        raw = {}

    lexicon = _normalize_to_unit_range(raw)
    _CACHE[path] = lexicon
    return lexicon


def is_lexicon_available(path: str | None = None) -> bool:
    return len(load_lexicon(path)) > 0
