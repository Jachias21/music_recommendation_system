# 🎵 Sound Lens — Sistema de Recomendación Musical

Sistema de recomendación de música basado en audio features y similitud coseno, con frontend en Angular 21, backend FastAPI y base de datos MongoDB.

---

## 📋 Requisitos Previos

Asegúrate de tener instalado en tu máquina:

| Herramienta | Versión mínima | Notas |
|---|---|---|
| **Python** | 3.13+ | Requerido por `pyproject.toml` |
| **Node.js / npm** | npm 11+ | Para el frontend Angular |
| **Docker** + **Docker Compose** | Cualquier reciente | Para levantar MongoDB |
| **uv** | Cualquier reciente | Recomendado; alternativa: `pip` |

Instalar `uv` si no lo tienes:
```bash
curl -Ls https://astral.sh/uv/install.sh | sh
```

---

## 🗄️ 1. Levantar MongoDB (Docker)

La base de datos corre en un contenedor Docker para no ensuciar tu máquina local. Arráncala antes de cualquier otro paso:

```bash
docker-compose up -d
```

Esto levanta MongoDB en el puerto `27018` con usuario `admin` / contraseña `admin123`.

> Para pararlo al terminar: `docker-compose down`

---

## 📦 2. Instalar dependencias Python

Desde la raíz del proyecto:

```bash
# Opción recomendada (uv — muy rápido)
uv sync

# Opción alternativa (pip clásico)
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

---

## 🎵 3. Descargar el Dataset

> ⚠️ **El dataset NO está incluido en el repositorio** (>300 MB). Debes descargarlo manualmente.

### Fuente
**Kaggle — Spotify 1.2M+ Songs**
🔗 [https://www.kaggle.com/datasets/rodolfofigueroa/spotify-12m-songs](https://www.kaggle.com/datasets/rodolfofigueroa/spotify-12m-songs)

### Pasos
1. Inicia sesión en Kaggle (o regístrate, es gratis)
2. Descarga el archivo `tracks_features.csv`
3. Renómbralo a `dataset_spotify.csv`
4. Colócalo en la ruta exacta:

```
music_recommendation_system/
└── data/
    └── source/
        └── dataset_spotify.csv   ← aquí
```

Crea la carpeta si no existe:
```bash
mkdir -p data/source
```

---

## 🔄 4. Pipeline de Datos (ejecutar en orden)

Una vez descargado el CSV, ejecuta los scripts en este orden para poblar la base de datos:

### Paso 1 — Ingesta y clasificación
Lee el CSV, clasifica cada canción por emoción usando sus audio features y genera un JSON intermedio en `data/raw/`.

```bash
source .venv/bin/activate
python3 src/ingest_data.py
```

**Output esperado:**
```
Dataset cargado:   1,204,022 filas
Tras limpiar nulos y duplicados:  1,204,022 filas

Clasificación completada. Distribución por emoción:
  Neutro    :  532,439  (44.2%)
  Triste    :  320,909  (26.7%)
  Alegre    :  212,351  (17.6%)
  Energico  :  138,323  (11.5%)

✅ Finalizado. Datos guardados en: data/raw/spotify_raw_data.json
```

### Paso 2 — Carga en MongoDB
Lee el JSON generado e inserta todos los documentos en la colección `songs` de MongoDB.

```bash
python3 src/process_data.py
```

**Output esperado:**
```
Leidos 1,204,022 registros del archivo fuente.
Conexion establecida correctamente con MongoDB.
Insertados 1,204,022 documentos en la coleccion 'songs'.
Indice creado sobre el campo 'emocion'.
```

> ⏱️ La ingesta tarda ~30-60 segundos. La carga en MongoDB puede tardar 2-5 minutos dependiendo de tu máquina.

---

## 🚀 5. Arrancar la Aplicación

El sistema necesita **dos servicios corriendo simultáneamente** en terminales separadas:

### Terminal 1 — Backend FastAPI (puerto 8000)
```bash
source .venv/bin/activate
python -m uvicorn api:app --host 0.0.0.0 --port 8000 --reload
```

Espera hasta ver:
```
[API] Loaded 1,204,022 songs from data source.
INFO:     Application startup complete.
```

### Terminal 2 — Frontend Angular (puerto 4200)
```bash
cd frontend
npm install        # solo la primera vez
npm start
```

Espera hasta ver:
```
Application bundle generation complete.
➜  Local:   http://127.0.0.1:4200/
```

### Acceder a la app
**⚠️ Importante:** Usa siempre `http://127.0.0.1:4200` (no `localhost:4200`).
El flujo OAuth de Spotify está configurado con esa URI exacta.

---

## 🔑 6. Autenticación con Spotify

El login con Spotify usa **OAuth 2.0 con PKCE** (sin backend propio para el token).

- La `redirect_uri` registrada en el Spotify Developer Dashboard es: `http://127.0.0.1:4200/callback`
- Si quieres añadir tu cuenta de Spotify como usuario de prueba, contacta al propietario de la app en el Dashboard

> El login con email/contraseña funciona sin configuración adicional (almacenamiento local).

---

## 📁 Estructura del Proyecto

```
music_recommendation_system/
├── api.py                          # FastAPI — capa REST principal
├── pyproject.toml                  # Dependencias Python (uv)
├── requirements.txt                # Dependencias Python (pip)
├── docker-compose.yml              # MongoDB dockerizado
├── data/
│   ├── source/                     # ← Aquí va el CSV de Kaggle (no en git)
│   └── raw/                        # ← JSON generado por ingest_data.py (no en git)
├── src/
│   ├── ingest_data.py              # Paso 1: Lee CSV, clasifica emociones
│   ├── process_data.py             # Paso 2: Carga datos en MongoDB
│   └── modeling/
│       └── recommendation_engine.py # Motor ML (similitud coseno)
├── frontend/                       # Angular 21 SPA
│   ├── src/app/
│   │   ├── core/services/          # auth.service, api.service, spotify.service
│   │   └── features/               # login, dashboard, discover, playlist, callback
│   └── package.json
└── docs/                           # Documentación MkDocs
```

---

## 🧠 Lógica de Clasificación de Emociones

El nuevo dataset no incluye género musical, por lo que la emoción se infiere automáticamente de las **audio features** de Spotify:

| Emoción | Condición |
|---|---|
| **Energico** | `energy ≥ 0.75` AND `tempo ≥ 130 BPM` |
| **Alegre** | `valence ≥ 0.60` AND `danceability ≥ 0.55` |
| **Triste** | `valence ≤ 0.35` AND `acousticness ≥ 0.30` AND `energy ≤ 0.55` |
| **Neutro** | El resto |

---

## 📖 Documentación técnica

Para consultar la arquitectura y los módulos:

```bash
uv run mkdocs serve
```

Abre `http://localhost:8000` (o el puerto que indique).
