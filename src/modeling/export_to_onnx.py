"""
Script de Exportación del modelo NCF a formato ONNX
====================================================
Convierte los pesos preentrenados de PyTorch (.pth) al estándar ONNX
para inferencia optimizada con ONNX Runtime en producción.

Artefactos generados:
  - models/ncf_model.onnx          → Modelo completo en formato ONNX
  - models/item_embeddings.npy     → Matriz de embeddings de ítems (NumPy)

Uso:
  uv run src/modeling/06_export_to_onnx.py
"""

import os
import sys

# Añadir el directorio raíz del proyecto al PYTHONPATH
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import torch
import pickle
from src.modeling.ncf_model import NeuralCollaborativeFiltering

# Rutas
MODELS_DIR = "models"
MODEL_WEIGHTS_PATH = os.path.join(MODELS_DIR, "ncf_weights.pth")
USER_ENCODER_PATH = os.path.join(MODELS_DIR, "user_encoder.pkl")
ITEM_ENCODER_PATH = os.path.join(MODELS_DIR, "item_encoder.pkl")
ONNX_MODEL_PATH = os.path.join(MODELS_DIR, "ncf_model.onnx")

def export_hybrid_to_onnx():
    print("Iniciando exportación a ONNX del Modelo Híbrido...")

    # 1. Cargar Encoders para saber el tamaño de la red
    with open(USER_ENCODER_PATH, 'rb') as f:
        user_enc = pickle.load(f)
    with open(ITEM_ENCODER_PATH, 'rb') as f:
        item_enc = pickle.load(f)

    num_users = len(user_enc.classes_)
    num_items = len(item_enc.classes_)
    
    # 🚨 IMPORTANTE: Tus 7 variables extra (danceability, energy, loudness, tempo, valence, deezer_rank, lang_confidence)
    item_features_dim = 7 

    # 2. Reconstruir el modelo
    model = NeuralCollaborativeFiltering(
        num_users=num_users, 
        num_items=num_items, 
        item_features_dim=item_features_dim
    )
    
    # Cargar los pesos que acabas de entrenar
    model.load_state_dict(torch.load(MODEL_WEIGHTS_PATH, map_location=torch.device('cpu')))
    model.eval() # Modo evaluación (apaga el Dropout)

    # 3. Crear tensores de ejemplo (Dummy Inputs) para que ONNX trace el mapa
    dummy_user = torch.tensor([0], dtype=torch.long)
    dummy_item = torch.tensor([0], dtype=torch.long)
    dummy_features = torch.zeros((1, item_features_dim), dtype=torch.float32)

    # 4. Exportar a ONNX
    print(f"Exportando modelo con {num_users:,} usuarios y {num_items:,} canciones...")
    
    torch.onnx.export(
        model, 
        (dummy_user, dummy_item, dummy_features), # <--- Los 3 inputs de nuestro modelo híbrido
        ONNX_MODEL_PATH,
        export_params=True,
        opset_version=14, # Versión estable de ONNX
        do_constant_folding=True,
        input_names=['user_input', 'item_input', 'item_features_input'], # Nombres clave
        output_names=['prediction'],
        dynamic_axes={
            'user_input': {0: 'batch_size'},
            'item_input': {0: 'batch_size'},
            'item_features_input': {0: 'batch_size'},
            'prediction': {0: 'batch_size'}
        }
    )

    print(f"¡ÉXITO! Modelo Híbrido ONNX exportado en: {ONNX_MODEL_PATH}")

if __name__ == "__main__":
    export_hybrid_to_onnx()