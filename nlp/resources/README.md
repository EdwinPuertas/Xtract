# NRC VAD Lexicon

`nlp/vad_emotion.py` calcula las emociones de cada post a partir del **NRC
Valence-Arousal-Dominance (VAD) Lexicon**. El léxico real ya está incluido en
este proyecto en `nlp/NRC-VAD-Lexicon-v2.1.txt` (la versión 2.1, en inglés,
54 801 términos) — no hace falta descargar nada para que funcione.

## Formato y escala

Texto separado por tabulador: `término<TAB>valence<TAB>arousal<TAB>dominance`.
El archivo oficial de NRC (incluida esta v2.1) usa escala **-1..1** con 0 como
punto neutro; `nlp/vad_lexicon.py` lo detecta automáticamente (si ve algún
valor negativo) y lo remapea a **0..1** con 0.5 como neutro, que es la escala
que usa el resto de Xtract (heurística de octantes, léxico de respaldo). No
hay que convertir nada a mano.

## Limitación importante: solo inglés

Este archivo cubre **vocabulario en inglés**. Para posts en español (el
idioma por defecto de Xtract), `compute_vad` no encontrará casi ninguna
palabra en este léxico y usará el léxico de respaldo (`_fallback_lexicon` en
`nlp/vad_emotion.py`, derivado de `lexical_features.py` — menos preciso, solo
aproxima la valencia). Si quieres emociones basadas en el léxico real también
para español, necesitas una versión en español del NRC VAD Lexicon (NRC
publica traducciones automáticas a más de 100 idiomas por separado del
archivo en inglés) y colocarla en su propio archivo — el loader actual solo
soporta un idioma a la vez.

## Usar otro archivo / otra ruta

`nlp/vad_lexicon.py` busca, en este orden, hasta encontrar el primero que
exista:

1. La ruta en la variable de entorno `NRC_VAD_LEXICON_PATH`, si está definida.
2. `nlp/NRC-VAD-Lexicon-v2.1.txt` (donde ya está el archivo de este proyecto).
3. `nlp/resources/NRC-VAD-Lexicon-v2.1.txt`
4. `nlp/resources/NRC-VAD-Lexicon-v2.txt`

Para reemplazar el léxico (otra versión, otro idioma), sobrescribe ese
archivo o define `NRC_VAD_LEXICON_PATH` apuntando al nuevo.

## Si no hay ningún archivo disponible

`nlp/vad_emotion.py` sigue funcionando igual: usa como respaldo un léxico
propio, mucho más pequeño, derivado de `nlp/lexical_features.py` (listas de
adjetivos positivos/negativos ya presentes en el repo). Ese respaldo solo
aproxima la valencia (activación y dominancia quedan neutras), así que las
emociones calculadas así son menos precisas. Cada resultado indica el campo
`source` (`nrc_vad_v2` o `fallback_lexico_propio`) para saber cuál se usó.

## Nota sobre licencia

El NRC VAD Lexicon es de uso libre para investigación (NRC, National
Research Council Canada), normalmente disponible previa solicitud en
https://saifmohammad.com/WebPages/nrc-vad.html — sus términos no autorizan
explícitamente la redistribución junto con otro software. Si este
repositorio es público, ten en cuenta esa condición de la licencia al decidir
si el archivo `nlp/NRC-VAD-Lexicon-v2.1.txt` debe quedar en el repo o
manejarse aparte (por ejemplo, subiéndolo directo al hosting sin commitearlo).
