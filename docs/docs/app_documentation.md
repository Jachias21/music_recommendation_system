# Documentación de `app.py` (Interfaz de Usuario Principal)

El archivo `app.py` es el punto de entrada principal para la interfaz de usuario de nuestro **Sistema de Recomendación Musical**. Está construido utilizando el framework **Streamlit** y se encarga de gestionar toda la interacción inicial con el usuario, su perfil de preferencias musicales (Onboarding) y la presentación final de las recomendaciones contextuales.

## Arquitectura y Conexiones del Archivo

Para funcionar correctamente, `app.py` no existe de forma aislada, sino que actúa como el "orquestador visual" de los procesos y modelos construidos en el sistema.

### Dependencias y Archivos que Invoca:
`app.py` realiza llamadas a toda la raíz del backend (directorio `src/`) para delegar el procesamiento de datos y la inteligencia de recomendación:

1. **`src/process_data.py`**
   - **Variables importadas**: `MONGO_URI`, `DB_NAME`, `COLLECTION_NAME`.
   - **Por qué lo llama**: `app.py` necesita saber dónde y cómo conectarse a la base de datos de MongoDB. En lugar de codificar ("hardcodear") estas credenciales en el archivo de interfaz, las importa de las variables de entorno centrales definidas en el archivo de procesamiento.

2. **`src/modeling/recommendation_engine.py`**
   - **Funciones importadas**: `get_mongodb_data`, `create_user_profile`, `get_contextual_recommendations`.
   - **Por qué lo llama**: Constituye el núcleo o "cerebro" matemático importado en la vista.
     - Utiliza `get_mongodb_data` para extraer el catálogo completo de canciones al inicializar la app y guardarlo en memoria caché (`@st.cache_data`) optimizando los tiempos de carga.
     - Utiliza `create_user_profile` enviando las 3 canciones favoritas seleccionadas en la interfaz para que este módulo devuelva el "ADN Musical" (vector de 5 dimensiones).
     - Utiliza `get_contextual_recommendations` enviando ese vector y la emoción elegida, devolviendo un Top 10 formateado para que `app.py` lo pinte en pantalla.

---

## Dinámica Funcional y Diseño de la App

La aplicación está dividida en tres lógicas principales de interacción (Fases):

### 1. Gestión de Estado y Memoria (Session State)
Streamlit, por defecto, se recarga por completo en cada interacción. `app.py` resuelve este problema empleando *Session State* (`st.session_state.selected_songs`).
- Se inicializa un "carrito" o lista vacía `[]` la primera vez que arranca la aplicación.
- Este estado sobrevive a los reinicios de Streamlit, permitiendo que la interfaz actúe verdaderamente como una Single Page Application (SPA).

### 2. Panel Lateral: Onboarding y Búsqueda Dinámica
Para sustituir listas estáticas inmanejables, se ha programado un **Motor de Búsqueda Dinámico**:
- **Búsqueda Avanzada**: El usuario usa un cuadro de texto (`st.sidebar.text_input`). A partir de los 2 caracteres, `app.py` lanza una consulta lógica usando Pandas (`str.contains`) sobre el catálogo musical cacheado detectando coincidencias de pista o artista, obviando mayúsculas y minúsculas.
- **Paginación Eficiente**: El panel restringe las visualizaciones visuales a un `.head(10)` para no congestionar la interfaz web (DOM).
- **Validación del Carrito**:
  - Al pulsar "Añadir" en una canción buscada, el sistema valida que no esté duplicada.
  - Verifica que no se exceda el cupo paramétrico de `len == 3`. Si es válido, lo inyecta a `st.session_state.selected_songs`.
  - Provee una visualización en tiempo real de lo seleccionado con la posibilidad de "🗑️ Quitar" elementos, lo que elimina el elemento mediante comando `.pop()` y actualiza la página (`st.rerun()`). Una barra de progreso interactiva informa visualmente de cuán cerca se está del objetivo.

### 3. Panel Central: Contexto y Generación Condicional
El bloque principal asume el control cuando el usuario completó la Fase 2:
- Expone un selector de emociones (Contexto emocional del usuario). Extrae las opciones directamente del formato dinámico de los metadatos parseados desde MongoDB.
- **Bloqueo Inteligente**: El botón principal de llamado a la acción (`Generar Playlist Contextual`) incluye lógica de interbloqueo (`disabled=True`). Si el usuario no ha completado las 3 pistas exigidas para crear un Cold Start real, la app muestra un `st.warning` inhabilitando el botón.
- **Generación Final**: Una vez completado, el clic desencadena toda la cadena del motor en el backend y formatea la respuesta mostrando listas ordenadas por el % de similitud de coseno devuelto, emparejado con nombre y artista de la recomendación.
