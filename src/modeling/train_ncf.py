import os
import pickle
import pandas as pd
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import Dataset, DataLoader
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder
from src.modeling.ncf_model import NeuralCollaborativeFiltering

# Configuración de Rutas
DATA_PATH = os.path.join("data", "processed", "ncf_interactions.csv")
ITEMS_DATA_PATH = "dataset_soundwave_CLEAN_V3.csv" 
MODELS_DIR = "models"
MODEL_WEIGHTS_PATH = os.path.join(MODELS_DIR, "ncf_weights.pth")

# Hiperparámetros
BATCH_SIZE = 16384
EPOCHS = 30
LEARNING_RATE = 0.001

class NCFHybridDataset(Dataset):
    def __init__(self, users, items, labels, features_matrix):
        self.users = users
        self.items = items
        self.labels = labels
        self.features_matrix = features_matrix

    def __len__(self):
        return len(self.labels)

    def __getitem__(self, idx):
        item_idx = self.items[idx]
        return self.users[idx], item_idx, self.labels[idx], self.features_matrix[item_idx]

def train():
    # 1. Detección de CUDA
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"🚀 Entrenando en: {device}")

    # 2. Carga de datos
    df_interact = pd.read_csv(DATA_PATH)
    df_items = pd.read_csv(ITEMS_DATA_PATH)
    
    # Seleccionamos las variables numéricas procesadas
    feature_cols = ['danceability', 'energy', 'loudness', 'tempo', 'valence', 'deezer_rank', 'lang_confidence']
    
    # Encoders
    user_enc, item_enc = LabelEncoder(), LabelEncoder()
    df_interact['user_idx'] = user_enc.fit_transform(df_interact['user_id'])
    
    # Usamos el dataset maestro de canciones para el encoder de items
    df_items['item_idx'] = item_enc.fit_transform(df_items['track_id'])
    df_interact['item_idx'] = item_enc.transform(df_interact['item_id'])

    # Matriz de características para acceso rápido en el Dataset
    features_tensor = torch.tensor(df_items.sort_values('item_idx')[feature_cols].values, dtype=torch.float32)

    # Guardar objetos para inferencia
    os.makedirs(MODELS_DIR, exist_ok=True)
    with open(os.path.join(MODELS_DIR, "user_encoder.pkl"), 'wb') as f: pickle.dump(user_enc, f)
    with open(os.path.join(MODELS_DIR, "item_encoder.pkl"), 'wb') as f: pickle.dump(item_enc, f)

    # Split y Loaders
    train_df, val_df = train_test_split(df_interact, test_size=0.2, random_state=42)
    
    train_loader = DataLoader(NCFHybridDataset(
        torch.tensor(train_df['user_idx'].values), torch.tensor(train_df['item_idx'].values),
        torch.tensor(train_df['label'].values, dtype=torch.float32), features_tensor
    ), batch_size=BATCH_SIZE, shuffle=True)

    # 3. Inicialización del modelo con CUDA
    model = NeuralCollaborativeFiltering(
        num_users=len(user_enc.classes_), 
        num_items=len(item_enc.classes_), 
        item_features_dim=len(feature_cols)
    ).to(device)

    optimizer = optim.Adam(model.parameters(), lr=LEARNING_RATE)
    criterion = nn.BCELoss()

    # 4. Bucle de entrenamiento
    for epoch in range(EPOCHS):
        model.train()
        total_loss = 0
        for b_user, b_item, b_label, b_feat in train_loader:
            # Enviar todo a la GPU
            b_user, b_item, b_label, b_feat = b_user.to(device), b_item.to(device), b_label.to(device), b_feat.to(device)

            optimizer.zero_grad()
            output = model(b_user, b_item, item_features=b_feat)
            loss = criterion(output, b_label)
            loss.backward()
            optimizer.step()
            total_loss += loss.item()

        print(f"Época {epoch+1}/{EPOCHS} - Loss: {total_loss/len(train_loader):.4f}")
        
    torch.save(model.state_dict(), MODEL_WEIGHTS_PATH)
    print("✅ Entrenamiento completado y modelo guardado.")

if __name__ == "__main__":
    train()