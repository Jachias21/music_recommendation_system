import os
import time
import torch
import lyricsgenius
from transformers import pipeline
from pymongo import MongoClient
from dotenv import load_dotenv

# 1. Configuración Básica
base_dir = os.path.dirname(os.path.dirname(__file__))
load_dotenv(os.path.join(base_dir, ".env"))

client = MongoClient(os.getenv("MONGO_URI"))
db = client[os.getenv("DB_NAME")]
collection = db[os.getenv("COLLECTION_NAME", "songs")]

genius = lyricsgenius.Genius(os.getenv("GENIUS_ACCESS_TOKEN"))
genius.verbose = False
genius.remove_section_headers = True

# 2. La Lista VIP (50 idiomas)
TOP_50_LANGUAGES = {
    "en", "es", "zh", "hi", "fr", "ar", "bn", "ru", "pt", "ur", 
    "id", "de", "ja", "mr", "te", "tr", "ta", "vi", "ko", "it", 
    "fa", "pa", "gu", "th", "am", "jv", "bho", "ha", "my", "nl", 
    "sr", "pl", "yo", "ig", "uz", "sn", "ro", "nl", "ig", "zu", 
    "el", "sv", "uk", "cs", "hu", "fi", "da", "no", "he", "ca"
}

# 3. Cargar IA
print("🤖 Iniciando sistema de Inteligencia Artificial...")
dispositivo = 0 if torch.cuda.is_available() else -1
language_detector = pipeline(
    "text-classification", 
    model="papluca/xlm-roberta-base-language-detection",
    device=dispositivo
)

def guardar_idioma(cancion, idioma, confianza):
    track_id = cancion.get("id") or cancion.get("track_id")
    collection.update_one(
        {"$or": [{"id": track_id}, {"track_id": track_id}]},
        {"$set": {"language": idioma, "lang_confidence": confianza}}
    )

# 4. Lógica con Temporizador
def procesar_lote_idiomas(limite_canciones=15000, max_horas=2):
    # --- CÁLCULO DE ESTADÍSTICAS GLOBALES ---
    total_db = collection.count_documents({})
    pendientes = collection.count_documents({"language": {"$exists": False}})
    completadas = total_db - pendientes
    porcentaje = (completadas / total_db) * 100 if total_db > 0 else 0

    print("\n" + "="*50)
    print("📊 ESTADO GLOBAL: DETECCIÓN DE IDIOMAS")
    print("="*50)
    print(f"   📀 Total en BD:    {total_db:,}")
    print(f"   ✅ Completadas:    {completadas:,} ({porcentaje:.2f}%)")
    print(f"   ⏳ Pendientes:     {pendientes:,}")
    print("="*50)
    # ----------------------------------------

    print(f"\n🚀 INICIANDO MARATÓN: Límite {max_horas} horas o {limite_canciones} canciones.")
    
    query = {"language": {"$exists": False}}
    canciones = list(collection.find(query).limit(limite_canciones))
    
    tiempo_inicio = time.time()
    max_segundos = max_horas * 3600
    procesadas = 0

    for cancion in canciones:
        # Comprobar el reloj antes de cada canción
        tiempo_transcurrido = time.time() - tiempo_inicio
        if tiempo_transcurrido > max_segundos:
            print(f"\n⏳ ¡DING DING DING! Se han cumplido las {max_horas} horas.")
            print(f"📊 Resumen: Se procesaron {procesadas} canciones en esta sesión.")
            break

        titulo = cancion.get('name', 'Desconocido')
        artista = cancion.get('artist', 'Desconocido')
        instrumentalness = cancion.get('instrumentalness', 0.0)
        
        print(f"\n🎵 [{procesadas+1}] {titulo} - {artista} | Instr: {instrumentalness}")
        
        if instrumentalness > 0.6:
            print("   🎸 Es instrumental según Spotify. Nos saltamos la IA.")
            guardar_idioma(cancion, "instrumental", 1.0)
            procesadas += 1
            continue
            
        try:
            texto_a_analizar = ""
            song = genius.search_song(titulo, artista)
            
            if song and song.lyrics:
                texto_a_analizar = song.lyrics[:300]
            else:
                print("   ⚠️ No hay letra en Genius. Marcando como 'unknown'.")
                guardar_idioma(cancion, "unknown", 0.5)
                procesadas += 1
                continue

            resultado = language_detector(texto_a_analizar[:512])[0]
            idioma_ia = resultado['label']
            certeza = resultado['score']
            
            if idioma_ia in TOP_50_LANGUAGES:
                idioma_final = idioma_ia
                print(f"   🧠 Idioma: '{idioma_final}' ({certeza:.0%})")
            else:
                idioma_final = "other"
                print(f"   🧠 Minoritario ('{idioma_ia}'). Agrupado en 'other' ({certeza:.0%})")
            
            guardar_idioma(cancion, idioma_final, float(certeza))
            procesadas += 1
                
        except Exception as e:
            print(f"   ❌ Error: {e}")

if __name__ == "__main__":
    # Ajustado a tu prueba de 0.25 horas (15 minutos)
    procesar_lote_idiomas(limite_canciones=15000, max_horas=0.25)