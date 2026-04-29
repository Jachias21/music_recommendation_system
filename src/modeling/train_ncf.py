import os
import pickle
import pandas as pd
import torch
import torch.nn as nn
import torch.optim as optim
import matplotlib.pyplot as plt
from torch.utils.data import Dataset, DataLoader
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder, MinMaxScaler
from src.modeling.ncf_model import NeuralCollaborativeFiltering

# ──────────────────────────────────────────────────────────────────────
# CONFIGURACIÓN DE RUTAS Y PARÁMETROS
# ──────────────────────────────────────────────────────────────────────
DATA_PATH = os.path.join("data", "processed", "ncf_interactions.csv")
ITEMS_DATA_PATH = "dataset_soundwave_CLEAN_V4.csv" 
MODELS_DIR = "models"
MODEL_WEIGHTS_PATH = os.path.join(MODELS_DIR, "ncf_weights.pth")
LOSS_PLOT_PATH = os.path.join(MODELS_DIR, "training_loss.png")

BATCH_SIZE = 16384
EPOCHS = 30           # El Early Stopping parará antes si es necesario
LEARNING_RATE = 0.0003 # LR más bajo para una convergencia más estable
WEIGHT_DECAY = 1e-4    # Regularización L2 para combatir el overfitting

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
    # 1. Detección de Dispositivo (CUDA/GPU)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"🚀 Dispositivo: {device} ({torch.cuda.get_device_name(0) if device.type == 'cuda' else 'CPU'})")

    # 2. Carga y Procesamiento de Datos
    print("📖 Cargando interacciones y catálogo...")
    df_interact = pd.read_csv(DATA_PATH)
    df_items = pd.read_csv(ITEMS_DATA_PATH)
    
    if 'track_id' in df_items.columns and 'id' not in df_items.columns:
        df_items.rename(columns={'track_id': 'id'}, inplace=True)
    
    # One-Hot Encoding de Idiomas (Top 10 + Other)
    top_idiomas = ['en', 'es', 'fr', 'pt', 'de', 'it', 'ko', 'ja', 'ru', 'tr']
    df_items['lang_clean'] = df_items['language'].apply(lambda x: x if x in top_idiomas else 'other')
    df_items = pd.get_dummies(df_items, columns=['lang_clean'], dtype=float)
    lang_cols = [col for col in df_items.columns if col.startswith('lang_clean_')]
    
    # Variables acústicas críticas para adivinar géneros implícitamente
    variables_a_escalar = [
        'danceability', 'energy', 'loudness', 'tempo', 'valence', 
        'acousticness', 'instrumentalness', 'speechiness',
        'deezer_rank', 'lang_confidence'
    ]    
    feature_cols = variables_a_escalar + lang_cols
    
    df_items[feature_cols] = df_items[feature_cols].fillna(0)
    scaler = MinMaxScaler()
    df_items[variables_a_escalar] = scaler.fit_transform(df_items[variables_a_escalar])

    # Codificación de IDs
    user_enc, item_enc = LabelEncoder(), LabelEncoder()
    df_interact['user_idx'] = user_enc.fit_transform(df_interact['user_id'].astype(str))
    df_items['item_idx'] = item_enc.fit_transform(df_items['id'].astype(str))
    df_interact['item_idx'] = item_enc.transform(df_interact['item_id'].astype(str))

    features_tensor = torch.tensor(df_items.sort_values('item_idx')[feature_cols].values, dtype=torch.float32)

    # Guardar encoders para la fase de inferencia
    os.makedirs(MODELS_DIR, exist_ok=True)
    with open(os.path.join(MODELS_DIR, "user_encoder.pkl"), 'wb') as f: pickle.dump(user_enc, f)
    with open(os.path.join(MODELS_DIR, "item_encoder.pkl"), 'wb') as f: pickle.dump(item_enc, f)

    # Split 80/20
    train_df, val_df = train_test_split(df_interact, test_size=0.2, random_state=42)
    
    train_loader = DataLoader(NCFHybridDataset(
        torch.tensor(train_df['user_idx'].values), torch.tensor(train_df['item_idx'].values),
        torch.tensor(train_df['label'].values, dtype=torch.float32), features_tensor
    ), batch_size=BATCH_SIZE, shuffle=True)

    val_loader = DataLoader(NCFHybridDataset(
        torch.tensor(val_df['user_idx'].values), torch.tensor(val_df['item_idx'].values),
        torch.tensor(val_df['label'].values, dtype=torch.float32), features_tensor
    ), batch_size=BATCH_SIZE, shuffle=False)

    # 3. Inicialización del Modelo
    # item_features_dim debe ser 21 (10 idiomas + 1 other + 10 numéricas) o len(feature_cols)
    model = NeuralCollaborativeFiltering(
        num_users=len(user_enc.classes_), 
        num_items=len(item_enc.classes_), 
        item_features_dim=len(feature_cols),
        embedding_dim=64
    ).to(device)

    optimizer = optim.Adam(model.parameters(), lr=LEARNING_RATE, weight_decay=WEIGHT_DECAY)
    scheduler = optim.lr_scheduler.ReduceLROnPlateau(optimizer, mode='min', factor=0.5, patience=2)
    criterion = nn.BCELoss()

    # 4. Bucle de Entrenamiento con Early Stopping
    train_losses, val_losses = [], []
    best_val_loss = float('inf')
    patience_counter = 0
    EARLY_STOP_PATIENCE = 4 

    print(f"✨ Iniciando entrenamiento ({len(feature_cols)} features)...")

    for epoch in range(EPOCHS):
        # --- FASE DE ENTRENAMIENTO ---
        model.train()
        total_train_loss = 0
        for b_user, b_item, b_label, b_feat in train_loader:
            b_user, b_item, b_label, b_feat = b_user.to(device), b_item.to(device), b_label.to(device), b_feat.to(device)
            optimizer.zero_grad()
            output = model(b_user, b_item, item_features=b_feat)
            loss = criterion(output, b_label)
            loss.backward()
            optimizer.step()
            total_train_loss += loss.item()

        avg_train_loss = total_train_loss / len(train_loader)
        train_losses.append(avg_train_loss)

        # --- FASE DE VALIDACIÓN ---
        model.eval()
        total_val_loss = 0
        with torch.no_grad():
            for b_user, b_item, b_label, b_feat in val_loader:
                b_user, b_item, b_label, b_feat = b_user.to(device), b_item.to(device), b_label.to(device), b_feat.to(device)
                output = model(b_user, b_item, item_features=b_feat)
                v_loss = criterion(output, b_label)
                total_val_loss += v_loss.item()
        
        avg_val_loss = total_val_loss / len(val_loader)
        val_losses.append(avg_val_loss)
        
        scheduler.step(avg_val_loss)
        current_lr = optimizer.param_groups[0]['lr']

        print(f"Época {epoch+1:02d} | Train: {avg_train_loss:.4f} | Val: {avg_val_loss:.4f} | LR: {current_lr:.6f}")

        # --- GUARDAR SI ES EL MEJOR ---
        if avg_val_loss < best_val_loss:
            best_val_loss = avg_val_loss
            torch.save(model.state_dict(), MODEL_WEIGHTS_PATH)
            patience_counter = 0
            print(f"    ⭐ ¡Mejor modelo guardado! (Val Loss: {best_val_loss:.4f})")
        else:
            patience_counter += 1
            print(f"    ⚠️ Sin mejora. Paciencia: {patience_counter}/{EARLY_STOP_PATIENCE}")

        if patience_counter >= EARLY_STOP_PATIENCE:
            print(f"\n🛑 Parada temprana activada en la época {epoch+1}")
            break

    # 5. Generar Gráfica Final
    plt.figure(figsize=(10, 6))
    plt.plot(range(1, len(train_losses) + 1), train_losses, label='Train Loss')
    plt.plot(range(1, len(val_losses) + 1), val_losses, label='Val Loss')
    plt.title('Curva de Aprendizaje: NCF Híbrido')
    plt.xlabel('Época')
    plt.ylabel('Loss (BCE)')
    plt.legend()
    plt.grid(True)
    plt.savefig(LOSS_PLOT_PATH)
    plt.close()
    
    print(f"✅ Proceso finalizado. Gráfica en {LOSS_PLOT_PATH}")

if __name__ == "__main__":
    train()