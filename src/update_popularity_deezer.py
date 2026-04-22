import os
import time
import requests
import socket
from requests.adapters import HTTPAdapter
from concurrent.futures import ThreadPoolExecutor, as_completed
from pymongo import MongoClient, UpdateOne
from dotenv import load_dotenv

socket.setdefaulttimeout(10)

base_dir = os.path.dirname(os.path.dirname(__file__))
load_dotenv(os.path.join(base_dir, ".env"))

client = MongoClient(os.getenv("MONGO_URI"))
db = client[os.getenv("DB_NAME")]
collection = db[os.getenv("COLLECTION_NAME", "songs")]

# =====================================================================
# 🌟 TRUCO 1: ÍNDICE DE BASE DE DATOS (ELIMINA EL CANSANCIO DE MONGO)
# =====================================================================
print("⚙️ Verificando/Creando índice en MongoDB (puede tardar unos segundos la primera vez)...")
# Esto crea un índice en segundo plano. Hace que buscar canciones sin rank sea instantáneo.
collection.create_index([("deezer_rank", 1)], background=True)

# =====================================================================
# 🌟 TRUCO 2: CONNECTION POOLING AL LÍMITE (50 TUBERÍAS)
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

    print("\n" + "="*60)
    print(f"🚀 MODO HYPER-TURBO DEEZER: {num_hilos} HILOS + DB INDEX")
    print("="*60)
    print(f"   📀 Total en BD:    {total_db:,}")
    print(f"   ✅ Completadas:    {completadas:,} ({porcentaje:.2f}%)")
    print(f"   ⏳ Pendientes:     {pendientes:,}")
    print("="*60)

    tiempo_inicio = time.time()
    max_segundos = max_horas * 3600
    procesadas_total = 0
    # Mantenemos el lote a 100 para ver la velocidad en directo
    TAMAÑO_LOTE_MEMORIA = 100 

    print(f"\n⚡ Procesando a toda velocidad... ('.' = Éxito, 'x' = Fantasma/Error)")

    with ThreadPoolExecutor(max_workers=num_hilos) as executor:
        while True:
            if time.time() - tiempo_inicio > max_segundos:
                print(f"\n\n⏳ ¡Tiempo agotado! Deteniendo equipo de hilos...")
                break
            
            # ¡Gracias al índice, esta línea ahora tardará 0.001 segundos siempre!
            batch_songs = list(collection.find({"deezer_rank": {"$exists": False}}).limit(TAMAÑO_LOTE_MEMORIA))
            
            if not batch_songs: 
                print("\n\n✅ ¡No quedan más canciones por procesar! ¡Base de datos completada!")
                break 

            futuros = [executor.submit(buscar_rank_deezer, c) for c in batch_songs]
            
            operaciones_bulk = []
            exitos_lote = 0
            descartes_lote = 0
            
            for futuro in as_completed(futuros):
                operacion, fue_exito = futuro.result()
                operaciones_bulk.append(operacion)
                if fue_exito:
                    exitos_lote += 1
                    print(".", end="", flush=True) 
                else:
                    descartes_lote += 1
                    print("x", end="", flush=True) 
            
            if operaciones_bulk:
                collection.bulk_write(operaciones_bulk, ordered=False)
                procesadas_total += len(operaciones_bulk)
                print(f"  | 💾 Lote de {len(operaciones_bulk)} guardado. Total sesión: {procesadas_total}")

            time.sleep(0.1) 

    print(f"\n🎉 ¡Maratón finalizado! Total escaneado esta sesión: {procesadas_total} canciones.")


if __name__ == "__main__":
    CONFIG = {
        "MAX_HORAS": 20.0,        
        "NUM_HILOS": 50   # 🚀 Subimos a 50 (el límite seguro de la API de Deezer)       
    }
    
    procesar_maraton_turbo_deezer(
        max_horas=CONFIG["MAX_HORAS"],
        num_hilos=CONFIG["NUM_HILOS"]
    )