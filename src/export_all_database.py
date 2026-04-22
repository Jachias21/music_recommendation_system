import pandas as pd
from pymongo import MongoClient
import os
from dotenv import load_dotenv

# Conexión
load_dotenv()
client = MongoClient(os.getenv("MONGO_URI"))
db = client[os.getenv("DB_NAME")]
collection = db[os.getenv("COLLECTION_NAME", "songs")]

print("⏳ Extrayendo ABSOLUTAMENTE TODA la base de datos de MongoDB...")

# QUERY VACÍA: Sin filtros, queremos el millón de canciones entero.
query_total = {}

# Sacamos los datos (excluimos el _id de Mongo que a Pandas/IA no le suele servir)
cursor = collection.find(query_total, {"_id": 0})

# Convertimos a un DataFrame de Pandas y exportamos a CSV
df = pd.DataFrame(list(cursor))
df.to_csv("dataset_soundwave_COMPLETO.csv", index=False, encoding='utf-8')

print(f"✅ ¡Exportación completada! Se han extraído {len(df)} canciones (Toda la base de datos).")