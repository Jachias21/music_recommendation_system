# Documentación de `src/ingest_data.py` (Ingesta de Datos)

El archivo `ingest_data.py` es el **primer paso** del pipeline de datos de nuestro sistema de recomendación musical. Su objetivo principal es actuar como la capa de extracción (Extract) en un proceso ETL clásico, tomando los datos crudos desde una fuente externa masiva (un CSV) y transformándolos en una estructura curada inicial ("Bronze Data").

## Propósito y Funcionalidad

El catálogo original (como el de Kaggle) suele tener cientos de miles de registros y múltiples géneros que no nos interesan para nuestra prueba de concepto de emociones básicas.

La función principal `ingest_from_csv()` realiza estrictamente los siguientes pasos:
1. **Lectura Base**: Carga el dataset original masivo ubicado en `data/source/dataset_spotify.csv` en un DataFrame de Pandas.
2. **Filtrado y Mapeo Emocional Automático**:
   - Utiliza un diccionario de mapeo interno (`GENRE_MAP`) que relaciona una *emoción humana* ("Alegre", "Triste", "Energico") con *géneros musicales etiquetados* (ej: "Alegre" -> "party", "pop").
   - Cruza el DataFrame con estos géneros y filtra sólo las canciones que sirven a nuestro propósito, descartando el ruido del dataset.
3. **Limpieza y Estructuración (Deduplicación)**:
   - Extrae solo las características (features) útiles para nuestro motor de Machine Learning: metadatos básicos (`track_id`, `name`, `artist`) y métricas de audio (`danceability`, `energy`, `valence`, `tempo`, `acousticness`).
   - Evita duplicados manejando un conjunto (`ids_procesados`), ya que una misma canción en Spotify puede pertenecer a varios géneros simultáneos en el dataset fuente.
4. **Almacenamiento Local (Capa Raw / Bronze)**:
   - Exporta el listado final de diccionarios en formato JSON y lo guarda mecánicamente en `data/raw/spotify_raw_data.json`.
   - Este JSON es agnóstico a la tecnología de destino y sirve como estado intermedio seguro.

---

## Interacción con el Sistema

Este script no es importado habitualmente por los demás módulos en tiempo de ejecución de la interfaz. Su naturaleza es ser **ejecutado por lotes (Batch)**.

- **Pre-requisito**: Requiere que se haya descargado un CSV fuente y colocado en `data/source/`.
- **Salida / Output**: Crea un archivo estático `data/raw/spotify_raw_data.json` que será el input exacto que demandará el siguiente archivo lógico (`process_data.py`) para poder subir los datos a MongoDB.
