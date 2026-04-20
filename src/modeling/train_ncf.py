import os
import sys
import pickle
import time
import pandas as pd
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import Dataset, DataLoader
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder
from typing import Tuple
from pathlib import Path

root_path = Path(__file__).resolve().parent.parent.parent
if str(root_path) not in sys.path:
    sys.path.insert(0, str(root_path))

from src.modeling.ncf_model import NeuralCollaborativeFiltering

# ─────────────────────────────────────────────────────────────────────────────
# Configuración
# ─────────────────────────────────────────────────────────────────────────────
DATA_PATH = os.path.join("data", "processed", "ncf_interactions.csv")
MODELS_DIR = "models"
MODEL_WEIGHTS_PATH = os.path.join(MODELS_DIR, "ncf_weights.pth")
USER_ENCODER_PATH = os.path.join(MODELS_DIR, "user_encoder.pkl")
ITEM_ENCODER_PATH = os.path.join(MODELS_DIR, "item_encoder.pkl")

BATCH_SIZE = 16384
EPOCHS = 30
LEARNING_RATE = 0.001
EARLY_STOP_PATIENCE = 3       # Detener si val_loss no mejora en N épocas
NUM_WORKERS = 4               # Hilos paralelos para el DataLoader


# ─────────────────────────────────────────────────────────────────────────────
# Detección automática de dispositivo (CUDA > MPS > CPU)
# ─────────────────────────────────────────────────────────────────────────────
def get_device() -> torch.device:
    if torch.cuda.is_available():
        dev = torch.device("cuda")
        print(f"  GPU NVIDIA detectada: {torch.cuda.get_device_name(0)}")
    elif hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
        dev = torch.device("mps")
        print("  Apple Silicon (MPS) detectado.")
    else:
        dev = torch.device("cpu")
        print("  Usando CPU.")
    return dev


class NCFInteractionDataset(Dataset):
    def __init__(self, users: torch.Tensor, items: torch.Tensor, labels: torch.Tensor) -> None:
        self.users = users
        self.items = items
        self.labels = labels

    def __len__(self) -> int:
        return len(self.labels)

    def __getitem__(self, idx: int) -> Tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        return self.users[idx], self.items[idx], self.labels[idx]


def prepare_data(device: torch.device) -> Tuple[DataLoader, DataLoader, int, int]:
    print("\n[1/3] Carga y preprocesamiento de datos...")
    
    if not os.path.exists(DATA_PATH):
        raise FileNotFoundError(f"No se encontro el archivo de datos en {DATA_PATH}")

    # Lectura en chunks para reducir pico de RAM
    print("  Leyendo CSV...")
    df = pd.read_csv(DATA_PATH)
    print(f"  Filas cargadas: {len(df):,}")

    # Label Encoding
    user_encoder = LabelEncoder()
    item_encoder = LabelEncoder()

    df['user_idx'] = user_encoder.fit_transform(df['user_id'])
    df['item_idx'] = item_encoder.fit_transform(df['item_id'])

    num_users = len(user_encoder.classes_)
    num_items = len(item_encoder.classes_)

    # Guardar Encoders
    os.makedirs(MODELS_DIR, exist_ok=True)
    with open(USER_ENCODER_PATH, 'wb') as f:
        pickle.dump(user_encoder, f)
    with open(ITEM_ENCODER_PATH, 'wb') as f:
        pickle.dump(item_encoder, f)

    print(f"  Encoders guardados. Usuarios: {num_users:,} | Items: {num_items:,}")

    # Train/Val Split
    train_df, val_df = train_test_split(df, test_size=0.2, random_state=42, stratify=df['label'])

    train_dataset = NCFInteractionDataset(
        users=torch.tensor(train_df['user_idx'].values, dtype=torch.long),
        items=torch.tensor(train_df['item_idx'].values, dtype=torch.long),
        labels=torch.tensor(train_df['label'].values, dtype=torch.float32)
    )

    val_dataset = NCFInteractionDataset(
        users=torch.tensor(val_df['user_idx'].values, dtype=torch.long),
        items=torch.tensor(val_df['item_idx'].values, dtype=torch.long),
        labels=torch.tensor(val_df['label'].values, dtype=torch.float32)
    )

    # pin_memory solo para CUDA (no soportado en MPS)
    pin = device.type == "cuda"
    
    train_loader = DataLoader(
        train_dataset, batch_size=BATCH_SIZE, shuffle=True,
        num_workers=NUM_WORKERS, pin_memory=pin, persistent_workers=True
    )
    val_loader = DataLoader(
        val_dataset, batch_size=BATCH_SIZE, shuffle=False,
        num_workers=NUM_WORKERS, pin_memory=pin, persistent_workers=True
    )

    return train_loader, val_loader, num_users, num_items


def train_model() -> None:
    print("=" * 60)
    print("NCF TRAINING — Escala Producción")
    print(f"  Batch Size: {BATCH_SIZE:,} | Epochs: {EPOCHS} | LR: {LEARNING_RATE}")
    print(f"  Early Stopping: patience={EARLY_STOP_PATIENCE}")
    print("=" * 60)

    device = get_device()
    train_loader, val_loader, num_users, num_items = prepare_data(device)

    model = NeuralCollaborativeFiltering(num_users=num_users, num_items=num_items).to(device)
    criterion = nn.BCELoss()
    optimizer = optim.Adam(model.parameters(), lr=LEARNING_RATE, weight_decay=1e-5)
    
    # Early Stopping state
    best_val_loss = float("inf")
    patience_counter = 0

    print(f"\n[2/3] Entrenando modelo ({num_users:,} users × {num_items:,} items)...")
    
    for epoch in range(EPOCHS):
        t0 = time.time()
        
        # ── Train ─────────────────────────────────────────────────────────
        model.train()
        train_loss = 0.0
        
        for batch_users, batch_items, batch_labels in train_loader:
            batch_users = batch_users.to(device, non_blocking=True)
            batch_items = batch_items.to(device, non_blocking=True)
            batch_labels = batch_labels.to(device, non_blocking=True)

            optimizer.zero_grad()
            predictions = model(batch_users, batch_items)
            loss = criterion(predictions, batch_labels)
            loss.backward()
            optimizer.step()
            
            train_loss += loss.item() * batch_users.size(0)
            
        train_loss /= len(train_loader.dataset)

        # ── Validation ────────────────────────────────────────────────────
        model.eval()
        val_loss = 0.0
        
        with torch.no_grad():
            for batch_users, batch_items, batch_labels in val_loader:
                batch_users = batch_users.to(device, non_blocking=True)
                batch_items = batch_items.to(device, non_blocking=True)
                batch_labels = batch_labels.to(device, non_blocking=True)
                
                predictions = model(batch_users, batch_items)
                loss = criterion(predictions, batch_labels)
                val_loss += loss.item() * batch_users.size(0)
                
        val_loss /= len(val_loader.dataset)
        elapsed = time.time() - t0

        print(f"  Epoch {epoch+1:02d}/{EPOCHS} | Train Loss: {train_loss:.5f} | Val Loss: {val_loss:.5f} | {elapsed:.1f}s")

        # ── Early Stopping ────────────────────────────────────────────────
        if val_loss < best_val_loss:
            best_val_loss = val_loss
            patience_counter = 0
            # Guardar el mejor modelo hasta ahora
            torch.save(model.state_dict(), MODEL_WEIGHTS_PATH)
            print(f"    ↳ Mejor modelo guardado (val_loss={best_val_loss:.5f})")
        else:
            patience_counter += 1
            print(f"    ↳ Sin mejora ({patience_counter}/{EARLY_STOP_PATIENCE})")
            if patience_counter >= EARLY_STOP_PATIENCE:
                print(f"\n  ⛔ Early Stopping activado en época {epoch+1}. Mejor val_loss: {best_val_loss:.5f}")
                break

    print(f"\n[3/3] Entrenamiento finalizado. Pesos en: {MODEL_WEIGHTS_PATH}")
    print("=" * 60)


if __name__ == "__main__":
    train_model()