# Motor de Recomendación (Filtrado Contextual)

El motor de recomendación matemático está codificado íntegramente en `src/modeling/recommendation_engine.py` actuando como núcleo duro de procesamiento bajo demanda servido mediante API.

## Funciones Core

- **Módulo 1: Extracción de datos en caché**: Implementada la función `get_mongodb_data()`. Invoca Pymongo, retorna un DataFrame nativo Pandas para los cálculos algebraicos y escala en el momento la columna `tempo` usando el `MinMaxScaler` estandarizándolo (`0` a `1`) con las otras features para evitar sesgos por amplitudes asimétricas en la métrica (BPM).
  
- **Módulo 2: Perfilado (ADN) y "Cold Start"**: Implementada la función `create_user_profile(user_favorite_song_ids, df)`. Recibe N IDs de canciones base y agrupa mediante medias (`.mean()`) un vector matemático centroide de **8 dimensiones** (`danceability`, `energy`, `valence`, `tempo`, `acousticness`, `instrumentalness`, `liveness`, `speechiness`). Este es el perfil digital instantáneo de las preferencias acústicas del usuario.

- **Módulo 3: Motor de Recomendación Contextual**: Desarrollada la función `get_contextual_recommendations(...)`:
  1. Filtra primero en MongoDB exigiendo coincidir estrictamente con la `emocion` elegida (Alegre, Triste, Energico, etc) con un límite topado a los **25.000 registros**. Esto previene colapsos de memoria generados por la base de datos completa de 1.2M iterando de forma nativa.
  2. Emplea la técnica `cosine_similarity` extrayendo ángulos de similitud estricta entre el Perfil de Usuario de 8D con cada registro disponible habilitado.
  3. Ordena los clústeres descendientemente, filtrando temporalmente aquellos IDs originales a través de *Blacklisting* controlado (usando `id` o `track_id` limpiamente procesado) para no recomendar canciones base. Devuelve un formato serializado JSON List.

## Interfaz de Exposición

Dado el diseño full-stack propuesto, el framework general (Angular) no llama directamante a este Python. Por el medio figura un orquestador (API Gateway desarrollado en FastAPI) que importa estas bases, maneja el cache global del Dataframe `_df` (para no re-golpear a Mongo repetidamente) y expone Web Endpoints asíncronos en el puerto `8000` devolviéndoselos al SPA Client.