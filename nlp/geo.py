"""Detección heurística del país de un post o de un perfil de usuario.

No usa geocodificación externa: combina el `place` que devuelve la API de X
(cuando el post está geoetiquetado, expansión `geo.place_id`) con un catálogo
propio de países/alias/ciudades para inferir el país a partir del texto libre
de ubicación del perfil (`location`). Es una aproximación, no un resultado
verificado.
"""

import unicodedata

# code, nombre en español, alias (nombres alternos, gentilicios, códigos de país
# alternativos) y algunas ciudades/regiones que ayudan a inferir el país a partir
# del campo de ubicación de un perfil.
COUNTRIES = [
    {"code": "CO", "name": "Colombia", "aliases": ["colombiano", "colombiana"],
     "cities": ["bogota", "medellin", "cali", "barranquilla", "cartagena", "bucaramanga"]},
    {"code": "MX", "name": "México", "aliases": ["mexico", "mexicano", "mexicana"],
     "cities": ["ciudad de mexico", "cdmx", "guadalajara", "monterrey", "puebla", "cancun"]},
    {"code": "AR", "name": "Argentina", "aliases": ["argentino", "argentina"],
     "cities": ["buenos aires", "cordoba", "rosario", "mendoza", "la plata"]},
    {"code": "CL", "name": "Chile", "aliases": ["chileno", "chilena"],
     "cities": ["santiago", "valparaiso", "concepcion", "antofagasta"]},
    {"code": "PE", "name": "Perú", "aliases": ["peru", "peruano", "peruana"],
     "cities": ["lima", "arequipa", "trujillo", "cusco"]},
    {"code": "EC", "name": "Ecuador", "aliases": ["ecuatoriano", "ecuatoriana"],
     "cities": ["quito", "guayaquil", "cuenca"]},
    {"code": "VE", "name": "Venezuela", "aliases": ["venezolano", "venezolana"],
     "cities": ["caracas", "maracaibo", "valencia"]},
    {"code": "BO", "name": "Bolivia", "aliases": ["boliviano", "boliviana"],
     "cities": ["la paz", "santa cruz de la sierra", "cochabamba"]},
    {"code": "PY", "name": "Paraguay", "aliases": ["paraguayo", "paraguaya"],
     "cities": ["asuncion"]},
    {"code": "UY", "name": "Uruguay", "aliases": ["uruguayo", "uruguaya"],
     "cities": ["montevideo"]},
    {"code": "CR", "name": "Costa Rica", "aliases": ["costarricense", "tico", "tica"],
     "cities": ["san jose"]},
    {"code": "PA", "name": "Panamá", "aliases": ["panama", "panameno", "panamena"],
     "cities": ["ciudad de panama"]},
    {"code": "GT", "name": "Guatemala", "aliases": ["guatemalteco", "guatemalteca"],
     "cities": ["ciudad de guatemala"]},
    {"code": "HN", "name": "Honduras", "aliases": ["hondureno", "hondurena"],
     "cities": ["tegucigalpa", "san pedro sula"]},
    {"code": "SV", "name": "El Salvador", "aliases": ["salvadoreno", "salvadorena"],
     "cities": ["san salvador"]},
    {"code": "NI", "name": "Nicaragua", "aliases": ["nicaraguense"],
     "cities": ["managua"]},
    {"code": "CU", "name": "Cuba", "aliases": ["cubano", "cubana"],
     "cities": ["la habana"]},
    {"code": "DO", "name": "República Dominicana", "aliases": ["republica dominicana", "dominicano", "dominicana"],
     "cities": ["santo domingo"]},
    {"code": "PR", "name": "Puerto Rico", "aliases": ["puertorriqueno", "puertorriquena", "boricua"],
     "cities": ["san juan"]},
    {"code": "ES", "name": "España", "aliases": ["espana", "espanol", "espanola"],
     "cities": ["madrid", "barcelona", "valencia", "sevilla", "bilbao"]},
    {"code": "US", "name": "Estados Unidos", "aliases": ["usa", "eeuu", "estadounidense", "united states"],
     "cities": ["new york", "los angeles", "miami", "chicago", "houston"]},
    {"code": "GB", "name": "Reino Unido", "aliases": ["uk", "united kingdom", "inglaterra", "england"],
     "cities": ["london", "londres", "manchester"]},
    {"code": "CA", "name": "Canadá", "aliases": ["canada", "canadiense"],
     "cities": ["toronto", "montreal", "vancouver"]},
    {"code": "BR", "name": "Brasil", "aliases": ["brasileno", "brasilena", "brazil"],
     "cities": ["sao paulo", "rio de janeiro", "brasilia"]},
    {"code": "PT", "name": "Portugal", "aliases": ["portugues", "portuguesa"],
     "cities": ["lisboa", "porto"]},
    {"code": "FR", "name": "Francia", "aliases": ["france", "frances", "francesa"],
     "cities": ["paris"]},
    {"code": "DE", "name": "Alemania", "aliases": ["germany", "aleman", "alemana"],
     "cities": ["berlin", "munich"]},
    {"code": "IT", "name": "Italia", "aliases": ["italy", "italiano", "italiana"],
     "cities": ["roma", "milan"]},
]

COUNTRY_BY_CODE = {c["code"]: c for c in COUNTRIES}


def _normalize(text: str) -> str:
    text = text.lower().strip()
    text = unicodedata.normalize("NFD", text)
    return "".join(ch for ch in text if unicodedata.category(ch) != "Mn")


def _match_location_text(location: str):
    normalized = _normalize(location)
    if not normalized:
        return None
    for country in COUNTRIES:
        candidates = [country["name"], *country["aliases"], *country["cities"]]
        for candidate in candidates:
            if _normalize(candidate) in normalized:
                return country
    return None


def detect_country(place: dict | None, author_location: str | None) -> dict | None:
    """Determina el país de un post.

    Prioriza el `place` geoetiquetado del post (dato verificado por X); si no
    existe, intenta inferirlo del texto libre de ubicación del perfil del autor
    contra el catálogo `COUNTRIES` (aproximado, el usuario lo escribe a mano).
    """
    if place:
        code = (place.get("country_code") or "").upper()
        name = place.get("country")
        if code or name:
            info = COUNTRY_BY_CODE.get(code)
            return {
                "code": code or (info["code"] if info else None),
                "name": name or (info["name"] if info else code),
                "source": "geolocalización del post",
            }

    if author_location:
        match = _match_location_text(author_location)
        if match:
            return {
                "code": match["code"],
                "name": match["name"],
                "source": "ubicación del perfil (aproximado)",
            }

    return None
