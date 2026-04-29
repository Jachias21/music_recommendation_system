import pandas as pd
from pymongo import MongoClient
import os
from dotenv import load_dotenv
from sklearn.preprocessing import MinMaxScaler

load_dotenv()
client = MongoClient(os.getenv("MONGO_URI"))
db = client[os.getenv("DB_NAME")]
collection = db[os.getenv("COLLECTION_NAME", "songs")]

print("⏳ Extrayendo datos: Prioridad Absoluta al IDIOMA...")

# ==========================================
# 🔍 1. EL FILTRO DURO (Obligatorio Idioma)
# ==========================================
# Extraemos SOLO si el idioma existe y es válido.
# Nos da igual si la popularidad está o no está, ya lo arreglaremos luego.
query_idioma_obligatorio = {
    "language": {
        "$exists": True, 
        "$nin": ["error", "unknown", None]
    }
}

cursor = collection.find(query_idioma_obligatorio, {"_id": 0})
df = pd.DataFrame(list(cursor))

if df.empty:
    print("❌ No se encontraron datos válidos.")
    exit()

print(f"✅ Se han extraído {len(df):,} canciones con IDIOMA confirmado.")
print("🛠️ Fase 2: Reparación Inteligente de Popularidad...")

# ==========================================
# 📊 2. IMPUTACIÓN CONDICIONAL (El parche matemático)
# ==========================================
# 1. ¿Cuántas no tienen popularidad?
sin_rank = df['deezer_rank'].isna().sum()

# 2. Calculamos la mediana usando SOLO las que sí tienen y son comerciales (> -1)
canciones_con_rank = df[(df['deezer_rank'].notna()) & (df['deezer_rank'] > -1)]['deezer_rank']
mediana_real = canciones_con_rank.median() if not canciones_con_rank.empty else 50000

print(f"   -> Encontradas {sin_rank:,} canciones sin popularidad.")
print(f"   -> Imputando con la mediana calculada: {mediana_real}")

# 3. Rellenamos los huecos con esa mediana
df['deezer_rank'] = df['deezer_rank'].fillna(mediana_real)

# ==========================================
# 🎛️ 3. NORMALIZACIÓN PARA PYTORCH
# ==========================================
print("⚖️ Fase 3: Normalización de Audio (Tempo y Loudness)...")
cols_to_normalize = ['tempo', 'loudness']
scaler = MinMaxScaler()
df[cols_to_normalize] = scaler.fit_transform(df[cols_to_normalize])

# Escudo anti-crashes final
df = df.fillna(0)

# ==========================================
# 💾 4. EXPORTACIÓN
# ==========================================
nombre_archivo = "dataset_soundwave_CLEAN_V3.csv"
df.to_csv(nombre_archivo, index=False, encoding='utf-8')

print("\n" + "="*50)
print(f"🎉 ¡ÉXITO! Dataset de ALTO VALOR listo: {nombre_archivo}")
print(f"🚀 Total canciones listas para Node2Vec/NCF: {len(df):,}")
print("="*50)