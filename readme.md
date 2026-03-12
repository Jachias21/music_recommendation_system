# 🚀 Guía de Configuración para Desarrolladores

Bienvenido al repositorio del Sistema de Recomendación de Música. Este es un manual rápido para que los desarrolladores del equipo puedan configurar el entorno local, levantar los servicios necesarios y empezar a programar sin fricciones.

## 📋 1. Requisitos Previos

Asegúrate de tener instalado en tu sistema de desarrollo:
- **Python 3.10+** (o versiones compatibles)
- **Docker** y **Docker Compose**
- **uv** (Opcional pero altamente recomendado por su extrema velocidad en la gestión de paquetes en Python).

## 🛠️ 2. Entorno Virtual y Dependencias

Abre tu terminal y ubícate en la raíz del proyecto.

### Si utilizas `uv` (Recomendado)
Puedes crear el entorno o correr cosas al vuelo, pero para tener todo instalado:
```bash
# Sincroniza o instala todo el árbol de dependencias
uv sync

# (Opcional) Activar el entorno de manera clásica:
source .venv/bin/activate
```

### Si utilizas `pip` tradicional
```bash
python -m venv venv
source venv/bin/activate  # (En Windows: venv\Scripts\activate)
pip install -r requirements.txt
```

### Variables de Entorno (`.env`)
En la raíz del proyecto, debes crear un archivo llamado `.env` e introducir las credenciales de desarrollo. Puedes solicitar las claves exactas al propietario del proyecto:

```env
SPOTIPY_CLIENT_ID=solicitar_acceso (no necesario actualmente)
SPOTIPY_CLIENT_SECRET=solicitar_acceso (no necesario actualmente)
```

## 🗄️ 3. Base de Datos en Local (MongoDB)

Para no emsuciar tu máquina local, la base de datos corre dockerizada. Asegúrate de tener Docker abierto y ejecuta:

```bash
docker-compose up -d
```
*Tip: Para destruirla al terminar el día y liberar puertos usa `docker-compose down`.*

## 📖 4. Consultar y Editar la Documentación

La documentación técnica, de arquitectura y módulos vive separada en la ruta `/docs` usando **MkDocs**. Es la fuente de la verdad para consultar las dependencias de los módulos (como el Motor de Recomendación).

Para levantar el servidor web local con "hot-reload" (refresque en vivo), abre una pestaña de terminal y corre:

```bash
cd docs
uv run mkdocs serve
```

## 💻 5. Flujo Operativo y Testing Local

Cuando vayas a probar el código o hacer QA de todo el *pipeline* del proyecto, los scripts deben ejecutarse en este orden extricto:

1. **Ingesta:** Extrae la música usando la API de Spotify.
   ```bash
   uv run python ingest_data.py
   ```
2. **Transformación & Carga:** Limpia e inserta masivamente los diccionarios a tu Mongo local.
   ```bash
   uv run python process_data.py
   ```
3. **Motor ML (Recomendador):** Ejecuta la simulación de prueba del "Cold Start" y la predicción del coseno de Scikit-Learn.
   ```bash
   uv run python src/modeling/recommendation_engine.py
   ```

