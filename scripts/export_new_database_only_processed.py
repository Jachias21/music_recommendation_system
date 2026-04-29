import pandas as pd
from pymongo import MongoClient
import os
from dotenv import load_dotenv

# Conexión
load_dotenv()
client = MongoClient(os.getenv("MONGO_URI"))
db = client[os.getenv("DB_NAME")]
collection = db[os.getenv("COLLECTION_NAME", "songs")]

print("⏳ Extrayendo datos limpios de MongoDB...")

# QUERYS DE FILTRADO: Solo sacamos las que tengan un idioma válido y popularidad calculada
query_limpia = {
    "language": {"$nin": ["error", "unknown", None]}, 
    "deezer_rank": {"$exists": True}
}

# Sacamos los datos (excluimos el _id de Mongo que a la IA no le sirve)
cursor = collection.find(query_limpia, {"_id": 0})

# Convertimos a un DataFrame de Pandas y exportamos a CSV
df = pd.DataFrame(list(cursor))
df.to_csv("dataset_soundwave_limpio.csv", index=False, encoding='utf-8')

print(f"✅ ¡Exportación completada! Se han extraído {len(df)} canciones listas para PyTorch.")