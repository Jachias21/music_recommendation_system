# Documentación de `src/process_data.py` (Procesamiento y Carga)

El archivo `process_data.py` representa los pasos finales del pipeline ETL local de nuestro sistema. Su objetivo vital es tomar los datos curados (capa Bronze generada por `ingest_data.py`) e inyectarlos de manera óptima en nuestra base de datos NoSQL operacional (MongoDB dockerizada).

## Propósito y Funcionalidad

Este script funciona como un **Data Loader** dedicado y expone configuraciones críticas:

1. **Gestión de Cadenas de Conexión y Setup Global**:
   - Define las credenciales maestras y la ruta de conexión absoluta mediante un relative path fix (`__file__`) hacia la base de datos: `MONGO_URI`, `DB_NAME` y `COLLECTION_NAME`. Estas variables clave son consumidas por la capa del API para conectarse al ecosistema persistido central.

2. **La función `process_and_load_data()`**:
   - **Lectura del almacén intermedio**: Abre y carga de un volcado el gigantesco JSON temporal (`data/raw/spotify_raw_data.json`).
   - **Handshake con MongoDB**: Instancia un cliente de conexión usando `PyMongo`, añadiendo un tiempo de espera muy corto (timeout) intencional de 5 segundos (`serverSelectionTimeoutMS=5000`). Esto lanza alertas en consola útiles a los desarrolladores si olvidaron encender el contenedor Docker (`docker-compose up -d`).
   - **Estrategia Drop & Replace (Idempotencia)**: Vacía intencionadamente la colección existente al conectarse (`collection.drop()`), previniendo colisiones de claves, duplicidades u over-fetching cuando es necesario retrocesar y actualizar el dataset.
   - **Inserción Masiva (Bulk Insert)**: Utiliza `.insert_many()` para inyectar transaccionalmente millones de documentos a la MongoDB alojada en el puerto `27018`.
   - **Optimización de Consultas (Indexación)**: Finalmente, crea automáticamente un índice de nivel de motor sobre la propiedad `emocion`. Esto reduce dramáticamente la complejidad espacial/temporal del read-flow base que hará nuestro API, ya que nuestro recomedador extrae siempre pre-filtrando el dataset según la emoción solicitada.

---

## Interacción con el Sistema

- **Como Script de Carga Batch**: Idealmente, se invoca manualmente desde la CLI desde la raíz del proyecto tras cerciorarse que Docker y el JSON previo están listos (`uv run python src/process_data.py`).
- **Proveedor de Configuración (Backend API)**: FastAPI hereda de aquí estructuralmente la base paramétrica (URI y Namespaces) eliminando redundancias y "hardcodes" en el middleware.
