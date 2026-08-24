"""Job de recolección y análisis periódico para la vista de tendencias.

Se ejecuta desde el endpoint `/api/cron/trends` (invocado por el Cron Job de
Vercel, ver `vercel.json`) o manualmente. Busca hasta `TRENDS_TARGET_POSTS`
posts recientes para la consulta `TRENDS_QUERY`, calcula KPIs sobre todos
ellos y un análisis de texto (tópicos, bigramas/trigramas, sentimiento,
emociones VAD) sobre los primeros `TRENDS_ANALYZE_MAX_POSTS` — el análisis
con spaCy/NLTK es costoso por post, así que se limita para no exceder el
tiempo máximo de una función serverless — y guarda un resumen en la base de
datos vía `trends_store.save_run`.
"""

import os

from app import (
    PLACE_FIELDS,
    TWEET_FIELDS,
    USER_FIELDS,
    _build_post_dict,
    _places_by_id_from_includes,
    _users_by_id_from_includes,
    compute_tweet_kpis,
    get_client,
)
from nlp.analysis import analyze_posts

import trends_store

DEFAULT_QUERY = "lang:es -is:retweet"
TRENDS_QUERY = os.environ.get("TRENDS_QUERY", DEFAULT_QUERY)
TRENDS_TARGET_POSTS = int(os.environ.get("TRENDS_TARGET_POSTS", "1000"))
TRENDS_ANALYZE_MAX_POSTS = int(os.environ.get("TRENDS_ANALYZE_MAX_POSTS", "300"))


def fetch_posts(query: str, target: int) -> list[dict]:
    """Trae hasta `target` posts recientes para `query`, paginando con
    next_token (la API de X limita cada página a 100 resultados)."""
    client = get_client()
    posts: list[dict] = []
    next_token = None

    while len(posts) < target:
        page_size = max(min(100, target - len(posts)), 10)
        response = client.search_recent_tweets(
            query=query,
            max_results=page_size,
            tweet_fields=TWEET_FIELDS,
            expansions=["author_id", "geo.place_id"],
            user_fields=USER_FIELDS,
            place_fields=PLACE_FIELDS,
            next_token=next_token,
        )

        users_by_id = _users_by_id_from_includes(response)
        places_by_id = _places_by_id_from_includes(response)
        page_posts = [_build_post_dict(t, users_by_id, places_by_id) for t in response.data or []]
        posts.extend(page_posts)

        next_token = (response.meta or {}).get("next_token")
        if not next_token or not page_posts:
            break

    return posts[:target]


def _summarize_kpis(kpis: dict) -> dict:
    """Solo los agregados relevantes para la serie de tiempo (se descarta
    top_post: es pesado y no aporta a las gráficas históricas)."""
    return {
        "total_posts": kpis.get("total_posts"),
        "total_engagement": kpis.get("total_engagement"),
        "avg_engagement": kpis.get("avg_engagement"),
        "total_likes": kpis.get("total_likes"),
        "total_retweets": kpis.get("total_retweets"),
        "total_replies": kpis.get("total_replies"),
        "unique_authors": kpis.get("unique_authors"),
        "verified_authors": kpis.get("verified_authors"),
        "top_languages": kpis.get("top_languages"),
        "top_hashtags": kpis.get("top_hashtags"),
        "top_categories": kpis.get("top_categories"),
        "top_countries": kpis.get("top_countries"),
    }


def _summarize_nlp(nlp: dict) -> dict:
    """Solo los agregados (se descartan `sentiments`/`vad`: el detalle por
    post no aporta a la serie de tiempo y hace crecer mucho cada fila)."""
    return {
        "analyzed_count": nlp.get("analyzed_count"),
        "top_bigrams": nlp.get("top_bigrams"),
        "top_trigrams": nlp.get("top_trigrams"),
        "top_noun_phrases": nlp.get("top_noun_phrases"),
        "sentiment_summary": nlp.get("sentiment_summary"),
        "vad_summary": nlp.get("vad_summary"),
    }


def run_trends_job() -> dict:
    posts = fetch_posts(TRENDS_QUERY, TRENDS_TARGET_POSTS)
    kpis = compute_tweet_kpis(posts)
    nlp_result = analyze_posts(posts, max_posts=TRENDS_ANALYZE_MAX_POSTS)

    run_id = trends_store.save_run(
        query=TRENDS_QUERY,
        post_count=len(posts),
        analyzed_count=nlp_result.get("analyzed_count", 0),
        kpis=_summarize_kpis(kpis),
        nlp=_summarize_nlp(nlp_result),
    )

    return {
        "run_id": run_id,
        "query": TRENDS_QUERY,
        "post_count": len(posts),
        "analyzed_count": nlp_result.get("analyzed_count", 0),
    }
