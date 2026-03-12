# Documentación de `src/process_data.py` (Procesamiento y Carga)

El archivo `process_data.py` representa los dos últimos pasos (Transform & Load) del pipeline de datos de nuestro sistema. Su objetivo vital es tomar los datos curados locales (capa Bronze) e inyectarlos de manera óptima en nuestra base de datos NoSQL operacional (MongoDB).

## Propósito y Funcionalidad

Este script funciona como un **Data Loader** dedicado y expone configuración crítica que el resto del sistema consume:

1. **Gestión de variables de entorno global**:
   - Define las credenciales maestras y la ruta de conexión a la base de datos: `MONGO_URI`, `DB_NAME` y `COLLECTION_NAME`. Estas variables son consumidas posteriormente por la interfaz gráfica (`app.py`) y el motor (`recommendation_engine.py`) para saber a dónde apuntar, centralizando así la configuración de infraestructura.

2. **La función `process_and_load_data()`**:
   - **Lectura del almacén intermedio**: Lee el archivo local `data/raw/spotify_raw_data.json` que fue generado previamente por el script `ingest_data.py`.
   - **Handshake con MongoDB**: Inicia un cliente de conexión usando `PyMongo`, añadiendo un tiempo de espera muy corto intencional de 5 segundos (`serverSelectionTimeoutMS=5000`). Esto lanza una alerta útil a los desarrolladores si olvidaron encender el motor de Docker. 
   - **Estrategia Drop & Replace**: Debido a que se trata del catálogo maestro, el script vacía intencionadamente la colección existente (`collection.drop()`). De este modo se evitan colisiones de IDs rotos o duplicidad parciales cuando un data engineer vuelva a inyectar un dataset modificado.
   - **Inserción Masiva (Bulk Insert)**: Utiliza `insert_many` para grabar la lista completa de miles de canciones en la memoria de MongoDB de un único golpe transaccional.
   - **Optimización de Consultas (Indexación)**: Finalmente, crea un "Índice" de nivel de base de datos automatizado sobre el campo `emocion`. Esto reduce dramáticamente la complejidad temporal de las consultas transversales (query performance) futuras, ya que nuestro motor de Machine Learning en `app.py` filtra estrictamente por emoción en su primer paso.

---

## Interacción con el Sistema

- **Como Script de Carga**: Se ejecuta (por ejemplo, desde terminal mediante `python -m src.process_data`) justo antes o después de encender los contenedores de Docker (`docker-compose up -d`) para rellenar de datos la base local viva.
- **Como Módulo de Configuración**: Todo el sistema de **Streamlit** importa estas 3 variables estáticas (`MONGO_URI`, `DB_NAME`, `COLLECTION_NAME`) para acceder al catálogo musical sin quemarlas directamente en su lógica.  Al conectarse, es la interfaz quien disfruta del índice de búsqueda `emocion` preconstruido aquí.
