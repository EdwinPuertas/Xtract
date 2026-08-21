import os
from collections import Counter

import nltk

from .lexical_features import lexical_en, lexical_es
from .text_processing import TextProcessing

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
    bigrams = Counter()
    trigrams = Counter()
    noun_phrases = Counter()
    sentiments = []
    sentiment_counts = Counter()

    for p in posts:
        text = p.get("text") or ""
        lang = p.get("lang") if p.get("lang") in ("es", "en") else "es"
        processor = get_processor(lang)

        cleaned = TextProcessing.transformer(text, lang=lang) or ""
        tokens = TextProcessing.tokenizer(cleaned)

        bigrams.update(TextProcessing.make_ngrams(cleaned, 2))
        trigrams.update(TextProcessing.make_ngrams(cleaned, 3))
        noun_phrases.update(processor.noun_phrases(text))

        sentiment = _score_sentiment(tokens, lang)
        sentiments.append({"id": p.get("id"), **sentiment})
        sentiment_counts[sentiment["label"]] += 1

    return {
        "analyzed_count": len(posts),
        "top_bigrams": bigrams.most_common(15),
        "top_trigrams": trigrams.most_common(15),
        "top_noun_phrases": noun_phrases.most_common(15),
        "sentiments": {s["id"]: s for s in sentiments},
        "sentiment_summary": dict(sentiment_counts),
    }
