# Xtract

App web sencilla (Flask) para buscar posts o usuarios en X y ver sus metadatos y KPIs
(métricas, fechas, autor, seguidores, etc.), usando la API oficial de X (v2).

## Requisitos

- Python 3.10+
- Un Bearer Token de la [X Developer Portal](https://developer.twitter.com/en/portal/dashboard)
  (App -> Keys and tokens -> Bearer Token). Con esto alcanza; no hace falta OAuth de usuario.
- Nivel de acceso: la búsqueda de posts (`search_recent_tweets`) requiere como mínimo
  el nivel **Basic** (de pago) de la API de X. El nivel Free solo permite publicar tweets,
  no buscarlos. La consulta de usuarios (`get_users`) sí está disponible en Free.

## Instalación

```bash
cd twitter-search-app
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```

Edita `.env` y pega tu `X_BEARER_TOKEN`.

## Ejecutar

```bash
python app.py
```

Abre http://localhost:5000

## Uso

- **Buscar posts**: usa la sintaxis de búsqueda de X, p. ej. `from:nasa`, `#IA lang:es`,
  `"inteligencia artificial" -is:retweet`.
- **Buscar usuarios**: escribe uno o varios `@usuario` separados por comas, p. ej. `nasa, spacex`.
- Cada búsqueda se puede exportar como **JSON** o **NDJSON** (un objeto por línea) desde
  los enlaces sobre los resultados.

## Notas

- Las credenciales se leen de `.env` (local) o de las variables de entorno del hosting
  (producción). `.env` está en `.gitignore` — nunca lo subas a un repositorio.
- Exportar JSON/NDJSON vuelve a ejecutar la búsqueda en el momento de la descarga (no hay
  caché de resultados), para que funcione igual en local y en despliegues serverless.

## Desplegar en Vercel

El repo ya incluye `vercel.json` (usa el runtime `@vercel/python`, que ejecuta `app.py`
como función serverless e incluye `templates/` y `static/`).

1. Sube el proyecto a un repo de GitHub (o usa `vercel` desde la CLI directamente).
2. En Vercel: **Add New Project** → importa el repo (o corre `vercel` en esta carpeta con
   la [Vercel CLI](https://vercel.com/docs/cli) ya instalada y con `vercel login` hecho).
3. En **Settings → Environment Variables** agrega `X_BEARER_TOKEN` con tu Bearer Token de
   X Developer Portal (para Production, Preview y Development).
4. Deploy. Vercel detecta `vercel.json` y despliega `app.py` como función Python.

Importante: cada invocación es una función serverless independiente y sin estado —
por eso las exportaciones re-consultan la API de X en vez de usar un caché en memoria del
servidor. Ten en cuenta tu cuota mensual de la API si exportas seguido.
