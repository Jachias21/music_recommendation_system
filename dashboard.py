import streamlit as st
import pandas as pd
import json
import os

st.set_page_config(page_title="NCF vs Base - Auditoría de Modelos", layout="wide")

# ==========================================
# Carga de Datos
# ==========================================
@st.cache_data
def load_results():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    res_path = os.path.join(base_dir, "data", "evaluation_results.json")
    if not os.path.exists(res_path):
        return None
    with open(res_path, "r", encoding="utf-8") as f:
        return json.load(f)

@st.cache_data
def load_catalog():
    # Load just enough to resolve names
    # Connect to mongo directly or read from a dump, but for simplicity of the dashboard
    # we can just use pymongo directly
    from pymongo import MongoClient
    
    env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    if os.path.exists(env_path):
        with open(env_path, "r") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    os.environ.setdefault(k.strip(), v.strip())
                    
    uri = os.environ.get("MONGO_URI", "mongodb://127.0.0.1:27017")
    db_name = os.environ.get("DB_NAME", "music_recommendation_db")
    col_name = os.environ.get("COLLECTION_NAME", "songs")
    
    client = MongoClient(uri)
    cursor = client[db_name][col_name].find({}, {"_id": 0, "id": 1, "track_id": 1, "name": 1, "artist": 1})
    df = pd.DataFrame(list(cursor))
    
    if df.empty:
        return {}
        
    if "track_id" in df.columns and "id" not in df.columns:
        df["id"] = df["track_id"].astype(str)
    
    # Create dict mapping id -> "Name - Artist"
    mapping = {}
    for _, row in df.iterrows():
        id_val = str(row.get("id", ""))
        mapping[id_val] = f"{row.get('name', 'Unknown')} - {row.get('artist', 'Unknown')}"
    return mapping

data = load_results()
catalog = load_catalog()

# ==========================================
# UI: Cabecera
# ==========================================
st.title("Auditoría de Modelos: NCF vs Motores de Contenido")
st.markdown("""
Este panel interactivo evalúa el rendimiento del sistema de recomendación híbrido.
Comparamos el motor original (Similitud del Coseno Acústica) con el nuevo modelo de **Neural Collaborative Filtering (NCF)** 
sobre un volumen de 200 usuarios sintéticos *Hold-out*.
""")

if not data:
    st.warning("No se encontró el archivo `data/evaluation_results.json`. Ejecuta `uv run src/evaluation/evaluate_models.py` primero.")
    st.stop()

summary = data["summary"]
users = data["users"]

# ==========================================
# UI: KPIs Globales
# ==========================================
st.header("1. Rendimiento Global (Métricas @5)")

col1, col2, col3, col4 = st.columns(4)

def get_delta(ncf_val, base_val, is_pct=True):
    if base_val == 0: return "N/A"
    diff = ncf_val - base_val
    if is_pct:
        pct = (diff / base_val) * 100
        return f"{pct:+.1f}%"
    return f"{diff:+.3f}"

ncf_s = summary["ncf"]
base_s = summary["base"]

col1.metric("Precision@5 (NCF)", f"{ncf_s['precision']:.3f}", get_delta(ncf_s['precision'], base_s['precision']))
col2.metric("Recall@5 (NCF)", f"{ncf_s['recall']:.3f}", get_delta(ncf_s['recall'], base_s['recall']))
col3.metric("NDCG@5 (NCF)", f"{ncf_s['ndcg']:.3f}", get_delta(ncf_s['ndcg'], base_s['ndcg']))
col4.metric("Novelty (NCF)", f"{ncf_s['novelty']:.3f}", get_delta(ncf_s['novelty'], base_s['novelty'], is_pct=False))

# ==========================================
# UI: Gráficas de Comparación
# ==========================================
st.subheader("Comparativa de Modelos")

metrics_df = pd.DataFrame({
    "Métrica": ["Precision@5", "Recall@5", "NDCG@5", "Novelty"],
    "NCF": [ncf_s["precision"], ncf_s["recall"], ncf_s["ndcg"], ncf_s["novelty"]],
    "Base (Acústico)": [base_s["precision"], base_s["recall"], base_s["ndcg"], base_s["novelty"]]
}).set_index("Métrica")

st.bar_chart(metrics_df, height=350)

# ==========================================
# UI: Análisis de Ranking Acumulado
# ==========================================
st.subheader("Distribución de Ranking Empírico")
st.markdown("¿En qué posición exacta de la lista (1 al 5) acierta cada modelo?")

ncf_ranks = {1:0, 2:0, 3:0, 4:0, 5:0}
base_ranks = {1:0, 2:0, 3:0, 4:0, 5:0}

for u in users:
    gt = set(u["ground_truth"])
    for i, rec in enumerate(u["ncf"]["recommendations"][:5]):
        if rec in gt: ncf_ranks[i+1] += 1
    for i, rec in enumerate(u["base"]["recommendations"][:5]):
        if rec in gt: base_ranks[i+1] += 1

rank_df = pd.DataFrame({
    "Posición": ["Top 1", "Top 2", "Top 3", "Top 4", "Top 5"],
    "Aciertos NCF": list(ncf_ranks.values()),
    "Aciertos Base": list(base_ranks.values())
}).set_index("Posición")

st.line_chart(rank_df, height=300)

# ==========================================
# UI: Casos de Uso Reales (Auditoría)
# ==========================================
st.header("2. Auditoría Individual de Usuarios")

user_ids = [u["user_id"] for u in users]
selected_user = st.selectbox("Selecciona un usuario de prueba:", user_ids)

user_data = next(u for u in users if u["user_id"] == selected_user)
gt_set = set(user_data["ground_truth"])

def resolve_name(track_id):
    name = catalog.get(str(track_id), str(track_id))
    return f"{name}"

st.markdown(f"**Emoción Objetivo:** `{user_data['target_emotion']}`")

st.write("###Perfil del Usuario (Seeds ingresadas para Inferencia)")
for seed in user_data["seeds"]:
    st.markdown(f"- {resolve_name(seed)}")
    
c1, c2 = st.columns(2)

with c1:
    st.write("###Predicción NCF (Latent Pairwise)")
    for rec in user_data["ncf"]["recommendations"]:
        icon = "✅" if rec in gt_set else "❌"
        st.markdown(f"{icon} {resolve_name(rec)}")
        
with c2:
    st.write("###Predicción Base (Acoustic Cosine)")
    for rec in user_data["base"]["recommendations"]:
        icon = "✅" if rec in gt_set else "❌"
        st.markdown(f"{icon} {resolve_name(rec)}")

st.write("---")
with st.expander("Ver Ground Truth Real (Las canciones que realmente le gustan al usuario)"):
    for gt in user_data["ground_truth"]:
        st.markdown(f"- {resolve_name(gt)}")

