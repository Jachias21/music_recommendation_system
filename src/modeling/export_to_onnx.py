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
import pickle
import numpy as np
import torch
from pathlib import Path

root_path = Path(__file__).resolve().parent.parent.parent
if str(root_path) not in sys.path:
    sys.path.insert(0, str(root_path))

from src.modeling.ncf_model import NeuralCollaborativeFiltering

# ─────────────────────────────────────────────────────────────────────────────
# Rutas
# ─────────────────────────────────────────────────────────────────────────────
MODELS_DIR       = root_path / "models"
WEIGHTS_PATH     = MODELS_DIR / "ncf_weights.pth"
USER_ENC_PATH    = MODELS_DIR / "user_encoder.pkl"
ITEM_ENC_PATH    = MODELS_DIR / "item_encoder.pkl"
ONNX_PATH        = MODELS_DIR / "ncf_model.onnx"
EMBEDDINGS_PATH  = MODELS_DIR / "item_embeddings.npy"


def main():
    print("=" * 60)
    print("EXPORTACIÓN NCF → ONNX")
    print("=" * 60)

    # ── 1. Cargar encoders para dimensiones ───────────────────────────────
    if not ITEM_ENC_PATH.exists():
        raise FileNotFoundError(f"item_encoder.pkl no encontrado en {ITEM_ENC_PATH}. Ejecuta train_ncf.py primero.")

    with open(ITEM_ENC_PATH, "rb") as f:
        item_encoder = pickle.load(f)
    num_items = len(item_encoder.classes_)

    num_users = 3001  # default
    if USER_ENC_PATH.exists():
        with open(USER_ENC_PATH, "rb") as f:
            user_encoder = pickle.load(f)
        num_users = len(user_encoder.classes_)

    print(f"  Usuarios: {num_users:,} | Ítems: {num_items:,}")

    # ── 2. Instanciar modelo y cargar pesos ───────────────────────────────
    if not WEIGHTS_PATH.exists():
        raise FileNotFoundError(f"ncf_weights.pth no encontrado en {WEIGHTS_PATH}.")

    model = NeuralCollaborativeFiltering(num_users=num_users, num_items=num_items)
    state = torch.load(WEIGHTS_PATH, map_location="cpu", weights_only=True)
    model.load_state_dict(state)
    model.eval()
    print("  Pesos cargados correctamente.")

    # ── 3. Extraer y guardar la matriz de embeddings de ítems ─────────────
    item_embeddings = model.item_embedding.weight.data.cpu().numpy()
    np.save(str(EMBEDDINGS_PATH), item_embeddings)
    print(f"  Embeddings exportados: {EMBEDDINGS_PATH} → shape {item_embeddings.shape}")

    # ── 4. Definir tensores dummy para trazar el forward pass ─────────────
    batch_size = 1
    dummy_user = torch.zeros(batch_size, dtype=torch.long)
    dummy_item = torch.zeros(batch_size, dtype=torch.long)

    # Verificar forward pass
    with torch.no_grad():
        test_out = model(dummy_user, dummy_item)
    print(f"  Forward pass de prueba exitoso. Output shape: {test_out.shape}")

    # ── 5. Exportar a ONNX ────────────────────────────────────────────────
    print(f"\n  Exportando a ONNX: {ONNX_PATH}")

    torch.onnx.export(
        model,
        (dummy_user, dummy_item),
        str(ONNX_PATH),
        export_params=True,
        opset_version=17,
        do_constant_folding=True,
        input_names=["user_input", "item_input"],
        output_names=["prediction"],
        dynamic_axes={
            "user_input":  {0: "batch_size"},
            "item_input":  {0: "batch_size"},
            "prediction":  {0: "batch_size"},
        },
    )

    # ── 6. Validación del archivo ONNX ────────────────────────────────────
    import onnx
    onnx_model = onnx.load(str(ONNX_PATH))
    onnx.checker.check_model(onnx_model)

    file_size_mb = os.path.getsize(str(ONNX_PATH)) / (1024 * 1024)
    print(f"  Modelo ONNX validado correctamente. Tamaño: {file_size_mb:.2f} MB")

    # ── 7. Test rápido con ONNX Runtime ───────────────────────────────────
    import onnxruntime as ort

    sess = ort.InferenceSession(str(ONNX_PATH))
    ort_result = sess.run(
        None,
        {
            "user_input": np.zeros(1, dtype=np.int64),
            "item_input": np.zeros(1, dtype=np.int64),
        },
    )
    print(f"  Test ONNX Runtime exitoso. Predicción dummy: {ort_result[0]}")

    print("\n" + "=" * 60)
    print("EXPORTACIÓN COMPLETADA")
    print(f"  → {ONNX_PATH}")
    print(f"  → {EMBEDDINGS_PATH}")
    print("=" * 60)


if __name__ == "__main__":
    main()
