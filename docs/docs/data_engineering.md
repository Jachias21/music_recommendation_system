# Pipeline de Ingeniería de Datos

El sistema procesa un catálogo de **1.2 millones de canciones** mediante un pipeline estructurado en tres fases: Ingesta (Bronze), Procesamiento (Silver) y Carga en Base de Datos (Gold).

---

## Flujo de Trabajo

### 1. Ingesta y Limpieza (`ingest_data.py`)
El proceso comienza con la lectura del archivo fuente `tracks_features.csv` (Kaggle). Las operaciones clave incluyen:
- **Deduplicación:** Se eliminan duplicados basados en el `id` de Spotify.
- **Limpieza de Nulos:** Se descartan registros sin metadatos críticos (`name`, `artist`, `id`).
- **Parsing de Artistas:** Conversión de representaciones de listas en strings limpias.
- **Persistencia Bronze:** Exportación a un archivo JSON intermedio en `data/raw/`.

### 2. Clasificación Matemática de Emociones
Dado que el dataset original no incluye etiquetas emocionales, SoundWave implementa una lógica de clasificación heurística basada en **Audio Features** de Spotify. Los umbrales se han definido bajo criterios psicomusicales:

| Emoción | Regla Matemática (Orden de prioridad) |
| :--- | :--- |
| **Enérgico** | $energy \ge 0.75 \land tempo \ge 130$ BPM |
| **Alegre** | $valence \ge 0.60 \land danceability \ge 0.55$ |
| **Triste** | $valence \le 0.35 \land acousticness \ge 0.30 \land energy \le 0.55$ |
| **Neutro** | *Fallback (Resto de casos)* |

### 3. Normalización y Carga (`process_data.py`)
Antes de la inserción en MongoDB, los datos se someten a un refinamiento adicional:
- **Escalado:** Uso de `MinMaxScaler` para normalizar `tempo` y `loudness` al rango $[0, 1]$.
- **Limpieza de Texto:** Eliminación de sufijos como "(Remastered)" o "- Live" para optimizar la búsqueda semántica.
- **Indexación:** Creación de índices en MongoDB para `emocion`, `clean_name`, `clean_artist` y `track_id`.

---

## Esquema de Datos (MongoDB)

Cada documento en la colección `songs` sigue la siguiente estructura técnica:

```json
{
  "track_id": "string (Spotify ID)",
  "name": "string (Original Name)",
  "clean_name": "string (Lowercase, normalized)",
  "artist": "string (Artist list)",
  "clean_artist": "string (First artist, normalized)",
  "emocion": "string (Alegre | Triste | Energico | Neutro)",
  "danceability": "float [0-1]",
  "energy": "float [0-1]",
  "valence": "float [0-1]",
  "tempo": "float [0-1] (Scaled)",
  "acousticness": "float [0-1]",
  "instrumentalness": "float [0-1]",
  "liveness": "float [0-1]",
  "speechiness": "float [0-1]",
  "loudness": "float [0-1] (Scaled)",
  "year": "int | null"
}
```

Este esquema permite tanto la **búsqueda por texto** como la **búsqueda por vecindad** en el espacio vectorial de 8 dimensiones definido por las audio features.
