import os
import pandas as pd
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv()

# Rutas de conexión a tu MongoDB local
MONGO_URI = os.environ.get("MONGO_URI", "mongodb://localhost:27017/")
DB_NAME = os.environ.get("DB_NAME", "music_recommendation_db")
COLLECTION_NAME = os.environ.get("COLLECTION_NAME", "songs")

def export_v4_dataset():
    print("🔌 Conectando a MongoDB...")
    client = MongoClient(MONGO_URI)
    db = client[DB_NAME]
    collection = db[COLLECTION_NAME]

    # 1. FILTRO ESTRICTO: Traer solo canciones procesadas y limpias

    query = {
        "language": {"$nin": [None, "unknown", "error"]},
        "tempo": {"$exists": True, "$ne": None}
    }
    
    print("📥 Descargando catálogo limpio de la base de datos...")
    cursor = collection.find(query)
    df = pd.DataFrame(list(cursor))
    
    if df.empty:
        print("❌ No se encontraron canciones válidas.")
        return

    # Estandarizar la columna de ID (quitar el _id de Mongo que rompe el JSON)
    if "_id" in df.columns:
        df["id"] = df["_id"].astype(str)
        df.drop(columns=["_id"], inplace=True)
    elif "track_id" in df.columns:
        df["id"] = df["track_id"].astype(str)

    print(f"📊 Total de canciones Gold Standard descargadas: {len(df):,}")

    # 2. CURAR EL AGUJERO NEGRO DE LA POPULARIDAD
    if 'deezer_rank' in df.columns:
        canciones_rotas = len(df[df['deezer_rank'] == -1])
        print(f"🔍 Encontradas {canciones_rotas:,} canciones underground (-1).")

        # Calcular la MEDIANA ignorando los -1 y los vacíos
        valid_rank_df = df[(df['deezer_rank'] != -1) & (df['deezer_rank'].notna())]
        mediana_real = valid_rank_df['deezer_rank'].median()
        
        print(f"🧮 La mediana de popularidad comercial es: {mediana_real}")

        # Reemplazar los -1 y los vacíos por la mediana
        df['deezer_rank'] = df['deezer_rank'].replace(-1, mediana_real)
        df['deezer_rank'] = df['deezer_rank'].fillna(mediana_real)
        print("🛠️ Agujero negro sellado. Valores actualizados.")
    else:
        print("⚠️ Cuidado: No se encontró la columna 'deezer_rank'.")

    # 3. GUARDAR EL NUEVO DATASET DE PRODUCCIÓN
    output_path = "dataset_soundwave_CLEAN_V4.csv"
    df.to_csv(output_path, index=False)
    print(f"\n✅ ¡ÉXITO! Dataset V4 exportado correctamente a '{output_path}'.")
    print("👉 Siguiente paso: Generar interacciones apuntando a este CSV.")

if __name__ == "__main__":
    export_v4_dataset()