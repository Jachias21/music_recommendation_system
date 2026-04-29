import os
from pymongo import MongoClient
from dotenv import load_dotenv

# Obtener ruta base
base_dir = os.path.dirname(os.path.dirname(__file__))
load_dotenv(os.path.join(base_dir, ".env"))

client = MongoClient(os.getenv("MONGO_URI"))
db = client[os.getenv("DB_NAME")]
collection = db[os.getenv("COLLECTION_NAME", "songs")]

total_db = collection.count_documents({})

# --- ESTADO DE IDIOMAS ---
pendientes_lang = collection.count_documents({"language": {"$exists": False}})
completadas_lang = total_db - pendientes_lang
porcentaje_lang = (completadas_lang / total_db) * 100 if total_db > 0 else 0

print("\n" + "="*60)
print("ESTADO: DETECCIÓN DE IDIOMAS (detect_language.py)")
print("="*60)
print(f"   Total en BD:    {total_db:,}")
print(f"   Completadas:    {completadas_lang:,} ({porcentaje_lang:.2f}%)")
print(f"   Pendientes:     {pendientes_lang:,}")
print("="*60)

# --- ESTADO DE DEEZER ---
pendientes_deezer = collection.count_documents({"deezer_rank": {"$exists": False}})
completadas_deezer = total_db - pendientes_deezer
porcentaje_deezer = (completadas_deezer / total_db) * 100 if total_db > 0 else 0

print("\n" + "="*60)
print("ESTADO: POPULARIDAD DEEZER (update_popularity_deezer.py)")
print("="*60)
print(f"   Total en BD:    {total_db:,}")
print(f"   Completadas:    {completadas_deezer:,} ({porcentaje_deezer:.2f}%)")
print(f"   Pendientes:     {pendientes_deezer:,}")
print("="*60)
