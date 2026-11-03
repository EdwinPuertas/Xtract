"""Fusión de las características léxicas (el léxico NRC VAD / lexical_features.py
ya existentes) con similitud semántica por embeddings, para sentimiento,
emociones VAD y tópicos. Todo esto es inactivo si `nlp/embeddings.py` no está
configurado (sin VOYAGE_API_KEY): cada función devuelve el resultado léxico
sin modificar.

Reglas de fusión (explicables, no un clasificador entrenado):

- Si el léxico no encontró ninguna palabra conocida (p. ej. una emoción VAD en
  un post en español, ya que el NRC VAD Lexicon instalado es solo-inglés),
  se usa la etiqueta semántica (embeddings) directamente.
- Si el léxico y los embeddings coinciden, se mantiene esa etiqueta
  (`fusion_acuerdo`, la señal más confiable: dos fuentes independientes de
  acuerdo).
- Si no coinciden, se confía en la fuente con más señal: el léxico si
  encontró varias palabras relevantes, los embeddings si el léxico encontró
  muy pocas.

Cada resultado incluye `fusion_source` para que quede claro qué fuente ganó.
"""

from .embeddings import cosine_similarity, embed_texts, is_embeddings_available

_SENTIMENT_SEEDS = {
    "positivo": [
        "Estoy muy feliz y contento, todo salió excelente.",
        "I am so happy and excited, everything turned out great!",
        "Qué alegría, esto es maravilloso, lo logramos.",
        "This is wonderful news, I love it, amazing job.",
    ],
    "neutral": [
        "El informe se publicará la próxima semana en la página oficial.",
        "The report will be published next week on the official page.",
        "La reunión es a las tres de la tarde en la sala principal.",
        "The meeting is scheduled for three in the afternoon in the main room.",
    ],
    "negativo": [
        "Estoy muy triste y decepcionado, todo salió mal.",
        "I am so sad and disappointed, everything went wrong.",
        "Qué rabia, esto es terrible, una pésima decisión.",
        "This is awful news, I hate it, a terrible decision.",
    ],
}

_EMOTION_SEEDS = {
    "alegría": [
        "Estoy feliz y emocionado, qué alegría tan grande.",
        "I feel joyful and excited, what wonderful news.",
    ],
    "sorpresa": [
        "No puedo creerlo, qué sorpresa tan inesperada.",
        "I can't believe it, what a shocking surprise.",
    ],
    "calma": [
        "Me siento tranquilo y en paz, todo está en calma.",
        "I feel calm and peaceful, everything is relaxed.",
    ],
    "alivio": [
        "Qué alivio, por fin se resolvió el problema.",
        "What a relief, the problem is finally solved.",
    ],
    "enojo": [
        "Estoy furioso e indignado, esto me da mucha rabia.",
        "I am furious and outraged, this makes me so angry.",
    ],
    "miedo": [
        "Tengo mucho miedo, esto me aterra y me preocupa.",
        "I am terrified and scared, this frightens me.",
    ],
    "aburrimiento": [
        "Qué aburrido, esto no tiene nada de interesante.",
        "This is so boring, nothing interesting is happening.",
    ],
    "tristeza": [
        "Estoy muy triste y deprimido, siento una gran tristeza.",
        "I feel so sad and depressed, this is heartbreaking.",
    ],
}

_sentiment_prototypes_cache: dict[str, list[float]] | None = None
_emotion_prototypes_cache: dict[str, list[float]] | None = None


def _average(vectors: list[list[float]]) -> list[float]:
    n = len(vectors)
    dims = len(vectors[0])
    return [sum(v[d] for v in vectors) / n for d in range(dims)]


def _build_prototypes(seeds: dict[str, list[str]]) -> dict[str, list[float]] | None:
    labels = list(seeds.keys())
    all_texts = [text for label in labels for text in seeds[label]]
    vectors = embed_texts(all_texts, input_type="document")
    if not vectors:
        return None
    result = {}
    idx = 0
    for label in labels:
        n = len(seeds[label])
        result[label] = _average(vectors[idx : idx + n])
        idx += n
    return result


def _get_sentiment_prototypes() -> dict[str, list[float]] | None:
    global _sentiment_prototypes_cache
    if _sentiment_prototypes_cache is None and is_embeddings_available():
        _sentiment_prototypes_cache = _build_prototypes(_SENTIMENT_SEEDS) or {}
    return _sentiment_prototypes_cache or None


def _get_emotion_prototypes() -> dict[str, list[float]] | None:
    global _emotion_prototypes_cache
    if _emotion_prototypes_cache is None and is_embeddings_available():
        _emotion_prototypes_cache = _build_prototypes(_EMOTION_SEEDS) or {}
    return _emotion_prototypes_cache or None


def fuse_sentiment(lexical: dict, post_embedding: list[float] | None) -> dict:
    if post_embedding is None:
        return lexical
    protos = _get_sentiment_prototypes()
    if not protos:
        return lexical

    sims = {label: cosine_similarity(post_embedding, vec) for label, vec in protos.items()}
    semantic_label = max(sims, key=sims.get)
    lexical_label = lexical.get("label", "neutral")
    lexical_signal = lexical.get("pos", 0) + lexical.get("neg", 0)

    if lexical_signal == 0:
        final_label, source = semantic_label, "embeddings_voyage"
    elif lexical_label == semantic_label:
        final_label, source = lexical_label, "fusion_acuerdo"
    elif lexical_signal >= 2:
        final_label, source = lexical_label, "fusion_lexico"
    else:
        final_label, source = semantic_label, "fusion_embeddings"

    return {
        **lexical,
        "label": final_label,
        "semantic_label": semantic_label,
        "semantic_similarities": {k: round(v, 3) for k, v in sims.items()},
        "fusion_source": source,
    }


def fuse_emotion(vad_result: dict, post_embedding: list[float] | None) -> dict:
    if post_embedding is None:
        return vad_result
    protos = _get_emotion_prototypes()
    if not protos:
        return vad_result

    sims = {label: cosine_similarity(post_embedding, vec) for label, vec in protos.items()}
    semantic_label = max(sims, key=sims.get)
    lexical_label = vad_result.get("emotion")
    matched = vad_result.get("matched_words", 0)

    if lexical_label in (None, "sin_datos") or matched == 0:
        final_label, source = semantic_label, "embeddings_voyage"
    elif lexical_label == semantic_label:
        final_label, source = lexical_label, "fusion_acuerdo"
    elif matched >= 3:
        final_label, source = lexical_label, "fusion_lexico"
    else:
        final_label, source = semantic_label, "fusion_embeddings"

    return {
        **vad_result,
        "emotion": final_label,
        "semantic_emotion": semantic_label,
        "fusion_source": source,
    }


def merge_similar_phrases(
    phrase_counts: list[tuple[str, int]], threshold: float = 0.86
) -> tuple[list[tuple[str, int]], str]:
    """Fusiona frases léxicamente distintas pero semánticamente equivalentes
    (ej. "el presidente" y "el mandatario") sumando sus conteos, para que el
    conteo de frecuencia no las trate como tópicos separados solo porque usan
    palabras distintas. Devuelve (lista_fusionada, fuente): fuente es
    'lexico_fusionado_embeddings' si se pudo usar embeddings, o 'lexico_solo'
    si no (sin VOYAGE_API_KEY, o la llamada falló) — en ese caso la lista
    vuelve sin cambios."""
    if len(phrase_counts) < 2 or not is_embeddings_available():
        return phrase_counts, "lexico_solo"

    phrases = [p for p, _ in phrase_counts]
    vectors = embed_texts(phrases, input_type="document")
    if not vectors:
        return phrase_counts, "lexico_solo"

    order = sorted(range(len(phrase_counts)), key=lambda i: phrase_counts[i][1], reverse=True)
    assigned = [False] * len(phrase_counts)
    merged: list[tuple[str, int]] = []

    for i in order:
        if assigned[i]:
            continue
        assigned[i] = True
        total = phrase_counts[i][1]
        for j in order:
            if assigned[j]:
                continue
            if cosine_similarity(vectors[i], vectors[j]) >= threshold:
                total += phrase_counts[j][1]
                assigned[j] = True
        merged.append((phrase_counts[i][0], total))

    merged.sort(key=lambda kv: kv[1], reverse=True)
    return merged, "lexico_fusionado_embeddings"
