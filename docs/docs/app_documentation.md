# Documentación de Frontend (Angular) y API (FastAPI)

El sistema presenta una arquitectura Web moderna de tres capas, que desacopla la lógica de interfaz de usuario, orquestación de negocio e inteligencia artificial. Está diseñado para ofrecer una experiencia fluida como Single Page Application (SPA).

## 1. Servidor de Interfaz (Frontend - Localhost:4200)

Totalmente construido con **Angular 21** con diseño *Standalone components*. La aplicación gestiona internamente la navegación (Router), estados y renderizados sin congelar al usuario mediante Observables (RxJS).

### Pantallas Principales (Features):
- **/login**: Portal de autenticación con integración Social. Incluye Flujo OAuth 2.0 Proof Key for Code Exchange (PKCE) nativo conectándose a los Accounts Web de Spotify.
- **/callback**: El componente invisible al usuario final al que Spotify redirige con un Código de Intercambio (Code Challenge). Angular recoge este *uri state*, se vuelve a comunicar con Spotify, valida el token JWT asimétrico y recupera por primera vez los metadatos del usuario final.
- **/dashboard**: El corazón de la app interactiva. Si se es usuario Spotify cargará la lógica `SpotifyService`, iterando a través de paginación para descargar hasta **150 canciones guardadas**, e invalidando la caché temporal del navegador para estar siempre actualizados. Luego cruza esos datos. Para cuentas locales, se usa el `CartService`.
- **/discover**: Un explorador de toda la vida. Expone un Cuadro de entrada (Search Box) mapeado a un `Subject` de base reactiva con un `debounceTime(350ms)` controlando anti-flood en el servidor. Empaqueta un JSON y llena un carrito temporal al pulsar "Añadir".
- **/playlist**: Renderiza las sugerencias calculadas ordenando los Top Rankings generados desde la matriz de similitud de Coseno.

### Servicios Base (Core Layer):
- `AuthService`: Orquesta la JWT sessionStorage, las llamadas a `auth.spotify.com`, PKCE Generation local.
- `ApiService`: Interface principal del cliente HttpClient de Angular para despachar los `HttpParams` formados por Angular a través del puerto 8000 a la de nuestra capa de servidores REST Python.

---

## 2. API Gateway (FastAPI - Localhost:8000)

Desarrollada en `api.py` y servida usando un servidor ASGI de hiperrendimiento (`Uvicorn`).

Este middleware sirve como **Traductor Universal** entre la reactividad asíncrona de JavaScript y el mundo sincrónico de Dataframes y Scikit-Learn. 

### Características de Diseño Críticas
1. **Cacheado y Limpieza de Texto In-Memory en Startup**: Al arrancar `uvicorn api:app`, ejecuta una rutina (`_load_data()`) que descarga de MongoDB el catálogo musical. A la vez, invoca la función `clean_text()` basada en Regex (Módulo `re`) para generar las columnas pre-computadas `clean_name` y `clean_artist`.
    - *Ventaja MvP*: Cuando Angular solicita búsquedas, en vez de aplicar limpieza de strings en caliente a 1.2 millones de filas (bloqueando el hilo), el cruce de datos ocurre en memoria a latencias casi de tiempo constante (O(1)), eludiendo los ruidos de formato como "(feat. XYZ)" procedentes de los metadatos de Spotify.

2. **Endpoints Modulares (Pydantic Mappers)**:
   - `GET /api/songs/search`: Implementa iteradores básicos de búsqueda local retornando sugerencias instantáneas.
   - `POST /api/recommendations/auto`: Receptora oficial de Spotify Session. Pasa los hashes encontrados directamente al motor matemático para desencadenar el Cold Start.
   - `POST /api/songs/match-names`: End-point de recuperación masiva. Busca emparejar la biblioteca del usuario haciendo correspondencias **exactas** sobre el texto ya pre-limpiado en las cachés de regex `clean_name` & `clean_artist`, erradicando falsos positivos.
   - `POST /api/recommendations/by-names`: Soluciona el problema de carencia de IDs delegando en FastApi la resolución nativa de nombres/artistas introducidos sueltos y calculando automáticamente la similitud recomendando tracks nuevos.
