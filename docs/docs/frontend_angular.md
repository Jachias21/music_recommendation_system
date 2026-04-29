# Aplicación Cliente (Angular 21)

La interfaz de SoundWave es una Single Page Application (SPA) moderna diseñada para ofrecer una experiencia fluida e inmersiva.

---

## Arquitectura del Frontend

La aplicación sigue el patrón de diseño **Core/Features/Shared**:

- **Core (`/app/core/`):** Contiene servicios singleton (Auth, Spotify, API) y guards de rutas que gestionan el estado global y la comunicación.
- **Features (`/app/features/`):** Módulos independientes para cada funcionalidad clave (Home, Explorador, Onboarding, Player).
- **Shared (`/app/shared/`):** Componentes visuales reutilizables (Botones, Tarjetas de canciones, Spinners) y modelos de datos.

Utilizamos **Angular Signals** para una detección de cambios granular y eficiente, eliminando la necesidad de `Zone.js` en gran parte de la lógica reactiva.

---

## Integración con Spotify (OAuth 2.0 PKCE)

SoundWave permite la sincronización con Spotify para construir un perfil de usuario real instantáneamente. 

### Flujo PKCE (`spotify.service.ts`):
1. **Generación de Verifier/Challenge:** Se genera un código aleatorio en el cliente para evitar el uso de `client_secret` en el frontend.
2. **Autorización:** El usuario es redirigido a Spotify.
3. **Intercambio:** Al volver, el cliente intercambia el código por un `access_token` de corta duración.
4. **Mapeo del Perfil:** El servicio `SpotifyService` extrae las canciones guardadas (`/me/tracks`) y las envía al backend para buscar coincidencias exactas por ID o, en su defecto, por nombre y artista.

---

## Flujo de Onboarding

Para usuarios sin Spotify, SoundWave implementa un flujo de bienvenida obligatorio:

1. **Búsqueda Inicial:** El usuario busca y selecciona 5 canciones que definan su gusto musical actual.
2. **Selección de Semillas:** Estas canciones se envían al backend para calcular el **Centroide Neuronal** inicial.
3. **Persistencia:** Una vez completado, el estado del usuario cambia a `onboarding_complete: true`, desbloqueando el panel de recomendaciones personalizado.

---

## Diseño y UX
La aplicación utiliza **Vanilla CSS** con variables de diseño (tokens) para un tema oscuro profundo ("SoundWave Night"), con animaciones de micro-interacciones gestionadas mediante Angular Animations para transiciones suaves entre vistas.
