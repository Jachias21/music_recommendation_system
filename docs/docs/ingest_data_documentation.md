# Documentación de `src/ingest_data.py` (Ingesta de Datos)

El archivo `ingest_data.py` es el **primer paso** del pipeline de datos de nuestro sistema de recomendación musical. Su objetivo principal es tomar los datos crudos masivos (un archivo CSV local con más de 1.2 Millones de registros extraído de Kaggle) y transformarlos en una estructura limpia y procesable ("Bronze Data").

## Propósito y Funcionalidad

El código base evolucionó para abandonar por completo el uso lento de bucles tradicionales (`iterrows()`), empleando en su lugar procesamiento vectorizado nativo de Pandas y NumPy, logrando procesar el dataset completo en apenas segundos.

La función principal `ingest_from_csv()` realiza estrictamente los siguientes pasos:

1. **Lectura Segura y Estable**:
   - Calcula rutas absolutas de forma relativa al fichero (`__file__`) evitando fallos si se ejecuta desde distintos directorios (`CWD`).
   - Carga eficientemente el `dataset_spotify.csv`.

2. **Limpieza Vectorizada de Metadatos**:
   - Detecta duplicados y nulos de manera nativa en atributos críticos (`id`, `name`, `danceability`, `energy`, etc).
   - Analiza e interpreta listas anilladas como las del string `"['Rage Against The Machine']"`, aplicando transformaciones para extraer el texto limpio.

3. **Inferencia y Clasificación Emocional (MER)**:
   Debido a que el dataset no posee géneros (o son irrelevantes en clasificaciones granulares), empleamos directrices basadas en la literatura de **Music Emotion Recognition**:
   - **Energico**: `energy >= 0.75` AND `tempo >= 130 BPM`.
   - **Alegre**: `valence >= 0.60` AND `danceability >= 0.55`.
   - **Triste**: `valence <= 0.35` AND `acousticness >= 0.30` AND `energy <= 0.55`.
   - **Neutro**: Fallback cuando no se cumplen picos extremos.
   - Todo esto se evalúa de golpe en memoria usando `np.select`.

4. **Conversión y Exportación Final**:
   - Procesa y formatea el Output (limita precisión de flotantes).
   - Usa `to_dict` volcando un listado final que se almacena en disco `data/raw/spotify_raw_data.json`.

---

## Interacción con el Sistema

Este script actúa como Batch Job (Ejecución por Lotes) y se dispara una única vez al montar por primera vez el entorno.
- **Input esperado**: Un CSV ubicado en `data/source/dataset_spotify.csv`.
- **Output entregado**: El JSON `data/raw/spotify_raw_data.json` listo para ser ingerido por MongoDB en la fase de carga.
