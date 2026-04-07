import os
import json
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure

# ==========================================
# CONFIGURACION DE BASE DE DATOS Y RUTAS
# ==========================================
_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Intentar cargar variables de entorno desde el archivo .env si existe
env_path = os.path.join(_BASE_DIR, ".env")
if os.path.exists(env_path):
    with open(env_path, "r") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())

RAW_DATA_PATH = os.path.join(_BASE_DIR, "data", "raw", "spotify_raw_data.json")
MONGO_URI = os.environ.get("MONGO_URI")
DB_NAME = os.environ.get("DB_NAME")
COLLECTION_NAME = os.environ.get("COLLECTION_NAME")

def process_and_load_data():
    print("Iniciando carga de datos en MongoDB...")

    # 1. Lectura de datos crudos
    if not os.path.exists(RAW_DATA_PATH):
        print(f"ERROR: No se encuentra el archivo de datos en {RAW_DATA_PATH}")
        return

    with open(RAW_DATA_PATH, 'r', encoding='utf-8') as file:
        try:
            dataset = json.load(file)
        except json.JSONDecodeError as e:
            print(f"ERROR al decodificar el archivo JSON: {e}")
            return
    
    print(f"Leidos {len(dataset)} registros del archivo fuente.")

    # 2. Conexion a la base de datos
    try:
        # Añadimos un timeout corto para que falle rapido si Mongo no esta encendido
        client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
        client.admin.command('ping')
        print("Conexion establecida correctamente con MongoDB.")
    except ConnectionFailure:
        print("ERROR: No se ha podido conectar a MongoDB. Comprueba que el servicio o contenedor esta en ejecucion.")
        return

    db = client[DB_NAME]
    collection = db[COLLECTION_NAME]

    # 3. Limpieza de coleccion (Drop)
    # En fase de desarrollo vaciamos la coleccion antes de insertar para evitar duplicados
    print("Limpiando estado anterior de la coleccion...")
    collection.drop()

    # 4. Insercion masiva (Bulk Insert)
    if dataset:
        try:
            result = collection.insert_many(dataset)
            print(f"Insertados {len(result.inserted_ids)} documentos en la coleccion '{COLLECTION_NAME}'.")
            
            # 5. Optimizacion: Creacion de indices
            # Creamos un indice en el campo 'emocion' para acelerar los filtros del recomendador
            collection.create_index("emocion")
            print("Indice creado sobre el campo 'emocion'.")
            
        except Exception as e:
            print(f"ERROR durante la insercion de datos: {e}")
    else:
        print("ADVERTENCIA: El dataset esta vacio. No se ha insertado ningun registro.")

if __name__ == "__main__":
    process_and_load_data()