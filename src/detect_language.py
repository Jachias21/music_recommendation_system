import os
import time
import torch
import lyricsgenius
import threading
import socket
import requests
from requests.adapters import HTTPAdapter
from concurrent.futures import ThreadPoolExecutor, as_completed
from transformers import pipeline
from pymongo import MongoClient, UpdateOne
from dotenv import load_dotenv

# Forzar timeout global
socket.setdefaulttimeout(10)

base_dir = os.path.dirname(os.path.dirname(__file__))
load_dotenv(os.path.join(base_dir, ".env"))

client = MongoClient(os.getenv("MONGO_URI"))
db = client[os.getenv("DB_NAME")]
collection = db[os.getenv("COLLECTION_NAME", "songs")]

# =====================================================================
# 🌟 EL TRUCO SENIOR: INYECTAR SESIONES A GENIUS
# =====================================================================
# Creamos nuestras tuberías rápidas
custom_session = requests.Session()
adapter = HTTPAdapter(pool_connections=10, pool_maxsize=10)
custom_session.mount('https://', adapter)
custom_session.mount('http://', adapter)

genius = lyricsgenius.Genius(
    os.getenv("GENIUS_ACCESS_TOKEN"),
    timeout=5,
    retries=0
)
# ¡Hack! Le sobreescribimos su sesión lenta por nuestra sesión persistente
genius._session = custom_session 
genius.verbose = False
genius.remove_section_headers = True

TOP_50_LANGUAGES = {
    "en", "es", "zh", "hi", "fr", "ar", "bn", "ru", "pt", "ur", 
    "id", "de", "ja", "mr", "te", "tr", "ta", "vi", "ko", "it", 
    "fa", "pa", "gu", "th", "am", "jv", "bho", "ha", "my", "nl", 
    "sr", "pl", "yo", "ig", "uz", "sn", "ro", "nl", "ig", "zu", 
    "el", "sv", "uk", "cs", "hu", "fi", "da", "no", "he", "ca"
}

print("🤖 Iniciando sistema de IA en la Gráfica...")
dispositivo = 0 if torch.cuda.is_available() else -1
language_detector = pipeline(
    "text-classification", 
    model="papluca/xlm-roberta-base-language-detection",
    device=dispositivo
)

gpu_lock = threading.Lock()

def procesar_cancion_individual(cancion):
    titulo = cancion.get('name', 'Desconocido')
    artista = cancion.get('artist', 'Desconocido')
    instrumentalness = cancion.get('instrumentalness', 0.0)
    track_id = cancion.get("id") or cancion.get("track_id")

    # Filtro instrumental
    if instrumentalness > 0.6:
        op = UpdateOne({"$or": [{"id": track_id}, {"track_id": track_id}]}, 
                         {"$set": {"language": "instrumental", "lang_confidence": 1.0}})
        return op, True

    try:
        song = genius.search_song(titulo, artista)
        
        if not song or not song.lyrics:
            op = UpdateOne({"$or": [{"id": track_id}, {"track_id": track_id}]}, 
                             {"$set": {"language": "unknown", "lang_confidence": 0.5}})
            return op, False # Cuenta como "x" porque no hay letra

        texto_a_analizar = song.lyrics[:300]

        with gpu_lock:
            resultado = language_detector(texto_a_analizar[:512])[0]
        
        idioma_ia = resultado['label']
        certeza = resultado['score']
        idioma_final = idioma_ia if idioma_ia in TOP_50_LANGUAGES else "other"

        op = UpdateOne({"$or": [{"id": track_id}, {"track_id": track_id}]}, 
                         {"$set": {"language": idioma_final, "lang_confidence": float(certeza)}})
        return op, True
            
    except Exception:
        # Falla (timeout o bloqueo de Cloudflare)
        op = UpdateOne(
            {"$or": [{"id": track_id}, {"track_id": track_id}]}, 
            {"$set": {"language": "error", "lang_confidence": 0.0}}
        )
        return op, False


def procesar_lote_idiomas_turbo(max_horas, num_hilos):
    total_db = collection.count_documents({})
    pendientes = collection.count_documents({"language": {"$exists": False}})
    completadas = total_db - pendientes
    porcentaje = (completadas / total_db) * 100 if total_db > 0 else 0

    print("\n" + "="*60)
    print("🚀 MODO TURBO IDIOMAS: SESIONES PERSISTENTES")
    print("="*60)
    print(f"   📀 Total en BD:    {total_db:,}")
    print(f"   ✅ Completadas:    {completadas:,} ({porcentaje:.2f}%)")
    print(f"   ⏳ Pendientes:     {pendientes:,}")
    print(f"   ⚙️ Hilos (Threads): {num_hilos}")
    print("="*60)
    
    tiempo_inicio = time.time()
    max_segundos = max_horas * 3600
    procesadas_total = 0
    # Lote bajado a 50 para ver la velocidad en directo
    TAMAÑO_LOTE = 50 

    print(f"\n⚡ Extrayendo letras e identificando idioma... ('.' = Éxito, 'x' = Error/Fallo)")

    with ThreadPoolExecutor(max_workers=num_hilos) as executor:
        while True:
            if time.time() - tiempo_inicio > max_segundos:
                print(f"\n\n⏳ ¡Tiempo agotado!")
                break
            
            batch_songs = list(collection.find({"language": {"$exists": False}}).limit(TAMAÑO_LOTE))
            
            if not batch_songs: 
                print("\n\n✅ ¡No quedan más canciones por procesar!")
                break

            futuros = [executor.submit(procesar_cancion_individual, c) for c in batch_songs]
            operaciones_bulk = []
            
            # FEEDBACK VISUAL
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
                print(f"  | 💾 Lote de {len(operaciones_bulk)} guardado. Total: {procesadas_total}")
                
            time.sleep(0.1)

    print(f"\n🎉 Maratón finalizado. Total actualizado esta sesión: {procesadas_total} canciones.")

if __name__ == "__main__":
    CONFIG = {
        "MAX_HORAS": 20.0,
        "NUM_HILOS": 7  
    }
    
    procesar_lote_idiomas_turbo(
        max_horas=CONFIG["MAX_HORAS"],
        num_hilos=CONFIG["NUM_HILOS"]
    )