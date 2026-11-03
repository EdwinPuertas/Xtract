"""Cliente de embeddings (Voyage AI) para la fusión léxico+semántica de
sentimiento/tópicos y el re-ranking semántico de la búsqueda (ver
nlp/semantic_fusion.py y app.py).

Inactivo por defecto: todo lo que depende de este módulo se comporta
exactamente igual que antes si no se configura `VOYAGE_API_KEY` (ningún
costo, ninguna llamada de red, ningún texto sale de la app). Al definir la
variable de entorno, se activa:

- `VOYAGE_API_KEY`: API key de https://www.voyageai.com/ (obligatoria para
  activar esto).
- `VOYAGE_EMBEDDING_MODEL`: modelo a usar (por defecto `voyage-multilingual-2`,
  con buen soporte de español e inglés).

Este cliente llama a la API REST de Voyage directamente (con `requests`, ya
es una dependencia del proyecto) en vez de instalar su SDK, para no agregar
una dependencia nueva a requirements.txt. Cualquier error de red, de
autenticación o de formato de respuesta se degrada a `None` en vez de lanzar,
para que una falla de este servicio externo nunca rompa una búsqueda o el
job de tendencias — ver nlp/resources/README.md y el README principal para
más contexto sobre esta elección de proveedor.
"""

import math
import os

import requests

_API_URL = "https://api.voyageai.com/v1/embeddings"
_DEFAULT_MODEL = "voyage-multilingual-2"
_BATCH_SIZE = 96
_TIMEOUT_SECONDS = 20


def is_embeddings_available() -> bool:
    return bool(os.environ.get("VOYAGE_API_KEY"))


def _model() -> str:
    return os.environ.get("VOYAGE_EMBEDDING_MODEL", _DEFAULT_MODEL)


def _chunks(items: list, size: int):
    for i in range(0, len(items), size):
        yield items[i : i + size]


def embed_texts(texts: list[str], input_type: str = "document") -> list[list[float]] | None:
    """Embebe una lista de textos en uno o más batches. Devuelve una lista de
    vectores en el mismo orden que `texts`, o None si el servicio no está
    disponible/configurado o la llamada falla (degradación agraciada: quien
    llama debe caer de vuelta a su lógica puramente léxica)."""
    api_key = os.environ.get("VOYAGE_API_KEY")
    if not api_key or not texts:
        return None

    vectors: list[list[float]] = []
    try:
        for batch in _chunks(texts, _BATCH_SIZE):
            response = requests.post(
                _API_URL,
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json={"input": batch, "model": _model(), "input_type": input_type},
                timeout=_TIMEOUT_SECONDS,
            )
            response.raise_for_status()
            data = response.json()
            items = sorted(data["data"], key=lambda item: item.get("index", 0))
            vectors.extend(item["embedding"] for item in items)
    except Exception as exc:
        print(f"Error embed_texts (Voyage AI): {exc}")
        return None

    if len(vectors) != len(texts):
        print("Error embed_texts (Voyage AI): la cantidad de embeddings no coincide con la de textos.")
        return None
    return vectors


def cosine_similarity(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def rerank_posts_by_relevance(query: str, posts: list[dict]) -> bool:
    """Reordena `posts` en el lugar por relevancia semántica respecto a
    `query` (lo que el usuario escribió, sin los operadores lang:/
    place_country: que agrega la app) y agrega 'semantic_score' a cada post
    (coseno contra el embedding de la query, 'query' vs. 'document' para
    aprovechar el modo asimétrico de Voyage). Devuelve True si se aplicó
    (embeddings disponibles y ambas llamadas funcionaron); False si no — en
    ese caso `posts` queda intacto, en el orden que ya traía de la API de X."""
    if not is_embeddings_available() or not posts:
        return False

    query_vectors = embed_texts([query], input_type="query")
    if not query_vectors:
        return False
    doc_vectors = embed_texts([p.get("text") or "" for p in posts], input_type="document")
    if not doc_vectors:
        return False

    query_vector = query_vectors[0]
    for p, vec in zip(posts, doc_vectors):
        p["semantic_score"] = round(cosine_similarity(query_vector, vec), 3)
    posts.sort(key=lambda p: p.get("semantic_score", 0.0), reverse=True)
    return True
