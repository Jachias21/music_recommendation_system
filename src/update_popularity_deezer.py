import os
import time
import requests
import socket
import logging
import re
from requests.adapters import HTTPAdapter
from concurrent.futures import ThreadPoolExecutor, as_completed
from pymongo import MongoClient, UpdateOne
from dotenv import load_dotenv

base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
logs_dir = os.path.join(base_dir, "logs")
os.makedirs(logs_dir, exist_ok=True)

# =====================================================================
# 📝 CONFIGURACIÓN DEL LOGGER DUAL
# =====================================================================
def clean_text(text):
    return re.sub(r'[^\x00-\x7F]+', '', str(text))

class NoEmojiFormatter(logging.Formatter):
    def format(self, record):
        original_msg = record.msg
        record.msg = clean_text(original_msg)
        result = super().format(record)
        record.msg = original_msg
        return result

logger = logging.getLogger("SoundWave_Deezer")
logger.setLevel(logging.INFO)

console_handler = logging.StreamHandler()
console_handler.setFormatter(logging.Formatter('%(message)s'))
logger.addHandler(console_handler)

file_handler = logging.FileHandler(os.path.join(logs_dir, "ejecucion_deezer.log"), mode="a", encoding="utf-8")
file_handler.setFormatter(NoEmojiFormatter('[%(asctime)s] %(levelname)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S'))
logger.addHandler(file_handler)
# =====================================================================

socket.setdefaulttimeout(10)

load_dotenv(os.path.join(base_dir, ".env"))

client = MongoClient(os.getenv("MONGO_URI"))
db = client[os.getenv("DB_NAME")]
collection = db[os.getenv("COLLECTION_NAME", "songs")]

# =====================================================================
logger.info("⚙️ Verificando/Creando índice en MongoDB (puede tardar unos segundos la primera vez)...")
collection.create_index([("deezer_rank", 1)], background=True)

# =====================================================================
session = requests.Session()
adapter = HTTPAdapter(pool_connections=50, pool_maxsize=50)
session.mount('https://', adapter)
session.mount('http://', adapter)

def buscar_rank_deezer(cancion):
    titulo = cancion.get('name', 'Desconocido')
    artista = cancion.get('artist', 'Desconocido')
    track_id = cancion.get("id") or cancion.get("track_id")
    
    query = f'track:"{titulo}" artist:"{artista}"'
    url = f"https://api.deezer.com/search?q={query}"
    
    try:
        response = session.get(url, timeout=5)
        if response.status_code == 200:
            data = response.json()
            if data.get('total', 0) > 0:
                rank = data['data'][0].get('rank')
                op = UpdateOne(
                    {"$or": [{"id": track_id}, {"track_id": track_id}]},
                    {"$set": {"deezer_rank": int(rank)}}
                )
                return op, True 
    except:
        pass
    
    op_vacia = UpdateOne(
        {"$or": [{"id": track_id}, {"track_id": track_id}]},
        {"$set": {"deezer_rank": -1}}
    )
    return op_vacia, False 


def procesar_maraton_turbo_deezer(max_horas, num_hilos):
    total_db = collection.count_documents({})
    pendientes = collection.count_documents({"deezer_rank": {"$exists": False}})
    completadas = total_db - pendientes
    porcentaje = (completadas / total_db) * 100 if total_db > 0 else 0

    logger.info("\n" + "="*60)
    logger.info(f"🚀 MODO HYPER-TURBO DEEZER: {num_hilos} HILOS + DB INDEX")
    logger.info("="*60)
    logger.info(f"   📀 Total en BD:    {total_db:,}")
    logger.info(f"   ✅ Completadas:    {completadas:,} ({porcentaje:.2f}%)")
    logger.info(f"   ⏳ Pendientes:     {pendientes:,}")
    logger.info("="*60)

    tiempo_inicio = time.time()
    max_segundos = max_horas * 3600
    procesadas_total = 0
    TAMAÑO_LOTE_MEMORIA = 100 

    logger.info(f"\n⚡ Procesando a toda velocidad... ('.' = Éxito, 'x' = Fantasma/Error)")

    with ThreadPoolExecutor(max_workers=num_hilos) as executor:
        while True:
            if time.time() - tiempo_inicio > max_segundos:
                logger.info(f"\n\n⏳ ¡Tiempo agotado! Deteniendo equipo de hilos...")
                break
            
            batch_songs = list(collection.find({"deezer_rank": {"$exists": False}}).limit(TAMAÑO_LOTE_MEMORIA))
            
            if not batch_songs: 
                logger.info("\n\n✅ ¡No quedan más canciones por procesar! ¡Base de datos completada!")
                break 

            futuros = [executor.submit(buscar_rank_deezer, c) for c in batch_songs]
            
            operaciones_bulk = []
            
            for futuro in as_completed(futuros):
                operacion, fue_exito = futuro.result()
                operaciones_bulk.append(operacion)
                if fue_exito:
                    print(".", end="", flush=True) 
                else:
                    print("x", end="", flush=True) 
            
            if operaciones_bulk:
                collection.bulk_write(operaciones_bulk, ordered=False)
                procesadas_total += len(operaciones_bulk)
                print("") 
                logger.info(f"  | 💾 Lote de {len(operaciones_bulk)} guardado. Total sesión: {procesadas_total}")

            time.sleep(0.1) 

    logger.info(f"\n🎉 ¡Maratón finalizado! Total escaneado esta sesión: {procesadas_total} canciones.")

if __name__ == "__main__":
    CONFIG = {
        "MAX_HORAS": 20.0,        
        "NUM_HILOS": 50        
    }
    
    procesar_maraton_turbo_deezer(
        max_horas=CONFIG["MAX_HORAS"],
        num_hilos=CONFIG["NUM_HILOS"]
    )