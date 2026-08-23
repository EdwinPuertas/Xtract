"""Algoritmo de emociones por post a partir del modelo VAD (Valence-Arousal-Dominance).

Calcula, por cada texto, el promedio de valencia/activación/dominancia de sus
palabras según el NRC VAD Lexicon v2 (`nlp/vad_lexicon.py`) y clasifica el
resultado en una emoción discreta usando una heurística de octantes sobre el
espacio VAD (Valencia +/-, Activación +/-, Dominancia +/-), un enfoque
simplificado habitual en computación afectiva a partir del modelo circumplejo
de Russell extendido con dominancia.

Si el archivo del NRC VAD Lexicon no está instalado (ver `vad_lexicon.py`),
se usa como respaldo un léxico propio mucho más pequeño derivado de
`lexical_features.py` (solo valencia aproximada; activación y dominancia
quedan en el valor neutro 0.5). El resultado indica siempre `source` para
que quien consuma los datos sepa qué tan confiable es la puntuación.
"""

from .lexical_features import lexical_en, lexical_es
from .text_processing import TextProcessing
from .vad_lexicon import load_lexicon

_NEUTRAL_BAND = 0.08

_OCTANTS = {
    (1, 1, 1): "alegría",
    (1, 1, -1): "sorpresa",
    (1, -1, 1): "calma",
    (1, -1, -1): "alivio",
    (-1, 1, 1): "enojo",
    (-1, 1, -1): "miedo",
    (-1, -1, 1): "aburrimiento",
    (-1, -1, -1): "tristeza",
}


def _sign(delta: float) -> int:
    return 1 if delta >= 0 else -1


def _label_from_vad(valence: float, arousal: float, dominance: float) -> str:
    dv, da, dd = valence - 0.5, arousal - 0.5, dominance - 0.5
    if abs(dv) < _NEUTRAL_BAND and abs(da) < _NEUTRAL_BAND:
        return "neutral"
    return _OCTANTS[(_sign(dv), _sign(da), _sign(dd))]


def _fallback_lexicon(lang: str) -> dict[str, tuple[float, float, float]]:
    lex = lexical_es if lang == "es" else lexical_en
    scores = {w.lower(): (0.8, 0.5, 0.5) for w in lex.get("adjetives_pos", [])}
    scores.update({w.lower(): (0.2, 0.5, 0.5) for w in lex.get("adjetives_neg", [])})
    return scores


def compute_vad(text: str, lang: str = "es") -> dict:
    tokens = [t.lower() for t in TextProcessing.tokenizer(text or "")]

    lexicon = load_lexicon()
    source = "nrc_vad_v2"
    if not lexicon:
        lexicon = _fallback_lexicon(lang)
        source = "fallback_lexico_propio"

    matched = [lexicon[t] for t in tokens if t in lexicon]
    if not matched:
        return {
            "valence": None,
            "arousal": None,
            "dominance": None,
            "emotion": "sin_datos",
            "matched_words": 0,
            "total_tokens": len(tokens),
            "source": source,
        }

    valence = sum(m[0] for m in matched) / len(matched)
    arousal = sum(m[1] for m in matched) / len(matched)
    dominance = sum(m[2] for m in matched) / len(matched)

    return {
        "valence": round(valence, 3),
        "arousal": round(arousal, 3),
        "dominance": round(dominance, 3),
        "emotion": _label_from_vad(valence, arousal, dominance),
        "matched_words": len(matched),
        "total_tokens": len(tokens),
        "source": source,
    }
