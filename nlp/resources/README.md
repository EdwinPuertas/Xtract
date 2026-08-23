# NRC VAD Lexicon v2

Esta carpeta es el lugar donde debe colocarse el **NRC Valence-Arousal-Dominance
(VAD) Lexicon v2** para que `nlp/vad_emotion.py` calcule las emociones de cada
post con datos reales del léxico.

El léxico no se incluye en este repositorio porque su licencia (National
Research Council Canada, uso libre para investigación) no permite
redistribuirlo junto con software de terceros.

## Cómo activarlo

1. Solicita/descarga el léxico desde la página oficial de Saif Mohammad (NRC):
   https://saifmohammad.com/WebPages/nrc-vad.html
2. Copia el archivo de palabras a `nlp/resources/NRC-VAD-Lexicon-v2.txt`.
   Formato esperado, una palabra por línea, separada por tabulador:
   ```
   palabra\tvalence\tarousal\tdominance
   ```
   con `valence`, `arousal` y `dominance` como números entre 0 y 1 (0.5 = neutro).
3. Reinicia la app. `nlp/vad_lexicon.py` lo carga automáticamente desde esta
   ruta (o desde la ruta que definas en la variable de entorno
   `NRC_VAD_LEXICON_PATH`).

## Si no lo instalas

`nlp/vad_emotion.py` sigue funcionando: usa como respaldo un léxico propio,
mucho más pequeño, derivado de `nlp/lexical_features.py` (listas de
adjetivos positivos/negativos ya presentes en el repo). Ese respaldo solo
aproxima la valencia (activación y dominancia quedan neutras), así que las
emociones calculadas así son menos precisas. Cada resultado indica el campo
`source` (`nrc_vad_v2` o `fallback_lexico_propio`) para saber cuál se usó.
