import pandas as pd
import numpy as np
import os

INPUT_CSV = "dataset_soundwave_CLEAN_V4.csv"
OUTPUT_CSV = os.path.join("data", "processed", "ncf_interactions.csv")

NUM_USERS_PER_PROFILE = 1200
POS_PER_USER = 40
NEG_PER_USER = 40

def generate_data():
    print(f"📖 Leyendo catálogo...")
    df = pd.read_csv(INPUT_CSV)
    id_col = 'id' if 'id' in df.columns else 'track_id'
    all_ids = df[id_col].astype(str).values
    
    pools = {
        "urban_trap": df[(df['speechiness'] > 0.2) & (df['danceability'] > 0.65)].index.values,
        "acoustic_chill": df[(df['acousticness'] > 0.8) & (df['energy'] < 0.4)].index.values,
        "heavy_metal": df[(df['energy'] > 0.85) & (df['loudness'] > -6)].index.values,
        "jazz_inst": df[(df['instrumentalness'] > 0.7) & (df['acousticness'] > 0.5)].index.values,
        "classical": df[(df['instrumentalness'] > 0.9) & (df['energy'] < 0.3)].index.values,
        "latin": df[(df['language'] == 'es') & (df['danceability'] > 0.75)].index.values,
        "kpop": df[df['language'].isin(['ko', 'ja'])].index.values,
        "mainstream": df[df['deezer_rank'] > df['deezer_rank'].quantile(0.9)].index.values
    }

    results = []
    user_offset = 0

    print("⚡ Generando interacciones masivas (Vectorizado)...")
    for name, pool_indices in pools.items():
        if len(pool_indices) < 50: continue
        print(f"  -> Procesando {name}...")

        # Generamos IDs de usuario para este bloque
        users = [f"U{i:06d}" for i in range(user_offset, user_offset + NUM_USERS_PER_PROFILE)]
        user_offset += NUM_USERS_PER_PROFILE

        for u_id in users:
            # Seleccionamos favoritos del pool y randoms del total
            pos_pool = np.random.choice(pool_indices, int(POS_PER_USER * 0.8), replace=True)
            pos_rand = np.random.choice(len(all_ids), int(POS_PER_USER * 0.2), replace=True)
            
            # Negativas (fuera del pool)
            neg_indices = np.random.choice(len(all_ids), NEG_PER_USER, replace=True)

            # Guardamos de golpe
            for idx in pos_pool: results.append([u_id, all_ids[idx], 1])
            for idx in pos_rand: results.append([u_id, all_ids[idx], 1])
            for idx in neg_indices: results.append([u_id, all_ids[idx], 0])

    print("💾 Guardando CSV...")
    final_df = pd.DataFrame(results, columns=['user_id', 'item_id', 'label'])
    os.makedirs(os.path.dirname(OUTPUT_CSV), exist_ok=True)
    final_df.to_csv(OUTPUT_CSV, index=False)
    print(f"✅ ¡Hecho! {len(final_df)} interacciones creadas.")

if __name__ == "__main__":
    generate_data()