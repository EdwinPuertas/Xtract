import csv
import io
import json
import os
import time
from datetime import datetime, timezone

import requests
import tweepy
from dotenv import load_dotenv
from flask import Flask, Response, redirect, render_template, request, session, url_for

import xauth
from nlp.geo import COUNTRIES, detect_country

load_dotenv()

try:
    from nlp.analysis import analyze_posts

    NLP_AVAILABLE = True
    NLP_IMPORT_ERROR = ""
except Exception as _nlp_exc:  # spaCy/nltk models missing or failed to load
    NLP_AVAILABLE = False
    NLP_IMPORT_ERROR = str(_nlp_exc)

BEARER_TOKEN = os.environ.get("X_BEARER_TOKEN", "")

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "")

TWEET_FIELDS = [
    "id",
    "text",
    "created_at",
    "lang",
    "public_metrics",
    "possibly_sensitive",
    "source",
    "author_id",
    "entities",
    "context_annotations",
    "geo",
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
PLACE_FIELDS = ["country", "country_code", "full_name", "name", "place_type"]

LANG_OPTIONS = {"": "Cualquiera", "es": "Español", "en": "Inglés", "pt": "Portugués", "fr": "Francés", "de": "Alemán", "it": "Italiano"}
DEFAULT_LANG = "es"
COUNTRY_CODES = {c["code"] for c in COUNTRIES}


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


def _extract_hashtags(tweet) -> list[str]:
    entities = tweet.entities or {}
    return sorted({f"#{h['tag']}" for h in entities.get("hashtags", []) if h.get("tag")})


def _extract_categories(tweet) -> list[str]:
    annotations = tweet.context_annotations or []
    return sorted({a["entity"]["name"] for a in annotations if a.get("entity", {}).get("name")})


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
            "top_hashtags": [],
            "top_categories": [],
            "top_countries": [],
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
    hashtag_counts: dict[str, int] = {}
    category_counts: dict[str, int] = {}
    country_counts: dict[str, int] = {}
    for p in posts:
        lang = p.get("lang") or "und"
        lang_counts[lang] = lang_counts.get(lang, 0) + 1
        for tag in p.get("hashtags", []):
            hashtag_counts[tag] = hashtag_counts.get(tag, 0) + 1
        for cat in p.get("categories", []):
            category_counts[cat] = category_counts.get(cat, 0) + 1
        country = p.get("country")
        if country and country.get("name"):
            country_counts[country["name"]] = country_counts.get(country["name"], 0) + 1
    top_languages = sorted(lang_counts.items(), key=lambda kv: kv[1], reverse=True)[:5]
    top_hashtags = sorted(hashtag_counts.items(), key=lambda kv: kv[1], reverse=True)[:10]
    top_categories = sorted(category_counts.items(), key=lambda kv: kv[1], reverse=True)[:10]
    top_countries = sorted(country_counts.items(), key=lambda kv: kv[1], reverse=True)[:5]

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
        "top_hashtags": top_hashtags,
        "top_categories": top_categories,
        "top_countries": top_countries,
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


def _build_user_dict(u) -> dict:
    return {
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


def _build_post_dict(t, users_by_id: dict, places_by_id: dict | None = None) -> dict:
    places_by_id = places_by_id or {}
    place = None
    if t.geo and t.geo.get("place_id"):
        place = places_by_id.get(t.geo["place_id"])
    author = users_by_id.get(t.author_id)

    return {
        "id": t.id,
        "text": t.text,
        "created_at": _iso(t.created_at),
        "lang": t.lang,
        "possibly_sensitive": t.possibly_sensitive,
        "source": t.source,
        "metrics": t.public_metrics,
        "author": author,
        "hashtags": _extract_hashtags(t),
        "categories": _extract_categories(t),
        "place": place,
        "country": detect_country(place, author.get("location") if author else None),
    }


def _users_by_id_from_includes(response) -> dict:
    users_by_id = {}
    if response.includes and "users" in response.includes:
        for u in response.includes["users"]:
            users_by_id[u.id] = _build_user_dict(u)
    return users_by_id


def _places_by_id_from_includes(response) -> dict:
    places_by_id = {}
    if response.includes and "places" in response.includes:
        for place in response.includes["places"]:
            places_by_id[place.id] = {
                "id": place.id,
                "name": place.name,
                "full_name": place.full_name,
                "country": place.country,
                "country_code": place.country_code,
                "place_type": place.place_type,
            }
    return places_by_id


def search_tweets(query: str, max_results: int) -> dict:
    client = get_client()
    response = client.search_recent_tweets(
        query=query,
        max_results=max_results,
        tweet_fields=TWEET_FIELDS,
        expansions=["author_id", "geo.place_id"],
        user_fields=USER_FIELDS,
        place_fields=PLACE_FIELDS,
    )

    users_by_id = _users_by_id_from_includes(response)
    places_by_id = _places_by_id_from_includes(response)
    posts = [_build_post_dict(t, users_by_id, places_by_id) for t in response.data or []]

    return {
        "mode": "tweets",
        "query": query,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "count": len(posts),
        "meta": response.meta or {},
        "posts": posts,
        "kpis": compute_tweet_kpis(posts),
    }


def get_user_timeline(user_id: str, max_results: int) -> dict:
    client = get_client()
    user_response = client.get_user(id=user_id, user_fields=USER_FIELDS)
    if not user_response.data:
        raise RuntimeError("Usuario no encontrado.")
    profile = _build_user_dict(user_response.data)

    tweets_response = client.get_users_tweets(
        id=user_id,
        max_results=max_results,
        tweet_fields=TWEET_FIELDS,
        exclude=["retweets", "replies"],
        expansions=["geo.place_id"],
        place_fields=PLACE_FIELDS,
    )
    users_by_id = {profile["id"]: profile}
    places_by_id = _places_by_id_from_includes(tweets_response)
    posts = [_build_post_dict(t, users_by_id, places_by_id) for t in tweets_response.data or []]

    return {
        "mode": "tweets",
        "query": f"from:{profile['username']}",
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "count": len(posts),
        "meta": tweets_response.meta or {},
        "posts": posts,
        "kpis": compute_tweet_kpis(posts),
        "profile": profile,
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


GROUP_BY_OPTIONS = {"none", "hashtag", "category"}


def parse_search_params(args) -> tuple[str, str, int, str, str]:
    mode = args.get("mode", "tweets")
    query = args.get("query", "").strip()
    try:
        max_results = int(args.get("max_results", 10))
    except ValueError:
        max_results = 10
    max_results = max(10, min(max_results, 100))

    lang = args.get("lang", DEFAULT_LANG)
    if lang not in LANG_OPTIONS:
        lang = DEFAULT_LANG

    country = args.get("country", "").strip().upper()
    if country not in COUNTRY_CODES:
        country = ""

    return mode, query, max_results, lang, country


def _augment_query(query: str, lang: str, country: str) -> str:
    """Agrega los operadores lang: / place_country: a la búsqueda de posts,
    salvo que el usuario ya los haya escrito manualmente en su búsqueda."""
    lowered = query.lower()
    parts = [query]
    if lang and "lang:" not in lowered:
        parts.append(f"lang:{lang}")
    if country and "place_country:" not in lowered:
        parts.append(f"place_country:{country}")
    return " ".join(parts)


def run_search(mode: str, query: str, max_results: int, lang: str = "", country: str = "") -> dict:
    if mode == "users":
        return search_users(query, max_results)
    return search_tweets(_augment_query(query, lang, country), max_results)


def group_posts(posts: list[dict], group_by: str) -> list[dict]:
    field = "hashtags" if group_by == "hashtag" else "categories"
    fallback = "Sin hashtag" if group_by == "hashtag" else "Sin categoría"

    groups: dict[str, list[dict]] = {}
    for p in posts:
        keys = p.get(field) or [fallback]
        for key in keys:
            groups.setdefault(key, []).append(p)

    ordered = sorted(groups.items(), key=lambda kv: len(kv[1]), reverse=True)
    return [{"key": key, "posts": items, "count": len(items)} for key, items in ordered]


@app.context_processor
def inject_connected():
    return {"connected": bool(session.get("access_token"))}


@app.context_processor
def inject_search_filters():
    return {"lang_options": LANG_OPTIONS, "countries": COUNTRIES, "default_lang": DEFAULT_LANG}


def get_user_access_token() -> str:
    token = session.get("access_token")
    if not token:
        raise RuntimeError("No has conectado tu cuenta de X todavía.")

    expires_at = session.get("token_expires_at", 0)
    refresh = session.get("refresh_token")
    if time.time() > expires_at - 30 and refresh:
        data = xauth.refresh_access_token(refresh)
        session["access_token"] = data["access_token"]
        session["refresh_token"] = data.get("refresh_token", refresh)
        session["token_expires_at"] = time.time() + data.get("expires_in", 7200)
        token = session["access_token"]
    return token


@app.route("/", methods=["GET"])
def index():
    return render_template("index.html", result=None, error=None, form={})


@app.route("/timeline/<user_id>", methods=["GET"])
def timeline(user_id):
    max_results = min(max(int(request.args.get("max_results", 20)), 5), 100)
    try:
        result = get_user_timeline(user_id, max_results)
    except tweepy.errors.TweepyException as exc:
        return render_template("timeline.html", result=None, profile=None, error=str(exc))
    except RuntimeError as exc:
        return render_template("timeline.html", result=None, profile=None, error=str(exc))

    return render_template("timeline.html", result=result, profile=result["profile"], error=None)


@app.route("/search", methods=["POST"])
def search():
    mode, query, max_results, lang, country = parse_search_params(request.form)
    group_by = request.form.get("group_by", "none")
    if group_by not in GROUP_BY_OPTIONS:
        group_by = "none"
    analyze_text = request.form.get("analyze_text") == "on"
    form = {
        "mode": mode,
        "query": query,
        "max_results": max_results,
        "group_by": group_by,
        "analyze_text": analyze_text,
        "lang": lang,
        "country": country,
    }

    if not query:
        return render_template("index.html", result=None, error="Escribe una búsqueda.", form=form)

    try:
        result = run_search(mode, query, max_results, lang, country)
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
    except tweepy.errors.BadRequest as exc:
        return render_template(
            "index.html",
            result=None,
            error=(
                f"La API de X rechazó la búsqueda: {exc}. Si filtraste por país, el operador "
                "'place_country:' puede no estar disponible en tu nivel de acceso."
            ),
            form=form,
        )
    except RuntimeError as exc:
        return render_template("index.html", result=None, error=str(exc), form=form)

    if result.get("mode") == "tweets" and group_by != "none":
        result["grouped"] = group_posts(result["posts"], group_by)

    nlp_error = None
    if result.get("mode") == "tweets" and analyze_text:
        if NLP_AVAILABLE:
            try:
                result["nlp"] = analyze_posts(result["posts"])
            except Exception as exc:
                nlp_error = f"No se pudo completar el análisis de texto: {exc}"
        else:
            nlp_error = f"El análisis de texto no está disponible en este despliegue: {NLP_IMPORT_ERROR}"

    return render_template("index.html", result=result, error=nlp_error, form=form)


@app.route("/export.json", methods=["GET"])
def export_json():
    mode, query, max_results, lang, country = parse_search_params(request.args)
    if not query:
        return Response("Falta el parámetro 'query'.", status=400)
    result = run_search(mode, query, max_results, lang, country)
    payload = json.dumps(result, ensure_ascii=False, indent=2)
    return Response(
        payload,
        mimetype="application/json",
        headers={"Content-Disposition": "attachment; filename=twitter-search.json"},
    )


@app.route("/export.ndjson", methods=["GET"])
def export_ndjson():
    mode, query, max_results, lang, country = parse_search_params(request.args)
    if not query:
        return Response("Falta el parámetro 'query'.", status=400)
    result = run_search(mode, query, max_results, lang, country)

    items = result.get("posts") if result.get("mode") == "tweets" else result.get("users")
    lines = [json.dumps(item, ensure_ascii=False) for item in (items or [])]
    payload = "\n".join(lines) + ("\n" if lines else "")
    return Response(
        payload,
        mimetype="application/x-ndjson",
        headers={"Content-Disposition": "attachment; filename=twitter-search.ndjson"},
    )


TWEET_CSV_COLUMNS = [
    "id", "text", "created_at", "lang", "like_count", "retweet_count",
    "reply_count", "quote_count", "author_username", "author_name",
    "author_followers", "hashtags", "categories", "country",
]
USER_CSV_COLUMNS = [
    "id", "username", "name", "followers_count", "following_count",
    "tweet_count", "listed_count", "verified", "protected", "location",
    "created_at", "description",
]


def _tweet_to_csv_row(p: dict) -> list:
    m = p.get("metrics") or {}
    author = p.get("author") or {}
    country = p.get("country") or {}
    return [
        p.get("id"), p.get("text"), p.get("created_at"), p.get("lang"),
        m.get("like_count"), m.get("retweet_count"), m.get("reply_count"), m.get("quote_count"),
        author.get("username"), author.get("name"), (author.get("metrics") or {}).get("followers_count"),
        " ".join(p.get("hashtags") or []), "; ".join(p.get("categories") or []), country.get("name"),
    ]


def _user_to_csv_row(u: dict) -> list:
    m = u.get("metrics") or {}
    return [
        u.get("id"), u.get("username"), u.get("name"), m.get("followers_count"),
        m.get("following_count"), m.get("tweet_count"), m.get("listed_count"),
        u.get("verified"), u.get("protected"), u.get("location"), u.get("created_at"),
        u.get("description"),
    ]


@app.route("/export.csv", methods=["GET"])
def export_csv():
    mode, query, max_results, lang, country = parse_search_params(request.args)
    if not query:
        return Response("Falta el parámetro 'query'.", status=400)
    result = run_search(mode, query, max_results, lang, country)

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    if result.get("mode") == "tweets":
        writer.writerow(TWEET_CSV_COLUMNS)
        for p in result.get("posts") or []:
            writer.writerow(_tweet_to_csv_row(p))
    else:
        writer.writerow(USER_CSV_COLUMNS)
        for u in result.get("users") or []:
            writer.writerow(_user_to_csv_row(u))

    return Response(
        "﻿" + buffer.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=twitter-search.csv"},
    )


@app.route("/login", methods=["GET"])
def login():
    if not app.secret_key:
        return render_template(
            "index.html",
            result=None,
            error="Falta FLASK_SECRET_KEY en las variables de entorno.",
            form={}
        )

    state = xauth.new_state()
    verifier, challenge = xauth.new_pkce_pair()
    session["oauth_state"] = state
    session["oauth_verifier"] = verifier

    try:
        auth_url = xauth.build_authorize_url(state, challenge)
    except RuntimeError as exc:
        return render_template("index.html", result=None, error=str(exc), form={})

    return redirect(auth_url)


@app.route("/callback", methods=["GET"])
def callback():
    oauth_error = request.args.get("error")
    if oauth_error:
        return render_template(
            "index.html",
            result=None,
            error=f"X rechazó la autorización: {oauth_error}",
            form={}
        )

    state = request.args.get("state")
    code = request.args.get("code")
    expected_state = session.pop("oauth_state", None)
    verifier = session.pop("oauth_verifier", None)

    if not state or state != expected_state:
        return render_template(
            "index.html",
            result=None,
            error="Estado OAuth inválido o expirado. Intenta conectar tu cuenta de nuevo.",
            form={}
        )

    if not code or not verifier:
        return render_template(
            "index.html", result=None, error="Falta el código de autorización.", form={}
        )

    try:
        token_data = xauth.exchange_code(code, verifier)
    except requests.HTTPError as exc:
        detail = exc.response.text if exc.response is not None else str(exc)
        return render_template(
            "index.html",
            result=None,
            error=f"No se pudo obtener el token de acceso: {detail}",
            form={}
        )

    session["access_token"] = token_data["access_token"]
    session["refresh_token"] = token_data.get("refresh_token")
    session["token_expires_at"] = time.time() + token_data.get("expires_in", 7200)
    return redirect(url_for("account"))


@app.route("/logout", methods=["GET"])
def logout():
    session.clear()
    return redirect(url_for("index"))


def get_authenticated_client() -> tweepy.Client:
    token = get_user_access_token()
    return tweepy.Client(bearer_token=token)


def fetch_me(client: tweepy.Client):
    try:
        return client.get_me(user_fields=USER_FIELDS, user_auth=False).data, None
    except tweepy.errors.TweepyException as exc:
        return None, str(exc)


@app.route("/account", methods=["GET"])
def account():
    try:
        client = get_authenticated_client()
    except RuntimeError:
        return redirect(url_for("login"))

    me, profile_error = fetch_me(client)
    return render_template("account.html", user=me, error=profile_error, posted=None, can_post=True)


@app.route("/post", methods=["POST"])
def post_tweet():
    text = request.form.get("text", "").strip()

    try:
        client = get_authenticated_client()
    except RuntimeError:
        return redirect(url_for("login"))

    me, profile_error = fetch_me(client)

    if not text:
        return render_template(
            "account.html", user=me, error="Escribe algo para publicar.", posted=None, can_post=True
        )

    try:
        response = client.create_tweet(text=text, user_auth=False)
        return render_template("account.html", user=me, error=None, posted=response.data, can_post=True)
    except tweepy.errors.TweepyException as exc:
        return render_template(
            "account.html", user=me, error=f"No se pudo publicar: {exc}", posted=None, can_post=True
        )


if __name__ == "__main__":
    app.run(debug=True, port=5000)
