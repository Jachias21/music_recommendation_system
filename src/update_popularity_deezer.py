import os
import time
import requests
from pymongo import MongoClient, UpdateOne
from dotenv import load_dotenv

# 1. Cargar configuración
base_dir = os.path.dirname(os.path.dirname(__file__))
load_dotenv(os.path.join(base_dir, ".env"))

client = MongoClient(os.getenv("MONGO_URI"))
db = client[os.getenv("DB_NAME")]
collection = db[os.getenv("COLLECTION_NAME", "songs")]

def buscar_rank_deezer(titulo, artista):
    query = f'track:"{titulo}" artist:"{artista}"'
    url = f"https://api.deezer.com/search?q={query}"
    try:
        response = requests.get(url, timeout=5) # 5 segundos máximo de espera
        if response.status_code == 200:
            data = response.json()
            if data.get('total', 0) > 0:
                return data['data'][0].get('rank')
        return None
    except Exception as e:
        return None

def procesar_maraton_deezer(limite_canciones=50000, max_horas=2):
    # --- CÁLCULO DE ESTADÍSTICAS GLOBALES ---
    total_db = collection.count_documents({})
    pendientes = collection.count_documents({"deezer_rank": {"$exists": False}})
    completadas = total_db - pendientes
    porcentaje = (completadas / total_db) * 100 if total_db > 0 else 0

    print("\n" + "="*50)
    print("📊 ESTADO GLOBAL: POPULARIDAD (DEEZER RANK)")
    print("="*50)
    print(f"   📀 Total en BD:    {total_db:,}")
    print(f"   ✅ Completadas:    {completadas:,} ({porcentaje:.2f}%)")
    print(f"   ⏳ Pendientes:     {pendientes:,}")
    print("="*50)
    # ----------------------------------------

    print(f"\n🚀 INICIANDO MARATÓN DEEZER: Límite {max_horas} horas o {limite_canciones} canciones.")
    
    query = {"deezer_rank": {"$exists": False}}
    canciones = list(collection.find(query).limit(limite_canciones))

    if not canciones:
        print("✅ ¡Misión cumplida! Toda la base de datos tiene ranking.")
        return

    tiempo_inicio = time.time()
    max_segundos = max_horas * 3600
    operaciones_bulk = []
    procesadas_exito = 0

    for i, cancion in enumerate(canciones):
        # Control del reloj
        if time.time() - tiempo_inicio > max_segundos:
            print(f"\n⏳ ¡Tiempo agotado! Se han cumplido las {max_horas} horas.")
            break

        titulo = cancion.get('name', 'Desconocido')
        artista = cancion.get('artist', 'Desconocido')
        
        print(f"🎵 [{i+1}/{len(canciones)}] Buscando: {titulo} - {artista}")
        
        rank = buscar_rank_deezer(titulo, artista)
        
        if rank is not None:
            track_id = cancion.get("id") or cancion.get("track_id")
            op = UpdateOne(
                {"$or": [{"id": track_id}, {"track_id": track_id}]},
                {"$set": {"deezer_rank": int(rank)}}
            )
            operaciones_bulk.append(op)
            procesadas_exito += 1
            print(f"   📈 Rank: {rank}")
        else:
            print("   ⚠️ No encontrado.")

        # Guardar cada 100 canciones
        if len(operaciones_bulk) >= 100:
            collection.bulk_write(operaciones_bulk)
            operaciones_bulk = []
            
        time.sleep(0.2) # Respetar a Deezer

    if operaciones_bulk:
        collection.bulk_write(operaciones_bulk)

    print(f"\n🎉 Maratón finalizado. Se actualizaron {procesadas_exito} canciones nuevas.")

if __name__ == "__main__":
    # Ajustado a tu prueba de 0.25 horas (15 minutos)
    procesar_maraton_deezer(limite_canciones=50000, max_horas=0.25)