# Guía de Despliegue (Manual del Mecánico)

Esta guía detalla el proceso completo de instalación, configuración y puesta en marcha del ecosistema **SoundWave**. Sigue estos pasos para replicar el entorno de producción en una máquina local o servidor.

---

## 1. Requisitos Previos

Antes de comenzar, asegúrate de tener instaladas las siguientes herramientas:

| Herramienta | Versión mínima | Notas |
|---|---|---|
| **Python** | 3.13+ | Gestionado preferiblemente con `uv` |
| **Node.js / npm** | 18+ / 11+ | Para el frontend Angular 21 |
| **Docker** | Reciente | Para levantar la instancia de MongoDB |
| **uv** | Reciente | Reemplazo rápido de `pip` ([Instalar aquí](https://astral.sh/uv)) |

---

## 2. Infraestructura de Base de Datos

SoundWave utiliza **MongoDB 7.0** alojado en un contenedor Docker para aislar la persistencia.

### Levantar el contenedor
Ejecuta el siguiente comando en la raíz del proyecto:
```bash
docker-compose up -d
```

**Configuración por defecto:**
- **Puerto:** `27018`
- **Usuario:** `admin`
- **Contraseña:** `admin123`
- **Base de Datos:** `music_recommendation_db`

> [!TIP]
> Para detener la base de datos sin borrar los volúmenes: `docker-compose stop`. Para eliminarla: `docker-compose down`.

---

## 3. Preparación del Dataset

El dataset principal (**Spotify 1.2M+ Songs**) no está incluido en el repositorio debido a su tamaño (>300 MB).

1.  **Descarga:** Obtén el archivo `tracks_features.csv` desde [Kaggle](https://www.kaggle.com/datasets/rodolfofigueroa/spotify-12m-songs).
2.  **Ubicación:** Crea la carpeta `data/source` si no existe.
3.  **Renombrado:** Guarda el archivo como `dataset_spotify.csv` en la siguiente ruta:
    `data/source/dataset_spotify.csv`

---

## 4. Pipeline de Datos (ETL)

Con el CSV en su lugar y MongoDB activo, ejecuta el pipeline de ingesta en orden estricto:

### Paso 1: Ingesta y Clasificación Emocional
Este script limpia nulos, elimina duplicados y aplica las reglas matemáticas de clasificación de emociones.
```bash
uv run src/data/ingest_data.py
```
*Output esperado:* Archivo `data/raw/spotify_raw_data.json` generado con ~1.2M de registros.

### Paso 2: Carga y Normalización en MongoDB
Este script escala las variables continuas (tempo, loudness) y carga los documentos en la colección `songs`.
```bash
uv run src/data/process_data.py
```
*Output esperado:* "Insertados 1,204,022 documentos en la coleccion 'songs'".

---

## 5. Arranque de Servicios

SoundWave requiere tres procesos ejecutándose simultáneamente en terminales independientes:

### Terminal A: Backend API (FastAPI)
```bash
source .venv/bin/activate
uvicorn src.api.api:app --host 0.0.0.0 --port 8000 --reload
```
Acceso a documentación interactiva: `http://localhost:8000/docs`

### Terminal B: Frontend (Angular 21)
```bash
cd frontend
npm install   # Solo la primera vez
npm start
```
Acceso a la aplicación: `http://127.0.0.1:4200`

### Terminal C: Dashboard de Auditoría (Streamlit)
```bash
streamlit run src/dashboard/dashboard.py
```
Acceso al panel de control: `http://localhost:8501`

---

## 6. Configuración de Autenticación Spotify

Para que el login con Spotify funcione:
1. Crea una App en el [Spotify Developer Dashboard](https://developer.spotify.com/dashboard).
2. Configura la **Redirect URI** como: `http://127.0.0.1:4200/callback`.
3. Copia el **Client ID** en tu archivo `.env` o directamente en el servicio de Angular si prefieres un flujo puro de cliente.

---

## 7. Mantenimiento y Logs

- **Re-entrenamiento NCF:** Si cambias los datos de interacción, ejecuta `python src/modeling/train_ncf.py`.
- **Actualización de Grafo:** Para Node2Vec, ejecuta `python -m src.modeling.node2vec_engine`.
- **Logs de errores:** Revisa la carpeta `logs/` para trazas de errores del backend y del proceso de entrenamiento.

---
*Manual del Mecánico — SoundWave. Última actualización: 29/04/2026.*
