import pandas as pd
from pymongo import MongoClient
import os
from dotenv import load_dotenv

def upload_to_production():
    load_dotenv()
    
    # 1. Configuración
    MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017/")
    DB_NAME = os.getenv("DB_NAME", "music_recommendation_db")
    # OJO: Asegúrate de que el nombre de la colección coincide con la que lee tu API
    COLLECTION_NAME = os.getenv("COLLECTION_NAME", "songs") 
    V4_CSV_PATH = "dataset_soundwave_CLEAN_V4.csv"

    print(f"🔌 Conectando a MongoDB en la base de datos: {DB_NAME}...")
    client = MongoClient(MONGO_URI)
    collection = client[DB_NAME][COLLECTION_NAME]

    # 2. Cargar el V4
    print(f"📖 Leyendo {V4_CSV_PATH}...")
    df = pd.read_csv(V4_CSV_PATH)
    
    # 3. Formatear los datos a diccionarios de Python
    records = df.to_dict(orient="records")

    # 4. Operación destructiva: Borrar catálogo viejo
    print("🗑️ Borrando el catálogo antiguo de la colección (1.2M canciones)...")
    collection.delete_many({})

    # 5. Insertar el nuevo catálogo
    print("⏳ Subiendo el catálogo V4 a Producción. Esto puede tardar un minuto...")
    collection.insert_many(records)

    print(f"✅ ¡ÉXITO! {len(records)} canciones sincronizadas con la página web.")

if __name__ == "__main__":
    upload_to_production()