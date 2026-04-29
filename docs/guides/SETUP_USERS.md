# Sistema de usuarios — Pasos de configuración

## 1. Instalar dependencia nueva

```bash
pip install passlib[bcrypt]
```

O con el archivo de requisitos completo:

```bash
pip install -r requirements.txt
```

---

## 2. Verificar que MongoDB está corriendo

El sistema guarda los usuarios en MongoDB. Asegúrate de que el contenedor está activo:

```bash
docker ps | grep mongo
```

Si no aparece, iniciarlo (ajusta el comando a cómo lo tienes configurado):

```bash
docker start <nombre-del-contenedor-mongo>
```

La URL esperada es:
```
mongodb://admin:admin123@127.0.0.1:27018/music_recommendation_db?authSource=admin
```

---

## 3. Iniciar el backend

```bash
cd proyecto4v2/music_recommendation_system
uvicorn api:app --reload --port 8002
```

El backend creará automáticamente la colección `users` con un índice único en `email` al arrancar.

---

## 4. Iniciar el frontend

```bash
cd proyecto4v2/music_recommendation_system/frontend
ng serve --host 0.0.0.0
```

Accede en: http://127.0.0.1:4200

---

## Flujo de usuario nuevo

1. El usuario va a `/register` y crea una cuenta.
2. Tras registrarse, es redirigido automáticamente a `/onboarding`.
3. En onboarding busca y selecciona **hasta 3 canciones** favoritas.
4. Al pulsar "Continuar", las canciones se guardan en MongoDB y el flag `onboarding_complete` se pone a `true`.
5. En inicios de sesión posteriores, el onboarding se omite y va directo a `/dashboard`.

## Flujo de usuario existente (segunda vez que inicia sesión)

1. Va a `/login`, introduce email y contraseña.
2. El backend valida contra MongoDB.
3. Como `onboarding_complete === true`, va directo a `/dashboard`.

---

## Notas técnicas

- Las contraseñas se almacenan hasheadas con **bcrypt** (passlib).
- No hay JWT; la sesión se mantiene en `localStorage` del navegador (igual que antes para Spotify).
- Los usuarios de Spotify no pasan por onboarding (ya tienen perfil).
- La colección `users` queda en la misma base de datos `music_recommendation_db`, separada de la colección `songs`.
