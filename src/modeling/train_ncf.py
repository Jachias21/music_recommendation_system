import os
import sys
import pickle
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

# Configuraciones globales
DATA_PATH = os.path.join("data", "processed", "ncf_interactions.csv")
MODELS_DIR = "models"
MODEL_WEIGHTS_PATH = os.path.join(MODELS_DIR, "ncf_weights.pth")
USER_ENCODER_PATH = os.path.join(MODELS_DIR, "user_encoder.pkl")
ITEM_ENCODER_PATH = os.path.join(MODELS_DIR, "item_encoder.pkl")

BATCH_SIZE = 256
EPOCHS = 10
LEARNING_RATE = 0.001

class NCFInteractionDataset(Dataset):
    """
    Custom PyTorch Dataset for Neural Collaborative Filtering interactions.
    """
    def __init__(self, users: torch.Tensor, items: torch.Tensor, labels: torch.Tensor) -> None:
        self.users = users
        self.items = items
        self.labels = labels

    def __len__(self) -> int:
        return len(self.labels)

    def __getitem__(self, idx: int) -> Tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        return self.users[idx], self.items[idx], self.labels[idx]


def prepare_data() -> Tuple[DataLoader, DataLoader, int, int]:
    """
    Loads interactions, applies Label Encoding, saves encoders, and splits the dataset.

    Returns:
        Tuple containing:
            - train_loader (DataLoader): DataLoader for training data.
            - val_loader (DataLoader): DataLoader for validation data.
            - num_users (int): Total unique users.
            - num_items (int): Total unique items.
    """
    print("Iniciando la carga y preprocesamiento de datos...")
    
    if not os.path.exists(DATA_PATH):
        raise FileNotFoundError(f"No se encontro el archivo de datos en {DATA_PATH}")

    df = pd.read_csv(DATA_PATH)

    # 1. Label Encoding
    user_encoder = LabelEncoder()
    item_encoder = LabelEncoder()

    df['user_idx'] = user_encoder.fit_transform(df['user_id'])
    df['item_idx'] = item_encoder.fit_transform(df['item_id'])

    num_users = len(user_encoder.classes_)
    num_items = len(item_encoder.classes_)

    # 2. Guardar Encoders para produccion
    os.makedirs(MODELS_DIR, exist_ok=True)
    with open(USER_ENCODER_PATH, 'wb') as f:
        pickle.dump(user_encoder, f)
    with open(ITEM_ENCODER_PATH, 'wb') as f:
        pickle.dump(item_encoder, f)

    print(f"Encoders guardados. Usuarios unicos: {num_users}, Items unicos: {num_items}")

    # 3. Train/Validation Split (80/20)
    train_df, val_df = train_test_split(df, test_size=0.2, random_state=42, stratify=df['label'])

    # 4. Conversion a Tensores PyTorch
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

    # 5. DataLoaders
    train_loader = DataLoader(train_dataset, batch_size=BATCH_SIZE, shuffle=True)
    val_loader = DataLoader(val_dataset, batch_size=BATCH_SIZE, shuffle=False)

    return train_loader, val_loader, num_users, num_items


def train_model() -> None:
    """
    Main training loop for the NCF model.
    """
    train_loader, val_loader, num_users, num_items = prepare_data()

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Dispositivo de entrenamiento configurado: {device}")

    # Inicializar modelo, funcion de perdida y optimizador
    model = NeuralCollaborativeFiltering(num_users=num_users, num_items=num_items).to(device)
    criterion = nn.BCELoss()
    optimizer = optim.Adam(model.parameters(), lr=LEARNING_RATE, weight_decay=1e-5) # weight_decay for L2 regularization

    print("Iniciando bucle de entrenamiento...")
    
    for epoch in range(EPOCHS):
        # Fase de entrenamiento
        model.train()
        train_loss = 0.0
        
        for batch_users, batch_items, batch_labels in train_loader:
            batch_users, batch_items, batch_labels = batch_users.to(device), batch_items.to(device), batch_labels.to(device)

            optimizer.zero_grad()
            
            predictions = model(batch_users, batch_items)
            loss = criterion(predictions, batch_labels)
            
            loss.backward()
            optimizer.step()
            
            train_loss += loss.item() * batch_users.size(0)
            
        train_loss /= len(train_loader.dataset)

        # Fase de validacion
        model.eval()
        val_loss = 0.0
        
        with torch.no_grad():
            for batch_users, batch_items, batch_labels in val_loader:
                batch_users, batch_items, batch_labels = batch_users.to(device), batch_items.to(device), batch_labels.to(device)
                
                predictions = model(batch_users, batch_items)
                loss = criterion(predictions, batch_labels)
                
                val_loss += loss.item() * batch_users.size(0)
                
        val_loss /= len(val_loader.dataset)

        print(f"Epoch {epoch+1}/{EPOCHS} | Train Loss: {train_loss:.4f} | Val Loss: {val_loss:.4f}")

    # Guardar pesos del modelo
    torch.save(model.state_dict(), MODEL_WEIGHTS_PATH)
    print(f"Entrenamiento finalizado. Pesos del modelo guardados en {MODEL_WEIGHTS_PATH}")


if __name__ == "__main__":
    train_model()