import pandas as pd
from pymongo import MongoClient
import os
from dotenv import load_dotenv

load_dotenv()
client = MongoClient(os.getenv("MONGO_URI"))
db = client[os.getenv("DB_NAME")]
collection = db[os.getenv("COLLECTION_NAME", "songs")]

print("⏳ Extrayendo la base de datos completa (1.2M) para balanceo...")

# Sacamos TODO de Mongo
cursor = collection.find({}, {"_id": 0})
df = pd.DataFrame(list(cursor))

print("🧹 Aplicando Data Imputation (Limpiando NaNs y Errores para PyTorch)...")

# --- 1. ARREGLAR EL IDIOMA Y LA CONFIANZA ---
# Si es error, unknown o no existe (NaN), lo llamamos 'unprocessed'
invalid_langs = ['error', 'unknown', None]
df['language'] = df['language'].apply(lambda x: 'unprocessed' if x in invalid_langs or pd.isna(x) else x)

# Si el idioma es 'unprocessed', su confianza es 0.0 (Para que PyTorch lo ignore)
# Rellenamos los NaN de la confianza con 0.0 también
df['lang_confidence'] = df['lang_confidence'].fillna(0.0)
df.loc[df['language'] == 'unprocessed', 'lang_confidence'] = 0.0

# --- 2. ARREGLAR EL DEEZER RANK (Estadística Real) ---
# Calculamos la mediana SOLO de las canciones comerciales (mayores a -1)
# Así no dejamos que los -1 bajen la media injustamente ni creamos sesgos artificiales.
canciones_comerciales = df[df['deezer_rank'] > -1]['deezer_rank']

if not canciones_comerciales.empty:
    RANK_MEDIANA = canciones_comerciales.median()
else:
    RANK_MEDIANA = 0 

print(f"📊 Mediana de popularidad comercial calculada: {RANK_MEDIANA}")

# Rellenamos los NaN con esta mediana real para no romper la distribución espacial
df['deezer_rank'] = df['deezer_rank'].fillna(RANK_MEDIANA)

# --- 3. ESCUDO ANTI-CRASHES (Eliminar cualquier NaN residual) ---
# Años vacíos, duraciones vacías... Todo lo que quede en blanco se pone a 0.
df = df.fillna(0)

# Exportamos el CSV definitivo
nombre_archivo = "dataset_soundwave_EQUILIBRADO.csv"
df.to_csv(nombre_archivo, index=False, encoding='utf-8')

print("\n" + "="*50)
print(f"✅ ¡ÉXITO! Se ha exportado el archivo: {nombre_archivo}")
print(f"📊 Total de canciones: {len(df):,}")
print("🛡️ Nulos (NaNs) eliminados. Listo para entrenar Redes Neuronales sin crasheos.")
print("="*50)