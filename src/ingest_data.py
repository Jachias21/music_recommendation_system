import os
import json
import ast
import pandas as pd
import numpy as np

# ==========================================
# CONFIGURACIÓN DEL DATASET
# ==========================================

# Rutas relativas a la raíz del proyecto (funciona sin importar el CWD)
_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CSV_PATH = os.path.join(_BASE_DIR, "data", "source", "dataset_spotify.csv")


def _clean_artists_series(series: pd.Series) -> pd.Series:
    """Convierte "['Artist A', 'Artist B']" en "Artist A, Artist B" (vectorizado)."""
    def _parse(raw):
        try:
            parsed = ast.literal_eval(str(raw))
            if isinstance(parsed, list):
                return ", ".join(str(a) for a in parsed)
        except Exception:
            pass
        return str(raw)
    return series.map(_parse)


def _classify_emotions(df: pd.DataFrame) -> pd.Series:
    """
    Clasifica la emoción usando reglas vectorizadas sobre audio features.

    Lógica (orden de prioridad):
      1. Energico  → energy ≥ 0.75  AND  tempo ≥ 130
      2. Alegre    → valence ≥ 0.60 AND  danceability ≥ 0.55
      3. Triste    → valence ≤ 0.35 AND  acousticness ≥ 0.30 AND energy ≤ 0.55
      4. Neutro    → resto
    """
    conditions = [
        (df["energy"] >= 0.75) & (df["tempo"] >= 130),
        (df["valence"] >= 0.60) & (df["danceability"] >= 0.55),
        (df["valence"] <= 0.35) & (df["acousticness"] >= 0.30) & (df["energy"] <= 0.55),
    ]
    choices = ["Energico", "Alegre", "Triste"]
    return np.select(conditions, choices, default="Neutro")


def ingest_from_csv():
    print(f"Iniciando ingesta masiva desde:\n  {CSV_PATH}\n")

    if not os.path.exists(CSV_PATH):
        print(f"ERROR: No se encuentra {CSV_PATH}")
        print("Asegúrate de que el CSV está en data/source/dataset_spotify.csv")
        return

    # 1. Leer CSV
    try:
        df = pd.read_csv(CSV_PATH, low_memory=False)
        print(f"Dataset cargado:  {len(df):>10,} filas")
        print(f"Columnas: {df.columns.tolist()}\n")
    except Exception as e:
        print(f"Error leyendo CSV: {e}")
        return

    # 2. Limpieza: nulos y duplicados
    columnas_requeridas = [
        "id", "name", "artists",
        "danceability", "energy", "valence",
        "tempo", "acousticness",
    ]
    df = df.dropna(subset=columnas_requeridas)
    df = df.drop_duplicates(subset=["id"])
    print(f"Tras limpiar nulos y duplicados: {len(df):>10,} filas")

    # 3. Conversión de tipos (segura)
    num_cols = ["danceability", "energy", "valence", "tempo",
                "acousticness", "instrumentalness", "liveness",
                "speechiness", "loudness"]
    for col in num_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)

    # 4. Clasificación de emociones (vectorizada, ~100× más rápido que iterrows)
    df["emocion"] = _classify_emotions(df)

    # 5. Limpieza de artistas (series.map, mucho más rápido que bucle)
    df["artists_clean"] = _clean_artists_series(df["artists"])

    # 6. Columna year
    if "year" in df.columns:
        df["year"] = pd.to_numeric(df["year"], errors="coerce")
    else:
        df["year"] = np.nan

    # 7. Estadísticas de distribución
    conteo = df["emocion"].value_counts()
    print("\nClasificación completada. Distribución por emoción:")
    for emocion, n in conteo.items():
        pct = 100 * n / len(df)
        print(f"  {emocion:10s}: {n:>8,}  ({pct:.1f}%)")

    # 8. Construir lista de documentos (to_dict es vectorizado)
    output_cols = {
        "track_id":        "id",
        "name":            "name",
        "artist":          "artists_clean",
        "album":           "album",
        "emocion":         "emocion",
        "danceability":    "danceability",
        "energy":          "energy",
        "valence":         "valence",
        "tempo":           "tempo",
        "acousticness":    "acousticness",
        "instrumentalness":"instrumentalness",
        "liveness":        "liveness",
        "speechiness":     "speechiness",
        "loudness":        "loudness",
    }

    df_out = pd.DataFrame()
    for out_col, src_col in output_cols.items():
        if src_col in df.columns:
            df_out[out_col] = df[src_col]
        else:
            df_out[out_col] = None

    # year como int o None
    df_out["year"] = df["year"].apply(lambda v: int(v) if pd.notna(v) else None)

    # Redondear floats
    float_cols = ["danceability","energy","valence","acousticness",
                  "instrumentalness","liveness","speechiness"]
    for col in float_cols:
        if col in df_out.columns:
            df_out[col] = df_out[col].round(4)
    df_out["tempo"]    = df_out["tempo"].round(2)
    df_out["loudness"] = df_out["loudness"].round(2)

    dataset_final = df_out.to_dict(orient="records")
    print(f"\nTotal canciones a guardar: {len(dataset_final):,}")

    # 9. Guardar en capa Bronze (JSON)
    output_dir = os.path.join(_BASE_DIR, "data", "raw")
    os.makedirs(output_dir, exist_ok=True)
    output_file = os.path.join(output_dir, "spotify_raw_data.json")

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(dataset_final, f, ensure_ascii=False, indent=2)

    print(f"\nFinalizado. Datos guardados en:\n  {output_file}")


if __name__ == "__main__":
    ingest_from_csv()