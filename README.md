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
- **Agrupar por** (solo búsqueda de posts): agrupa los resultados en pantalla por hashtag o
  por categoría (usa `context_annotations` de la API de X, clasificación temática nativa de
  cada post — Tecnología, Deportes, etc.). Un post con varios hashtags/categorías aparece en
  cada grupo correspondiente.
- El resumen de KPIs también incluye los hashtags y categorías más frecuentes de la búsqueda.
- Cada búsqueda se puede exportar como **JSON**, **NDJSON** (un objeto por línea) o **CSV**
  (con columnas planas, incluyendo hashtags/categorías) desde los enlaces sobre los resultados.
- **Conectar cuenta de X**: botón en la parte superior → autoriza en X → vuelves a Xtract
  con tu perfil y un cuadro para publicar tweets.
- **Timeline de usuario**: haz clic en cualquier autor (en resultados de posts o de usuarios)
  para ver sus últimos posts, KPIs y exportar esa vista.
- **Analizar texto** (checkbox en el formulario, solo búsqueda de posts): activa un análisis
  lingüístico de los resultados con spaCy/nltk — sintagmas nominales (tópicos frecuentes),
  bigramas/trigramas, sentimiento por post (positivo/neutral/negativo, basado en un léxico
  de adjetivos en español/inglés) y **emociones por post según el modelo VAD** (valencia,
  activación, dominancia) usando el NRC VAD Lexicon v2. Aumenta el tiempo de respuesta de
  la búsqueda.
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

## Módulo `nlp/` (código propietario de análisis lingüístico y detección de país)

El paquete `nlp/` contiene el motor propio de procesamiento de lenguaje natural que
alimenta la opción **Analizar texto** del formulario de búsqueda de posts. No es una
dependencia externa: es lógica propietaria de Xtract, construida sobre spaCy y NLTK como
librerías base. Se activa desde `app.py` (`from nlp.analysis import analyze_posts`, línea
~18) únicamente cuando el usuario marca el checkbox correspondiente, ya que añade latencia
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

### `nlp/vad_lexicon.py` — carga del NRC VAD Lexicon v2

Loader del **NRC Valence-Arousal-Dominance (VAD) Lexicon v2**. El archivo del léxico no se
distribuye con el repo (licencia de NRC, uso libre para investigación previa solicitud); ver
`nlp/resources/README.md` para instrucciones de instalación. `load_lexicon` busca el archivo
en `nlp/resources/NRC-VAD-Lexicon-v2.txt` (o en la ruta de la variable de entorno
`NRC_VAD_LEXICON_PATH`), parsea líneas `palabra<TAB>valence<TAB>arousal<TAB>dominance` y
cachea el resultado en memoria. Si el archivo no existe, devuelve un diccionario vacío en
vez de fallar. `is_lexicon_available()` indica si hay datos reales cargados.

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
4. En el X Developer Portal, agrega ese mismo `https://tu-dominio.vercel.app/callback`
   como Callback URI adicional en **User authentication settings**.
5. Deploy (o Redeploy si ya existía el proyecto — las variables de entorno no aplican
   solas, hay que redesplegar). Vercel detecta `vercel.json` y despliega `app.py` como
   función Python.

Importante: cada invocación es una función serverless independiente y sin estado —
por eso las exportaciones re-consultan la API de X en vez de usar un caché en memoria del
servidor. Ten en cuenta tu cuota mensual de la API si exportas seguido.

## Autor

**Edwin Puertas**

- Correo: [epuerta@utb.edu.co](mailto:epuerta@utb.edu.co)
- GitHub: [github.com/EdwinPuertas](https://github.com/EdwinPuertas)
- LinkedIn: [linkedin.com/in/edwinpuertas](https://www.linkedin.com/in/edwinpuertas/)
- Sitio web: [edwinpuertas.github.io](https://edwinpuertas.github.io/)
