import os
from collections import Counter, defaultdict

import nltk

from .lexical_features import lexical_en, lexical_es
from .embeddings import embed_texts, is_embeddings_available
from .semantic_fusion import fuse_emotion, fuse_sentiment, merge_similar_phrases
from .text_processing import TextProcessing
from .vad_emotion import compute_vad
from .vad_lexicon import is_lexicon_available

_NLTK_DIR = os.environ.get("NLTK_DATA", "/tmp/nltk_data")
os.makedirs(_NLTK_DIR, exist_ok=True)
if _NLTK_DIR not in nltk.data.path:
    nltk.data.path.append(_NLTK_DIR)

_NLTK_READY = False


def _ensure_nltk_data():
    global _NLTK_READY
    if _NLTK_READY:
        return
    for resource, package in (("tokenizers/punkt_tab", "punkt_tab"), ("tokenizers/punkt", "punkt")):
        try:
            nltk.data.find(resource)
        except LookupError:
            try:
                nltk.download(package, download_dir=_NLTK_DIR, quiet=True)
            except Exception as e:
                print("Error descargando recurso nltk {0}: {1}".format(package, e))
    _NLTK_READY = True


_PROCESSORS: dict[str, TextProcessing] = {}


def get_processor(lang: str) -> TextProcessing:
    lang = lang if lang in ("es", "en") else "es"
    if lang not in _PROCESSORS:
        _PROCESSORS[lang] = TextProcessing(lang=lang)
    return _PROCESSORS[lang]


def _score_sentiment(tokens: list[str], lang: str) -> dict:
    lexical = lexical_es if lang == "es" else lexical_en
    lowered = [t.lower() for t in tokens]
    pos = sum(1 for w in lowered if w in lexical["adjetives_pos"])
    neg = sum(1 for w in lowered if w in lexical["adjetives_neg"])
    total = pos + neg
    score = round((pos - neg) / total, 3) if total else 0.0
    if score > 0.15:
        label = "positivo"
    elif score < -0.15:
        label = "negativo"
    else:
        label = "neutral"
    return {"score": score, "label": label, "pos": pos, "neg": neg}


def analyze_posts(posts: list[dict], max_posts: int = 60) -> dict:
    _ensure_nltk_data()

    posts = posts[:max_posts]
    post_texts = [p.get("text") or "" for p in posts]
    post_embeddings = embed_texts(post_texts, input_type="document") if is_embeddings_available() else None

    bigrams = Counter()
    trigrams = Counter()
    noun_phrases = Counter()
    entity_counts: dict[str, Counter] = defaultdict(Counter)
    sentiments = []
    sentiment_counts = Counter()
    vad_results = {}
    emotion_counts = Counter()

    for i, p in enumerate(posts):
        text = p.get("text") or ""
        lang = p.get("lang") if p.get("lang") in ("es", "en") else "es"
        processor = get_processor(lang)
        post_embedding = post_embeddings[i] if post_embeddings else None

        cleaned = TextProcessing.transformer(text, lang=lang) or ""
        tokens = TextProcessing.tokenizer(cleaned)

        bigrams.update(TextProcessing.make_ngrams(cleaned, 2))
        trigrams.update(TextProcessing.make_ngrams(cleaned, 3))
        noun_phrases.update(processor.noun_phrases(text))
        for ent in processor.entities(text):
            entity_counts[ent["label"]][ent["text"]] += 1

        sentiment = _score_sentiment(tokens, lang)
        sentiment = fuse_sentiment(sentiment, post_embedding)
        sentiments.append({"id": p.get("id"), **sentiment})
        sentiment_counts[sentiment["label"]] += 1

        vad = compute_vad(text, lang)
        vad = fuse_emotion(vad, post_embedding)
        vad_results[p.get("id")] = vad
        if vad["emotion"] != "sin_datos":
            emotion_counts[vad["emotion"]] += 1

    top_bigrams, bigrams_source = merge_similar_phrases(bigrams.most_common(30))
    top_trigrams, trigrams_source = merge_similar_phrases(trigrams.most_common(30))
    top_noun_phrases, topics_source = merge_similar_phrases(noun_phrases.most_common(30))

    return {
        "analyzed_count": len(posts),
        "embeddings_used": post_embeddings is not None,
        "top_bigrams": top_bigrams[:15],
        "bigrams_source": bigrams_source,
        "top_trigrams": top_trigrams[:15],
        "trigrams_source": trigrams_source,
        "top_noun_phrases": top_noun_phrases[:15],
        "topics_source": topics_source,
        "top_entities_by_type": {label: counter.most_common(8) for label, counter in entity_counts.items()},
        "sentiments": {s["id"]: s for s in sentiments},
        "sentiment_summary": dict(sentiment_counts),
        "vad": vad_results,
        "vad_summary": {
            "emotion_counts": dict(emotion_counts),
            "lexicon_source": "nrc_vad_v2" if is_lexicon_available() else "fallback_lexico_propio",
        },
    }
