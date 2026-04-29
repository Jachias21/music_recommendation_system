import streamlit as st
import pandas as pd
import json
import os
import numpy as np

st.set_page_config(page_title="Music RecSys - Auditoría Multimodelo", layout="wide")

# ==========================================
# Carga de Datos
# ==========================================
@st.cache_data
def load_results():
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    res_path = os.path.join(base_dir, "data", "evaluation_results.json")
    if not os.path.exists(res_path):
        return None
    with open(res_path, "r", encoding="utf-8") as f:
        return json.load(f)

@st.cache_data
def load_catalog():
    from pymongo import MongoClient
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    env_path = os.path.join(base_dir, ".env")
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
    cursor = client[db_name][col_name].find({}, {"_id": 0, "track_id": 1, "name": 1, "artist": 1})
    df = pd.DataFrame(list(cursor))
    
    if df.empty: return {}
    
    mapping = {}
    for _, row in df.iterrows():
        id_val = str(row.get("track_id", ""))
        mapping[id_val] = f"{row.get('name', 'Unknown')} - {row.get('artist', 'Unknown')}"
    return mapping

data = load_results()
catalog = load_catalog()

# ==========================================
# UI: Cabecera
# ==========================================
st.title("Auditoría de Modelos de Recomendación")
st.markdown("""
Este panel evalúa comparativamente el rendimiento de tres arquitecturas de recomendación:
1. **Baseline**: Similitud acústica basada en audio features (Content-Based).
2. **NCF**: Neural Collaborative Filtering (Deep Learning).
3. **Node2Vec**: Graph Embeddings basados en caminatas aleatorias sobre similitudes acústicas.
""")

if not data:
    st.warning("No se encontraron resultados de evaluación. Ejecuta `python -m src.evaluation.evaluate_models` primero.")
    st.stop()

summary = data["summary"]
# In the new format, we might have 'users' in the root or not. 
# Let's check if it exists.
users = data.get("users", [])

# ==========================================
# UI: KPIs Globales
# ==========================================
st.header("1. Rendimiento Comparativo")

models = list(summary.keys())
metrics = ["hit_rate", "ndcg", "mrr", "novelty", "coverage"]

# Create a clean dataframe for metrics
display_data = []
for m in models:
    row = {"Modelo": m.upper()}
    for met in metrics:
        val = summary[m].get(met)
        if isinstance(val, dict):
            row[met.capitalize()] = val["mean"]
        else:
            row[met.capitalize()] = val
    display_data.append(row)

metrics_df = pd.DataFrame(display_data).set_index("Modelo")

st.subheader("Métricas Principales")
st.dataframe(metrics_df.style.highlight_max(axis=0, color='lightgreen'))

st.subheader("Visualización")
st.bar_chart(metrics_df[["Hit_rate", "Ndcg", "Mrr"]])

# ==========================================
# UI: Auditoría Individual
# ==========================================
if users:
    st.header("2. Auditoría Individual de Usuarios")
    
    user_ids = [u["user_id"] for u in users]
    selected_user = st.selectbox("Selecciona un usuario de prueba:", user_ids)
    
    user_data = next(u for u in users if u["user_id"] == selected_user)
    gt_set = set(user_data["ground_truth"])
    
    def resolve_name(tid):
        return catalog.get(str(tid), str(tid))

    st.markdown(f"**Emoción Objetivo:** `{user_data['target_emotion']}`")
    
    st.write("### Perfil (Seeds)")
    seed_cols = st.columns(len(user_data["seeds"]))
    for i, seed in enumerate(user_data["seeds"]):
        seed_cols[i].caption(resolve_name(seed))

    st.write("### Recomendaciones por Modelo")
    rec_cols = st.columns(len(models))
    for i, m in enumerate(models):
        with rec_cols[i]:
            st.write(f"**{m.upper()}**")
            recs = user_data.get(m, {}).get("recommendations", [])
            for r in recs:
                icon = "✅" if r in gt_set else "❌"
                st.markdown(f"{icon} {resolve_name(r)}")

    with st.expander("Ver Ground Truth Real"):
        for gt in user_data["ground_truth"]:
            st.markdown(f"- {resolve_name(gt)}")
else:
    st.info("No hay datos de usuarios individuales disponibles para auditoría en este reporte.")

st.write("---")
st.caption("Music Recommendation System - IA & Big Data P4")
