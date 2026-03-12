import os
import json
import pandas as pd
# ==========================================
# CONFIGURACIÓN DEL DATASET
# ==========================================
CSV_PATH = "data/source/dataset_spotify.csv"

GENRE_MAP = {
    "Alegre": ["happy", "pop", "dance", "ska", "party"],
    "Triste": ["sad", "acoustic", "emo", "piano", "romance"],
    "Energico": ["hardstyle", "heavy-metal", "gym", "workout", "drum-and-bass"]
}

def ingest_from_csv():
    print(f"Iniciando ingesta masiva desde: {CSV_PATH}")
    
    if not os.path.exists(CSV_PATH):
        print(f"ERROR: No se encuentra el archivo {CSV_PATH}.")
        print("Por favor, descarga el dataset de Kaggle y ponlo en esa ruta.")
        return

    # 1. Leer el archivo masivo 
    try:
        df = pd.read_csv(CSV_PATH)
        print(f"Dataset cargado. Total de canciones iniciales: {len(df)}")
    except Exception as e:
        print(f"Error al leer el CSV: {e}")
        return

    dataset_final = []
    ids_procesados = set()

    # 2. Filtrar y clasificar por emociones
    for emocion, generos in GENRE_MAP.items():
        # Filtramos el dataframe para quedarnos solo con las filas cuyo género esté en nuestra lista
        df_filtrado = df[df['track_genre'].isin(generos)]
        
        print(f"\n--- Procesando Emoción: {emocion} ---")
        print(f"Encontradas {len(df_filtrado)} canciones potenciales.")

        for _, row in df_filtrado.iterrows():
            track_id = str(row['track_id'])
            
            # Evitar duplicados (una misma canción puede estar etiquetada como 'pop' y 'party')
            if track_id not in ids_procesados:
                ids_procesados.add(track_id)
                
                # Construimos nuestro diccionario limpio tal cual lo necesita la BD
                cancion = {
                    "track_id": track_id,
                    "name": str(row.get('track_name', 'Unknown')),
                    "artist": str(row.get('artists', 'Unknown')),
                    "emocion": emocion,
                    "danceability": float(row.get('danceability', 0.0)),
                    "energy": float(row.get('energy', 0.0)),
                    "valence": float(row.get('valence', 0.0)),
                    "tempo": float(row.get('tempo', 0.0)),
                    "acousticness": float(row.get('acousticness', 0.0))
                }
                dataset_final.append(cancion)

    print(f"\nExtracción completada. Canciones únicas clasificadas: {len(dataset_final)}")

    # 3. Guardado de Datos (Capa Bronze)
    output_dir = "data/raw"
    os.makedirs(output_dir, exist_ok=True)
    output_file = os.path.join(output_dir, "spotify_raw_data.json")
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(dataset_final, f, ensure_ascii=False, indent=4)
        
    print(f" Finalizado y guardado en: {output_file}")

if __name__ == "__main__":
    ingest_from_csv()