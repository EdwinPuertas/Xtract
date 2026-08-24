# Xtract

App web (Flask) para X (Twitter): busca posts o usuarios con metadatos y KPIs usando la
API v2 app-only, y permite conectar tu cuenta (OAuth 2.0) para publicar tweets en tu nombre.

## Requisitos

- Python 3.10+
- Un App dentro de un **Project** en el [X Developer Portal](https://developer.twitter.com/en/portal/dashboard)
  (desde 2023 todo App debe vivir dentro de un Project; los standalone Apps antiguos no
  funcionan con la API v2).
- **Importante sobre acceso de lectura (búsqueda):** desde feb. 2026 X pasó a un modelo de
  **pago por uso** (créditos). El nivel Free heredado es solo-escritura — no permite ni
  siquiera leer tu propio perfil. Para que la búsqueda de posts/usuarios funcione necesitas
  cargar créditos en el Project (Billing/Usage en el portal).

## Dos formas de autenticación (usos distintos)

| | Variables | Para qué sirve | Requiere créditos de lectura |
|---|---|---|---|
| **Bearer Token** (app-only) | `X_BEARER_TOKEN` | Buscar posts/usuarios de cualquiera | Sí |
| **OAuth 2.0** (login de usuario) | `X_CLIENT_ID`, `X_CLIENT_SECRET`, `X_REDIRECT_URI` | Publicar/interactuar como tú mismo | Costos de escritura aparte, no depende de créditos de lectura |

## Instalación

```bash
cd xtract
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```

Completa `.env` con:

1. **`X_BEARER_TOKEN`** — App -> Keys and tokens -> Bearer Token.
2. **`X_CLIENT_ID` / `X_CLIENT_SECRET`** — App -> Keys and tokens -> OAuth 2.0 Client ID and
   Client Secret. Trátalo como una contraseña: si alguna vez se expone (pantallazo, chat,
   log), regenéralo de inmediato desde el portal.
3. Habilita OAuth 2.0 en **App -> User authentication settings**:
   - Type of App: **Web App, Automated App or Bot** (confidential client)
   - Callback URI / Redirect URL: agrega `http://127.0.0.1:5000/callback` (local) y tu URL
     de producción, p. ej. `https://xtract-five.vercel.app/callback`
4. **`X_REDIRECT_URI`** — debe coincidir EXACTAMENTE (protocolo, host, puerto, path) con uno
   de los Callback URI registrados. En local: `http://127.0.0.1:5000/callback`.
5. **`FLASK_SECRET_KEY`** — ya viene generada en tu `.env` local (firma la cookie de sesión
   del login). Genera una distinta para producción con:
   ```bash
   python -c "import secrets; print(secrets.token_hex(32))"
   ```

## Ejecutar

```bash
python app.py
```

Abre http://127.0.0.1:5000 (usa `127.0.0.1`, no `localhost`, para que coincida con el
Callback URI registrado en X).

## Uso

- **Buscar posts**: usa la sintaxis de búsqueda de X, p. ej. `from:nasa`, `#IA lang:es`,
  `"inteligencia artificial" -is:retweet`.
- **Buscar usuarios**: escribe uno o varios `@usuario` separados por comas, p. ej. `nasa, spacex`.
- **Agrupar por** (solo búsqueda de posts): agrupa los resultados en pantalla por hashtag,
  por categoría (usa `context_annotations` de la API de X, clasificación temática nativa de
  cada post — Tecnología, Deportes, etc.), por **sentimiento** (positivo/neutral/negativo) o
  por **emoción VAD** (alegría, enojo, calma, sorpresa, alivio, aburrimiento, miedo, tristeza).
  Un post con varios hashtags/categorías aparece en cada grupo correspondiente.
- El resumen de KPIs también incluye los hashtags, categorías y países más frecuentes de la
  búsqueda.
- Cada búsqueda se puede exportar como **JSON**, **NDJSON** (un objeto por línea) o **CSV**
  (con columnas planas, incluyendo hashtags/categorías/país) desde los enlaces sobre los
  resultados.
- **Conectar cuenta de X**: botón en la parte superior → autoriza en X → vuelves a Xtract
  con tu perfil y un cuadro para publicar tweets.
- **Timeline de usuario**: haz clic en cualquier autor (en resultados de posts o de usuarios)
  para ver sus últimos posts, KPIs y exportar esa vista.
- **Análisis de texto automático** (solo búsqueda de posts, siempre activo): cada búsqueda de
  posts corre un análisis lingüístico con spaCy/NLTK — sintagmas nominales (tópicos
  frecuentes), bigramas/trigramas, sentimiento por post (positivo/neutral/negativo, basado en
  un léxico de adjetivos en español/inglés) y **emociones por post según el modelo VAD**
  (valencia, activación, dominancia) usando el NRC VAD Lexicon v2. Esto añade latencia a cada
  búsqueda de posts a cambio de tener siempre tópicos/sentimiento/emociones disponibles (y
  poder agrupar por ellos).
- **Idioma** (solo búsqueda de posts): filtra por idioma con el operador `lang:` de la API
  de X. Por defecto es **español (`es`)**; puedes cambiarlo o dejarlo en "Cualquiera".
- **País** (solo búsqueda de posts): filtra con el operador `place_country:` de la API de X.
  Solo aplica a posts geoetiquetados (la mayoría de los posts no lo están, ya que el usuario
  debe activar la ubicación de forma explícita), y requiere que tu nivel de acceso a la API
  soporte ese operador. Si tu app lo rechaza, el resultado de "país" seguirá calculándose por
  post a partir de la ubicación de perfil de cada autor (ver punto siguiente).
- **País detectado por post**: cada post muestra un país inferido — a partir de su
  geoetiquetado si lo tiene, o si no, de un análisis heurístico del campo de ubicación libre
  del perfil del autor (`nlp/geo.py`). Es una aproximación, no un dato verificado por X.

## Vista de tendencias (`/trends`)

Además del análisis por búsqueda, Xtract corre un job periódico que recolecta hasta 1000
posts para una consulta fija y guarda un resumen histórico, para poder ver la evolución en
el tiempo de tópicos, tendencias, sentimiento y emociones — no solo el estado de una
búsqueda puntual.

### Cómo funciona

1. **`/api/cron/trends`** (`app.py` + `trends_job.py`): recolecta hasta `TRENDS_TARGET_POSTS`
   posts (1000 por defecto, paginando de a 100 con `next_token`) para la consulta
   `TRENDS_QUERY`, calcula KPIs sobre todos ellos (barato: solo conteos) y un análisis de
   texto completo (spaCy/NLTK: tópicos, bigramas/trigramas, sentimiento, emociones VAD) sobre
   los primeros `TRENDS_ANALYZE_MAX_POSTS` (300 por defecto — el análisis con spaCy es
   costoso por post; se limita para no exceder el tiempo máximo de una función serverless).
   El resumen agregado (no el detalle por post) se guarda en la base de datos vía
   `trends_store.save_run`.
2. **Vercel Cron Job** (`vercel.json`): invoca ese endpoint una vez al día, a las 17:00 UTC
   (mediodía en Colombia, UTC-5) — el plan gratuito (Hobby) de Vercel solo permite una
   ejecución diaria por cron; si tienes plan Pro y quieres correrlo cada 12 horas, agrega una
   segunda entrada en `vercel.json` con otro horario.
3. **`/trends`** (`app.py` + `charts.py` + `templates/trends.html`): lee las últimas 60
   corridas guardadas y dibuja dos gráficas de línea (SVG, sin librerías externas) —
   sentimiento y emociones VAD en el tiempo, como % de los posts analizados por corrida —
   más un historial cronológico con los hashtags, tópicos, bigramas, trigramas, países e
   idiomas más frecuentes de cada corrida.

### Configuración necesaria

Vercel no tiene disco persistente entre invocaciones serverless, así que el histórico se
guarda en una base de datos Postgres externa:

1. Crea una base de datos Postgres gratuita en [Neon](https://neon.tech),
   [Supabase](https://supabase.com) o Vercel Postgres.
2. Define `DATABASE_URL` (local en `.env`, producción en las variables de entorno de Vercel)
   con la cadena de conexión. `trends_store.py` crea la tabla `trend_runs` automáticamente en
   el primer uso (no hace falta migrar nada a mano).
3. (Opcional) Ajusta `TRENDS_QUERY`, `TRENDS_TARGET_POSTS` y `TRENDS_ANALYZE_MAX_POSTS` según
   qué quieras rastrear y cuánto tiempo/crédito de API quieras gastar por corrida.
4. (Opcional pero recomendado en producción) Define `CRON_SECRET` — Vercel lo envía
   automáticamente como header `Authorization: Bearer <CRON_SECRET>` en sus Cron Jobs, así
   que cualquier otra petición a `/api/cron/trends` sin ese header recibe `401`.

Si `DATABASE_URL` no está configurada (o `psycopg2` no está instalado), `/trends` y
`/api/cron/trends` muestran un error explicando qué falta, sin afectar el resto de la app
(búsqueda, timeline, login).

### Probarlo manualmente

```bash
curl -X POST http://127.0.0.1:5000/api/cron/trends
```

(agrega el header `Authorization: Bearer <CRON_SECRET>` si lo configuraste). Cada corrida de
1000 posts con análisis de 300 puede tardar uno o varios minutos, sobre todo la primera vez
que se cargan los modelos de spaCy.

## Módulo `nlp/` (código propietario de análisis lingüístico y detección de país)

El paquete `nlp/` contiene el motor propio de procesamiento de lenguaje natural que
alimenta el análisis automático de cada búsqueda de posts y el job de tendencias. No es una
dependencia externa: es lógica propietaria de Xtract, construida sobre spaCy y NLTK como
librerías base. Se activa desde `app.py` (`from nlp.analysis import analyze_posts`) en cada
búsqueda de posts, y desde `trends_job.py` en cada corrida programada; añade latencia
a la búsqueda.

### `nlp/__init__.py`

Vacío; solo marca `nlp/` como paquete Python importable.

### `nlp/text_processing.py` — clase `TextProcessing`

Encapsula todo el pipeline de limpieza y anotación lingüística de un texto, con soporte
para español (`es`) e inglés (`en`):

- **Carga de modelos spaCy** (`load_spacy`): carga perezosa de `es_core_news_sm` o
  `en_core_web_sm` según el idioma, con manejo de errores si el modelo no está instalado.
- **Extensión de token personalizada** (`Token._.stem`): registra en spaCy un atributo
  `stem` que calcula el stem (raíz) de cada token usando `SnowballStemmer` de NLTK
  (`_STEMMERS`, uno por idioma), evitando recomputarlo si ya existe.
- **`proper_encoding`**: normaliza texto Unicode a ASCII (NFD + strip de diacríticos) para
  homogeneizar tildes/caracteres especiales.
- **`stopwords`**: tokeniza con spaCy (`Spanish`/`English` vacíos, sin modelo entrenado, solo
  para el vocabulario de stopwords) y filtra las palabras vacías del idioma.
- **`remove_patterns`**: limpieza por expresiones regulares de símbolos, signos de puntuación,
  paréntesis/corchetes, operadores y números sueltos; pasa el texto a minúsculas.
- **`transformer`**: pipeline principal de normalización de un post — quita emojis (rango
  Unicode de emoji), URLs, menciones (`@usuario`) y hashtags (`#tag`) vía regex, aplica
  `remove_patterns`, opcionalmente elimina stopwords, colapsa espacios y devuelve `None` si
  el resultado queda vacío.
- **`tokenizer`**: tokeniza usando `TweetTokenizer` de NLTK (pensado para texto de redes
  sociales: conserva emoticonos, maneja repeticiones de letras, etc.).
- **`make_ngrams`**: genera bigramas/trigramas (o el n que se indique) a partir del texto
  tokenizado, usando `nltk.util.ngrams`.
- **`tagger`**: corre el texto por el pipeline de spaCy y devuelve, por token, texto, lema,
  stem (vía la extensión `_.stem`), POS, tag morfológico, dependencia sintáctica y flags
  `is_alpha`/`is_stop`.
- **`noun_phrases`**: extrae los sintagmas nominales (`doc.noun_chunks`) del texto, útil
  para detectar los "temas" o tópicos mencionados en un post.

### `nlp/lexical_features.py` — diccionarios `lexical_es` / `lexical_en`

Recursos léxicos propios (listas de palabras curadas a mano), usados como base de reglas
para el análisis de sentimiento y categorización semántica. Cada diccionario agrupa
palabras por categoría gramatical/semántica:

- Pronombres personales por persona y número (`first_person_singular`, `third_person_plurar`, etc.).
- Adverbios de tiempo, negación, lugar, modo y cantidad (`adverb_time`, `adverb_neg`,
  `adverb_place`, `adverb_mode`, `adverb_cant`).
- **Adjetivos positivos y negativos** (`adjetives_pos`, `adjetives_neg`): son el léxico que
  usa `analysis.py` para calcular el sentimiento de cada post.
- Sustantivos de roles/personas por género (`who_general`, `who_male`, `who_female`).
- Vocabulario asociado a "odio"/hostilidad (`hate`), reservado para futuras clasificaciones
  de discurso de odio o toxicidad.

### `nlp/analysis.py` — función `analyze_posts`

Orquesta el análisis de un lote de posts y es el punto de entrada que consume `app.py`:

- **`_ensure_nltk_data`**: descarga bajo demanda los recursos de NLTK (`punkt_tab`/`punkt`)
  a un directorio configurable (`NLTK_DATA`, por defecto `/tmp/nltk_data`, pensado para
  entornos serverless de solo-lectura como Vercel), y solo lo hace una vez por proceso.
- **`get_processor`**: cachea una instancia de `TextProcessing` por idioma (`_PROCESSORS`)
  para no recargar el modelo de spaCy en cada post.
- **`_score_sentiment`**: calcula un score de sentimiento simple por conteo — cuenta cuántos
  tokens del post aparecen en `adjetives_pos` vs `adjetives_neg` del lexicón del idioma
  correspondiente, y normaliza `(pos - neg) / (pos + neg)`. Clasifica el resultado como
  `positivo` (> 0.15), `negativo` (< -0.15) o `neutral` en el resto de los casos.
- **`analyze_posts(posts, max_posts=60)`**: función principal.
  1. Limita el análisis a los primeros `max_posts` posts (por costo de cómputo).
  2. Para cada post: detecta idioma (`es`/`en`, default `es`), limpia el texto
     (`TextProcessing.transformer`), lo tokeniza y extrae bigramas, trigramas y sintagmas
     nominales, acumulando frecuencias globales con `collections.Counter`.
  3. Calcula el sentimiento y las emociones VAD de cada post individualmente.
  4. Devuelve un diccionario con: `analyzed_count`, los 15 bigramas/trigramas/sintagmas
     nominales más frecuentes (`top_bigrams`, `top_trigrams`, `top_noun_phrases`), el detalle
     de sentimiento por post indexado por `id` (`sentiments`), un resumen de conteos por
     etiqueta (`sentiment_summary`), el detalle de emociones VAD por post (`vad`) y un
     resumen (`vad_summary`) con el conteo por emoción y la fuente del léxico usado.

Este resultado (`result["nlp"]`) es lo que consume `templates/index.html` para pintar los
tópicos frecuentes, n-gramas, sentimiento y emociones junto a los resultados de la búsqueda.

### `nlp/vad_lexicon.py` — carga del NRC VAD Lexicon

Loader del **NRC Valence-Arousal-Dominance (VAD) Lexicon**. El léxico real (v2.1, en inglés,
54 801 términos) ya está incluido en `nlp/NRC-VAD-Lexicon-v2.1.txt` — ver
`nlp/resources/README.md` para su formato, la limitación de que solo cubre inglés, y la nota
sobre licencia. `load_lexicon` busca, en orden, la ruta en `NRC_VAD_LEXICON_PATH`,
`nlp/NRC-VAD-Lexicon-v2.1.txt`, `nlp/resources/NRC-VAD-Lexicon-v2.1.txt` y
`nlp/resources/NRC-VAD-Lexicon-v2.txt`; parsea líneas `término<TAB>valence<TAB>arousal<TAB>dominance`
y cachea el resultado en memoria. El archivo oficial de NRC usa escala **-1..1** con 0 como
neutro; si detecta valores negativos, `load_lexicon` los remapea automáticamente a **0..1**
con 0.5 como neutro (la escala que usa el resto del módulo). Si no encuentra ningún archivo,
devuelve un diccionario vacío en vez de fallar. `is_lexicon_available()` indica si hay datos
reales cargados.

### `nlp/vad_emotion.py` — algoritmo de emociones (modelo VAD)

Calcula la emoción de un texto a partir del promedio de valencia/activación/dominancia de
sus palabras:

- **`compute_vad(text, lang="es")`**: tokeniza el texto (`TextProcessing.tokenizer`), busca
  cada token en el NRC VAD Lexicon (vía `vad_lexicon.load_lexicon`) y promedia los valores
  `valence`/`arousal`/`dominance` de las palabras encontradas. Clasifica el resultado en una
  emoción discreta (`alegría`, `sorpresa`, `calma`, `alivio`, `enojo`, `miedo`,
  `aburrimiento`, `tristeza` o `neutral`) con `_label_from_vad`, una heurística de octantes
  sobre el espacio VAD (signo de cada dimensión respecto al punto neutro 0.5, con una banda
  muerta de ±0.08 alrededor del centro para el caso `neutral`).
- Si el NRC VAD Lexicon real no está instalado, usa `_fallback_lexicon`: un léxico mucho más
  pequeño derivado de los adjetivos positivos/negativos de `lexical_features.py` (valencia
  aproximada 0.8/0.2, activación y dominancia neutras en 0.5). El resultado siempre incluye
  `source` (`nrc_vad_v2` o `fallback_lexico_propio`) para saber qué tan confiable es.
- Si ninguna palabra del texto está en el léxico disponible, devuelve `emotion: "sin_datos"`.

### `nlp/geo.py` — detección heurística del país de un post

No usa geocodificación externa. `COUNTRIES` es un catálogo propio (código ISO, nombre,
gentilicios/alias y ciudades principales) para un conjunto de países de habla hispana más
algunos adicionales (usado también para poblar el selector de país del formulario de
búsqueda). `detect_country(place, author_location)`:

1. Si el post está geoetiquetado (`place` viene de la expansión `geo.place_id` de la API de
   X, con `country`/`country_code`), usa ese dato — es la fuente más confiable.
2. Si no, intenta inferir el país normalizando (minúsculas, sin tildes) el campo de
   ubicación libre del perfil del autor (`location`) y buscando coincidencias contra los
   nombres/alias/ciudades del catálogo `COUNTRIES`.
3. Si no hay coincidencia, devuelve `None`.

El resultado incluye `source` (`"geolocalización del post"` o `"ubicación del perfil
(aproximado)"`) para que quede claro que el segundo caso es una aproximación y no un dato
verificado por X. Se usa en `app.py` (`_build_post_dict`) para anotar cada post con su
`country`, y en `compute_tweet_kpis` para el resumen `top_countries`.

### `nlp/utils.py` — clase `Utils`

Utilidad genérica de manejo de errores: `standard_error(exc_info)` imprime el traceback
completo de una excepción a partir de la tupla `sys.exc_info()`, usada para depuración
uniforme sin interrumpir el flujo de la aplicación.

## Módulos auxiliares de la vista de tendencias (raíz del proyecto)

### `trends_store.py`

Persistencia en Postgres del histórico de corridas. `ensure_schema()` crea la tabla
`trend_runs` (`run_at`, `query`, `post_count`, `analyzed_count`, `kpis` y `nlp` como
columnas `JSONB`) si no existe — no hay migraciones que correr a mano. `save_run(...)`
inserta una fila; `get_recent_runs(limit=60)` trae las últimas `limit` corridas ordenadas de
la más antigua a la más reciente (el orden que necesita una gráfica de serie de tiempo).
Cada función abre y cierra su propia conexión (`psycopg2.connect(DATABASE_URL)`), apropiado
para invocaciones serverless cortas y poco frecuentes (una vez al día) en vez de un pool de
conexiones persistente.

### `trends_job.py`

El job que corre `/api/cron/trends`. `fetch_posts(query, target)` pagina
`search_recent_tweets` con `next_token` hasta juntar `target` posts (100 por página, el
máximo de la API). `run_trends_job()` orquesta todo: recolecta los posts, calcula KPIs sobre
todos ellos (`compute_tweet_kpis`, barato) y análisis de texto sobre un subconjunto acotado
(`analyze_posts(posts, max_posts=TRENDS_ANALYZE_MAX_POSTS)`, costoso por spaCy), reduce
ambos resultados a sus campos agregados (`_summarize_kpis`/`_summarize_nlp` — se descartan
`top_post` y el detalle de sentimiento/VAD por post, que no aportan a una serie de tiempo y
hacen crecer cada fila) y llama a `trends_store.save_run`. Reutiliza directamente las
funciones de `app.py` (`get_client`, `_build_post_dict`, `compute_tweet_kpis`, etc.) en vez
de duplicar la lógica de búsqueda.

### `charts.py`

Construye las gráficas de línea de `/trends` como coordenadas SVG puras — sin ninguna
librería de gráficos externa ni JavaScript. `build_sentiment_chart(runs)` y
`build_emotion_chart(runs)` reciben las corridas de `trends_store.get_recent_runs` y
devuelven, para cada corrida, el % de posts en cada categoría (normalizando por el total de
esa corrida, así corridas con distinto `analyzed_count` son comparables). Los 8 colores de
emoción son la paleta categórica de referencia del skill de dataviz de Claude — un orden fijo
de 8 tonos validado contra ceguera al color y contraste en modo claro/oscuro (ver
`static/style.css`, variables `--emo-1`..`--emo-8`, con su variante de modo oscuro); nunca se
ciclan ni se reasignan por rango.

## Notas

- Las credenciales se leen de `.env` (local) o de las variables de entorno del hosting
  (producción). `.env` está en `.gitignore` — nunca lo subas a un repositorio.
- Exportar JSON/NDJSON vuelve a ejecutar la búsqueda en el momento de la descarga (no hay
  caché de resultados), para que funcione igual en local y en despliegues serverless.
- El login OAuth guarda el access/refresh token en la cookie de sesión de Flask (firmada,
  no cifrada). Es apropiado para uso personal/single-user como este; no lo uses tal cual
  para una app multiusuario sin cifrar el contenido de la sesión.

## Desplegar en Vercel

El repo ya incluye `vercel.json` (usa el runtime `@vercel/python`, que ejecuta `app.py`
como función serverless e incluye `templates/` y `static/`).

1. Sube el proyecto a un repo de GitHub (o usa `vercel` desde la CLI directamente).
2. En Vercel: **Add New Project** → importa el repo (o corre `vercel` en esta carpeta con
   la [Vercel CLI](https://vercel.com/docs/cli) ya instalada y con `vercel login` hecho).
3. En **Settings → Environments → Production** agrega estas variables de entorno:
   - `X_BEARER_TOKEN`
   - `X_CLIENT_ID`
   - `X_CLIENT_SECRET`
   - `X_REDIRECT_URI` = `https://tu-dominio.vercel.app/callback` (¡distinto al de local!)
   - `FLASK_SECRET_KEY` (genera una nueva, no reuses la de local)
   - `DATABASE_URL`, y opcionalmente `TRENDS_QUERY`, `TRENDS_TARGET_POSTS`,
     `TRENDS_ANALYZE_MAX_POSTS`, `CRON_SECRET` — para la vista `/trends` (ver esa sección).
4. En el X Developer Portal, agrega ese mismo `https://tu-dominio.vercel.app/callback`
   como Callback URI adicional en **User authentication settings**.
5. Deploy (o Redeploy si ya existía el proyecto — las variables de entorno no aplican
   solas, hay que redesplegar). Vercel detecta `vercel.json` y despliega `app.py` como
   función Python, y registra automáticamente el Cron Job de `/api/cron/trends` (definido en
   `vercel.json`) — no hace falta configurarlo aparte en el dashboard.

Importante: cada invocación es una función serverless independiente y sin estado —
por eso las exportaciones re-consultan la API de X en vez de usar un caché en memoria del
servidor. Ten en cuenta tu cuota mensual de la API si exportas seguido, y el costo/tiempo de
la corrida diaria de 1000 posts de `/api/cron/trends`.

**Plan Hobby (gratuito) vs Pro**: el cron de `/trends` está configurado para correr una vez
al día (17:00 UTC), el límite del plan Hobby. Con plan Pro puedes agregar una segunda entrada
en el arreglo `crons` de `vercel.json` para correrlo cada 12 horas. El plan Hobby también
limita la duración máxima de una función serverless; si `/api/cron/trends` empieza a fallar
por timeout, baja `TRENDS_TARGET_POSTS` y/o `TRENDS_ANALYZE_MAX_POSTS`.

## Autor

**Edwin Puertas**

- Correo: [epuerta@utb.edu.co](mailto:epuerta@utb.edu.co)
- GitHub: [github.com/EdwinPuertas](https://github.com/EdwinPuertas)
- LinkedIn: [linkedin.com/in/edwinpuertas](https://www.linkedin.com/in/edwinpuertas/)
- Sitio web: [edwinpuertas.github.io](https://edwinpuertas.github.io/)
