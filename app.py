import json
import os
from datetime import datetime, timezone

import tweepy
from dotenv import load_dotenv
from flask import Flask, Response, render_template, request

load_dotenv()

BEARER_TOKEN = os.environ.get("X_BEARER_TOKEN", "")

app = Flask(__name__)

TWEET_FIELDS = [
    "id",
    "text",
    "created_at",
    "lang",
    "public_metrics",
    "possibly_sensitive",
    "source",
    "author_id",
]
USER_FIELDS = [
    "id",
    "name",
    "username",
    "created_at",
    "description",
    "location",
    "verified",
    "protected",
    "profile_image_url",
    "public_metrics",
]


def get_client() -> tweepy.Client:
    if not BEARER_TOKEN:
        raise RuntimeError(
            "Falta X_BEARER_TOKEN. Configúralo en .env (local) o en las variables de entorno "
            "de tu hosting (producción), con tu Bearer Token de X Developer."
        )
    return tweepy.Client(bearer_token=BEARER_TOKEN, wait_on_rate_limit=False)


def _iso(value):
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc).isoformat()
    return value


def compute_tweet_kpis(posts: list[dict]) -> dict:
    if not posts:
        return {
            "total_posts": 0,
            "total_likes": 0,
            "total_retweets": 0,
            "total_replies": 0,
            "total_quotes": 0,
            "total_engagement": 0,
            "avg_engagement": 0,
            "unique_authors": 0,
            "verified_authors": 0,
            "top_languages": [],
            "top_post": None,
        }

    total_likes = sum(p["metrics"].get("like_count", 0) for p in posts)
    total_retweets = sum(p["metrics"].get("retweet_count", 0) for p in posts)
    total_replies = sum(p["metrics"].get("reply_count", 0) for p in posts)
    total_quotes = sum(p["metrics"].get("quote_count", 0) for p in posts)
    total_engagement = total_likes + total_retweets + total_replies + total_quotes

    author_ids = {p["author"]["id"] for p in posts if p.get("author")}
    verified_authors = {p["author"]["id"] for p in posts if p.get("author") and p["author"].get("verified")}

    lang_counts: dict[str, int] = {}
    for p in posts:
        lang = p.get("lang") or "und"
        lang_counts[lang] = lang_counts.get(lang, 0) + 1
    top_languages = sorted(lang_counts.items(), key=lambda kv: kv[1], reverse=True)[:5]

    def engagement(p: dict) -> int:
        m = p["metrics"]
        return m.get("like_count", 0) + m.get("retweet_count", 0) + m.get("reply_count", 0) + m.get("quote_count", 0)

    top_post = max(posts, key=engagement)

    return {
        "total_posts": len(posts),
        "total_likes": total_likes,
        "total_retweets": total_retweets,
        "total_replies": total_replies,
        "total_quotes": total_quotes,
        "total_engagement": total_engagement,
        "avg_engagement": round(total_engagement / len(posts), 1),
        "unique_authors": len(author_ids),
        "verified_authors": len(verified_authors),
        "top_languages": top_languages,
        "top_post": {
            "id": top_post["id"],
            "text": top_post["text"],
            "engagement": engagement(top_post),
            "author": top_post.get("author"),
        },
    }


def compute_user_kpis(users: list[dict]) -> dict:
    if not users:
        return {
            "total_users": 0,
            "total_followers": 0,
            "avg_followers": 0,
            "verified_users": 0,
            "protected_users": 0,
            "top_user": None,
        }

    total_followers = sum(u["metrics"].get("followers_count", 0) for u in users)
    verified_users = sum(1 for u in users if u.get("verified"))
    protected_users = sum(1 for u in users if u.get("protected"))
    top_user = max(users, key=lambda u: u["metrics"].get("followers_count", 0))

    return {
        "total_users": len(users),
        "total_followers": total_followers,
        "avg_followers": round(total_followers / len(users), 1),
        "verified_users": verified_users,
        "protected_users": protected_users,
        "top_user": {
            "username": top_user["username"],
            "name": top_user["name"],
            "followers": top_user["metrics"].get("followers_count", 0),
        },
    }


def search_tweets(query: str, max_results: int) -> dict:
    client = get_client()
    response = client.search_recent_tweets(
        query=query,
        max_results=max_results,
        tweet_fields=TWEET_FIELDS,
        expansions=["author_id"],
        user_fields=USER_FIELDS,
    )

    users_by_id = {}
    if response.includes and "users" in response.includes:
        for u in response.includes["users"]:
            users_by_id[u.id] = {
                "id": u.id,
                "username": u.username,
                "name": u.name,
                "created_at": _iso(u.created_at),
                "description": u.description,
                "location": u.location,
                "verified": u.verified,
                "protected": u.protected,
                "profile_image_url": u.profile_image_url,
                "metrics": u.public_metrics,
            }

    posts = []
    for t in response.data or []:
        posts.append(
            {
                "id": t.id,
                "text": t.text,
                "created_at": _iso(t.created_at),
                "lang": t.lang,
                "possibly_sensitive": t.possibly_sensitive,
                "source": t.source,
                "metrics": t.public_metrics,
                "author": users_by_id.get(t.author_id),
            }
        )

    return {
        "mode": "tweets",
        "query": query,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "count": len(posts),
        "meta": response.meta or {},
        "posts": posts,
        "kpis": compute_tweet_kpis(posts),
    }


def search_users(query: str, max_results: int) -> dict:
    client = get_client()
    usernames = [u.strip().lstrip("@") for u in query.split(",") if u.strip()][:100]
    if not usernames:
        return {
            "mode": "users",
            "query": query,
            "fetched_at": datetime.now(timezone.utc).isoformat(),
            "count": 0,
            "users": [],
        }

    response = client.get_users(usernames=usernames, user_fields=USER_FIELDS)

    users: list[dict] = []
    for u in response.data or []:
        users.append(
            {
                "id": u.id,
                "username": u.username,
                "name": u.name,
                "created_at": _iso(u.created_at),
                "description": u.description,
                "location": u.location,
                "verified": u.verified,
                "protected": u.protected,
                "profile_image_url": u.profile_image_url,
                "metrics": u.public_metrics,
            }
        )

    errors = [e.get("detail") for e in (response.errors or [])]
    users = users[:max_results]

    return {
        "mode": "users",
        "query": query,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "count": len(users),
        "errors": errors,
        "users": users,
        "kpis": compute_user_kpis(users),
    }


def parse_search_params(args) -> tuple[str, str, int]:
    mode = args.get("mode", "tweets")
    query = args.get("query", "").strip()
    try:
        max_results = int(args.get("max_results", 10))
    except ValueError:
        max_results = 10
    max_results = max(10, min(max_results, 100))
    return mode, query, max_results


def run_search(mode: str, query: str, max_results: int) -> dict:
    if mode == "users":
        return search_users(query, max_results)
    return search_tweets(query, max_results)


@app.route("/", methods=["GET"])
def index():
    return render_template("index.html", result=None, error=None, form={})


@app.route("/search", methods=["POST"])
def search():
    mode, query, max_results = parse_search_params(request.form)
    form = {"mode": mode, "query": query, "max_results": max_results}

    if not query:
        return render_template("index.html", result=None, error="Escribe una búsqueda.", form=form)

    try:
        result = run_search(mode, query, max_results)
    except tweepy.errors.Unauthorized:
        return render_template(
            "index.html",
            result=None,
            error="Credenciales inválidas. Revisa X_BEARER_TOKEN en las variables de entorno.",
            form=form,
        )
    except tweepy.errors.TooManyRequests:
        return render_template(
            "index.html",
            result=None,
            error="Se alcanzó el límite de peticiones de la API de X. Intenta de nuevo en unos minutos.",
            form=form,
        )
    except tweepy.errors.Forbidden as exc:
        return render_template(
            "index.html",
            result=None,
            error=f"Acceso rechazado por la API de X: {exc}. Tu nivel de acceso puede no incluir este endpoint.",
            form=form,
        )
    except RuntimeError as exc:
        return render_template("index.html", result=None, error=str(exc), form=form)

    return render_template("index.html", result=result, error=None, form=form)


@app.route("/export.json", methods=["GET"])
def export_json():
    mode, query, max_results = parse_search_params(request.args)
    if not query:
        return Response("Falta el parámetro 'query'.", status=400)
    result = run_search(mode, query, max_results)
    payload = json.dumps(result, ensure_ascii=False, indent=2)
    return Response(
        payload,
        mimetype="application/json",
        headers={"Content-Disposition": "attachment; filename=twitter-search.json"},
    )


@app.route("/export.ndjson", methods=["GET"])
def export_ndjson():
    mode, query, max_results = parse_search_params(request.args)
    if not query:
        return Response("Falta el parámetro 'query'.", status=400)
    result = run_search(mode, query, max_results)

    items = result.get("posts") if result.get("mode") == "tweets" else result.get("users")
    lines = [json.dumps(item, ensure_ascii=False) for item in (items or [])]
    payload = "\n".join(lines) + ("\n" if lines else "")
    return Response(
        payload,
        mimetype="application/x-ndjson",
        headers={"Content-Disposition": "attachment; filename=twitter-search.ndjson"},
    )


if __name__ == "__main__":
    app.run(debug=True, port=5000)
