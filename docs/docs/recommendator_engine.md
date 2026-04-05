# Motor de Recomendación (Filtrado Contextual)

El motor de recomendación matemático está codificado íntegramente en `src/modeling/recommendation_engine.py` actuando como núcleo duro de procesamiento bajo demanda servido mediante API.

## Funciones Core

- **Módulo 1: Extracción de datos en caché**: Implementada la función `get_mongodb_data()`. Invoca Pymongo, retorna un DataFrame nativo Pandas para los cálculos algebraicos y escala en el momento la columna `tempo` usando el `MinMaxScaler` estandarizándolo (`0` a `1`) con las otras features para evitar sesgos por amplitudes asimétricas en la métrica (BPM).
  
- **Módulo 2: Perfilado (ADN) y "Cold Start"**: Implementada la función `create_user_profile(user_favorite_song_ids, df)`. Recibe N IDs de canciones base (como las seleccionadas a mano, o las "Liked Songs" pasadas por Spotify) y agrupa mediante medias (.mean()) un vector matemático centroide de 5 dimensiones. Este es el perfil digital instantáneo de las preferencias acústicas y energéticas del usuario.

- **Módulo 3: Motor de Recomendación Contextual**: Desarrollada la función `get_contextual_recommendations(user_vector, target_emotion, dataframe_base, top_n)`.
  1. Filtra primero todo el dataset MongoDB (usualmente 1.2M) exigiendo coincidir con la `emocion` elegida (Alegre, Triste, Energico, etc). Reduce considerablemente costes de búsqueda matricial de fuerza bruta T(N^2).
  2. Emplea la técnica `cosine_similarity` extrayendo ángulos de similitud estricta entre el Perfil de Usuario con cada registro disponible habilitado.
  3. Ordena los clústeres descendientemente, filtrando aquellos que ya incluyó el usuario (no recomendamos lo mismo de lo que ya somos fan o hemos pre-seleccionado) y devuelve un formato serializado JSON List.

## Interfaz de Exposición

Dado el diseño full-stack propuesto, el framework general (Angular) no llama directamante a este Python. Por el medio figura un orquestador (API Gateway desarrollado en FastAPI) que importa estas bases, maneja el cache global del Dataframe `_df` (para no re-golpear a Mongo repetidamente) y expone Web Endpoints asíncronos en el puerto `8000` devolviéndoselos al SPA Client.