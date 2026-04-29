# Capa de Servicio (Backend API)

La API de SoundWave actúa como el puente entre la interfaz de usuario y los motores de recomendación, gestionando la orquestación de modelos, la autenticación y la persistencia.

---

## Endpoints Principales

### Recomendaciones
- `POST /api/recommendations`: Endpoint principal. Recibe 1-5 canciones semilla, una emoción y el tipo de modelo deseado. Orquesta la llamada entre NCF, Node2Vec o Base.
- `POST /api/recommendations/auto`: Diseñado para la integración con Spotify. Utiliza los IDs de Spotify para mapear contra el catálogo local y generar recomendaciones.
- `POST /api/recommendations/by-names`: Permite generar recomendaciones buscando canciones por nombre y artista sin necesidad de IDs internos.

### Búsqueda y Metadatos
- `GET /api/songs/search`: Búsqueda de texto completo (FTS) sobre el catálogo de 1.2M. Implementa una búsqueda insensible a mayúsculas y optimizada por índices de MongoDB.
- `GET /api/emotions`: Devuelve las etiquetas emocionales válidas del sistema.

---

## Autenticación y Usuarios

SoundWave implementa un sistema de gestión de usuarios robusto para el almacenamiento de preferencias de "onboarding".

### 1. Registro y Login (`bcrypt`)
- El sistema utiliza `passlib[bcrypt]` para el hashing de contraseñas, asegurando que nunca se almacenen contraseñas en texto plano.
- **Registro (`POST /api/auth/register`):** Valida la unicidad del email mediante un índice único en la colección `users` de MongoDB.
- **Login (`POST /api/auth/login`):** Verifica el hash de la contraseña y devuelve el perfil del usuario.

### 2. Ciclo de Onboarding
Cuando un usuario se registra, el sistema marca `onboarding_complete: false`. 
- El endpoint `PUT /api/users/{user_id}/onboarding` permite guardar las primeras 5 canciones favoritas del usuario.
- Estos IDs se utilizan como el perfil base para todas las recomendaciones automáticas futuras.

---

## Seguridad y CORS
La API incluye middleware de CORS configurado para permitir únicamente el acceso desde el dominio del frontend (`http://localhost:4200`), previniendo ataques de origen cruzado. 

La serialización de datos utiliza **Pydantic V2** para garantizar que todas las respuestas de la API cumplan con el contrato de datos (schemas) definido, evitando errores de tipo en el cliente Angular.
