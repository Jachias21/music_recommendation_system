# Documentación de Frontend (Angular) y API (FastAPI)

El sistema presenta una arquitectura Web moderna de tres capas, que desacopla la lógica de interfaz de usuario, orquestación de negocio e inteligencia artificial. Está diseñado para ofrecer una experiencia fluida como Single Page Application (SPA).

## 1. Servidor de Interfaz (Frontend - Localhost:4200)

Totalmente construido con **Angular 21** con diseño *Standalone components*. La aplicación gestiona internamente la navegación (Router), estados y renderizados sin congelar al usuario mediante Observables (RxJS).

### Pantallas Principales (Features):
- **/login**: Portal de autenticación con integración Social. Incluye Flujo OAuth 2.0 Proof Key for Code Exchange (PKCE) nativo conectándose a los Accounts Web de Spotify.
- **/callback**: El componente invisible al usuario final al que Spotify redirige con un Código de Intercambio (Code Challenge). Angular recoge este *uri state*, se vuelve a comunicar con Spotify, valida el token JWT asimétrico y recupera por primera vez los metadatos del usuario final.
- **/dashboard**: El corazón de la app interactiva. Si se es usuario Spotify cargará la lógica `SpotifyService`, trayéndose canciones salvadas (`Saved Tracks`) comparándolas primero por ID en nuestro DB y luego haciendo fuzzy match por string (`match-names`). Para cuentas locales, carga el `CartService`. En ambas presenta el panel para inyectarle parámetros contextuales (Emoción Deseada).
- **/discover**: Un explorador de toda la vida. Expone un Cuadro de entrada (Search Box) mapeado a un `Subject` de base reactiva con un `debounceTime(350ms)` controlando anti-flood en el servidor. Empaqueta un JSON y llena un carrito de la compra temporal al pulsar "Añadir".
- **/playlist**: Renderiza las sugerencias calculadas ordenando los Top Rankings generados desde la matriz de similitud de Coseno.

### Servicios Base (Core Layer):
- `AuthService`: Orquesta la JWT sessionStorage, las llamadas a `auth.spotify.com`, PKCE Generation local.
- `ApiService`: Interface principal del cliente HttpClient de Angular para despachar los `HttpParams` formados por Angular a través del puerto 8000 a la de nuestra capa de servidores REST Python.

---

## 2. API Gateway (FastAPI - Localhost:8000)

Desarrollada en `api.py` y servida usando un servidor ASGI de hiperrendimiento (`Uvicorn`).

Este middleware sirve como **Traductor Universal** entre la reactividad asíncrona de JavaScript y el mundo sincrónico de Dataframes y Scikit-Learn. 

### Características de Diseño Críticas
1. **Cacheado In-Memory en Startup**: Al arrancar `uvicorn api:app`, ejecuta una rutina decorada como `@app.on_event("startup")` que invoca `get_mongodb_data()`. Descarga de MongoDB el catálogo musical y lo hospeda pre-compilado en una variable global estática en memoria RAM (`_df`).
    - *Ventaja MvP*: Cuando Angular solicita búsquedas textuales o comparadores vectoriales cruzando tablas que afectarían duramente los I/O Disk de la base de datos Mongo (y por ende lentitud y bloqueos mutacionales), ahora simplemente lee esta Dataframe en memoria, despachando consultas en muy pocos milisegundos reales.

2. **Endpoints Modulares (Pydantic Mappers)**:
   - `GET /api/songs/search`: Implementa máscaras binarias de base de textos (`str.contains`) sobre `name` y `artist` retonando los Top 20 resultados instantáneos al Angular Discover Component.
   - `POST /api/recommendations`: Receptora oficial del flujo Offline/Local (Guest). Obtiene arrays con IDs y computa perfiles basales fijos (3 Tracks de límite base).
   - `POST /api/recommendations/auto`: Receptora oficial de Spotify Session. Permite procesar N identificadores obtenidos del perfil del usuario (las Liked Tracks). Desata el módulo "Cold Start" vectorizando la "Media" centroide y devolviendo sugerencias contextuales.
   - `POST /api/songs/match-names`: End-point de recuperación. Cuando un ID de track de una Spotify Library personal no encaja explícitamente en el corpus del ID local de nuestro Dataset de 1.2M Kaggle, ejecuta un barrido string coincidente exacto (`name.lower()`) simulando un Left-Join suave para recuperar las *audio features* relativas a esa popularidad.
