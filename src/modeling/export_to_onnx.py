import os
import pickle
import torch
from src.modeling.ncf_model import NeuralCollaborativeFiltering

def export_model():
    MODELS_DIR = "models"
    WEIGHTS_PATH = os.path.join(MODELS_DIR, "ncf_weights.pth")
    ONNX_PATH = os.path.join(MODELS_DIR, "ncf_model.onnx")
    
    print("⏳ Cargando encoders y arquitectura del modelo...")
    
    # 1. Cargar diccionarios
    with open(os.path.join(MODELS_DIR, "user_encoder.pkl"), 'rb') as f:
        user_enc = pickle.load(f)
    with open(os.path.join(MODELS_DIR, "item_encoder.pkl"), 'rb') as f:
        item_enc = pickle.load(f)
        
    num_users = len(user_enc.classes_)
    num_items = len(item_enc.classes_)

    # 2. Inicializar el modelo con las NUEVAS MEDIDAS (18 variables y 16 dimensiones)
    model = NeuralCollaborativeFiltering(
        num_users=num_users, 
        num_items=num_items, 
        item_features_dim=20,  # <--- Nuestro nuevo One-Hot de idiomas
        embedding_dim=64       # <--- El cerebro súper rápido
    )
    
    # 3. Cargar los pesos que acabamos de entrenar
    model.load_state_dict(torch.load(WEIGHTS_PATH, map_location=torch.device('cpu')))
    model.eval()
    
    print("🧠 Modelo PyTorch cargado correctamente. Exportando a ONNX...")

    # 4. Crear tensores de prueba (Dummy Inputs) para decirle a ONNX qué forma tienen los datos
    dummy_user = torch.tensor([0], dtype=torch.long)
    dummy_item = torch.tensor([0], dtype=torch.long)
    dummy_features = torch.zeros((1, 20), dtype=torch.float32)

    # 5. Exportar el motor de inferencia
    torch.onnx.export(
        model,
        (dummy_user, dummy_item, dummy_features),
        ONNX_PATH,
        export_params=True,
        opset_version=14,
        do_constant_folding=True,
        input_names=['user_input', 'item_input', 'item_features'],
        output_names=['output'],
        dynamic_axes={
            'user_input': {0: 'batch_size'},
            'item_input': {0: 'batch_size'},
            'item_features': {0: 'batch_size'},
            'output': {0: 'batch_size'}
        }
    )
    print(f"✅ ¡Éxito! Modelo exportado a {ONNX_PATH}")

if __name__ == "__main__":
    export_model()