# Guía de Entrenamiento del Modelo NCF

> **Audiencia:** Compañero con PC potente (GPU NVIDIA / mucha RAM).  
> **Tiempo estimado:** ~30-60 min (generación) + ~15-30 min (entrenamiento) + ~1 min (exportación).

---

## Requisitos Previos

### Hardware Recomendado
- **GPU NVIDIA** con CUDA (el script la detecta automáticamente)
- **RAM:** ≥ 16 GB (el catálogo completo + interacciones consume ~8-10 GB)
- **Disco:** ~2 GB libres para el CSV de interacciones

### Software
- Python 3.11+
- MongoDB corriendo con el catálogo de 1.2M canciones cargado
- `uv` instalado (`pip install uv`)

### Instalación de dependencias
```bash
# Desde la raíz del proyecto
uv sync
```

> **Nota GPU:** Si tu PC tiene GPU NVIDIA, instala la versión CUDA de PyTorch:
> ```bash
> uv pip install torch --index-url https://download.pytorch.org/whl/cu121
> ```
> El script detecta automáticamente `cuda` > `mps` > `cpu`.

---

## Pipeline Completo (4 pasos)

### Paso 1: Verificar que MongoDB está corriendo

```bash
docker compose up -d
```

Comprueba que el catálogo está cargado:
```bash
python -c "
from pymongo import MongoClient
import os
from dotenv import load_dotenv
load_dotenv()
client = MongoClient(os.getenv('MONGO_URI'))
db = client[os.getenv('DB_NAME')]
col = db[os.getenv('COLLECTION_NAME')]
print(f'Canciones en MongoDB: {col.count_documents({}):,}')
"
```
Debe devolver **~1,204,000 canciones**.

---

### Paso 2: Generar Interacciones Sintéticas

```bash
uv run src/modeling/generate_interactions.py
```

**¿Qué hace?**
- Descarga el catálogo completo de MongoDB (1.2M canciones)
- Genera **100,000 usuarios sintéticos** con interacciones positivas/negativas
- Aplica distribución **Pareto 80/20** (el 20% de artistas top acumula el 80% de clics)
- Escribe directamente a disco por **chunks de 50K filas** para no saturar RAM
- **Ratio negativo:** 4 negativos por cada positivo

**Output:**
```
data/processed/ncf_interactions.csv  (~1.5-2 GB, ~15-20M filas)
```

**Tiempo estimado:** 20-40 minutos (depende de la velocidad de MongoDB).

**Parámetros configurables** (al inicio del archivo):
```python
NUM_SONGS_SAMPLE = 1_200_000   # Catálogo completo
NUM_USERS = 100_000            # Usuarios sintéticos
NEGATIVE_RATIO = 4             # 1 positivo : 4 negativos
```

---

### Paso 3: Entrenar el Modelo NCF

```bash
uv run src/modeling/train_ncf.py
```

**¿Qué hace?**
- Lee el CSV de interacciones y aplica Label Encoding
- Entrena una red neuronal MLP (embeddings 64-dim → capas 128→64→32)
- **Early Stopping:** Si la validación no mejora en 3 épocas consecutivas, para automáticamente
- Guarda el **mejor modelo** (no el último)

**Configuración del entrenamiento:**
```python
BATCH_SIZE = 16384        # Aumentar a 32768 si tienes GPU con ≥12 GB VRAM
EPOCHS = 30               # Máximo, el Early Stopping suele parar en 8-15
LEARNING_RATE = 0.001
EARLY_STOP_PATIENCE = 3
NUM_WORKERS = 4            # Hilos del DataLoader (subir a 8 si tienes muchos cores)
```

**Output:**
```
models/ncf_weights.pth     # Pesos del modelo (~50-100 MB)
models/user_encoder.pkl    # Encoder de usuarios
models/item_encoder.pkl    # Encoder de ítems
```

**Tiempo estimado:** 
- Con GPU NVIDIA: ~10-20 min
- Con CPU potente: ~30-60 min
- Con Mac M-Series (MPS): ~15-25 min

**Ejemplo de log esperado:**
```
NCF TRAINING — Escala Producción
  Batch Size: 16,384 | Epochs: 30 | LR: 0.001
  Apple Silicon (MPS) detectado.
  Filas cargadas: 17,500,000
  Encoders guardados. Usuarios: 100,000 | Items: 1,100,000

  Epoch 01/30 | Train Loss: 0.58234 | Val Loss: 0.55123 | 45.2s
    ↳ Mejor modelo guardado (val_loss=0.55123)
  Epoch 02/30 | Train Loss: 0.51002 | Val Loss: 0.50891 | 43.1s
    ↳ Mejor modelo guardado (val_loss=0.50891)
  ...
  Epoch 12/30 | Train Loss: 0.42001 | Val Loss: 0.43500 | 42.8s
    ↳ Sin mejora (3/3)

  ⛔ Early Stopping activado en época 12. Mejor val_loss: 0.42800
```

---

### Paso 4: Exportar a ONNX

```bash
uv run src/modeling/06_export_to_onnx.py
```

**¿Qué hace?**
- Carga los pesos `.pth` y exporta el modelo a formato ONNX
- Extrae la matriz de embeddings de ítems a un archivo `.npy` independiente
- Valida automáticamente el archivo ONNX y ejecuta un test con ONNX Runtime

**Output:**
```
models/ncf_model.onnx         # Modelo ONNX para inferencia en producción
models/item_embeddings.npy    # Embeddings pre-extraídos (~50 MB)
```

**Tiempo estimado:** < 1 minuto.

---

## Resumen de Archivos Generados

| Archivo | Descripción | Tamaño aprox. |
|:---|:---|:---|
| `data/processed/ncf_interactions.csv` | Dataset de entrenamiento | ~1.5 GB |
| `models/ncf_weights.pth` | Pesos PyTorch del modelo | ~80 MB |
| `models/user_encoder.pkl` | Encoder de IDs de usuario | ~5 MB |
| `models/item_encoder.pkl` | Encoder de IDs de canción | ~50 MB |
| `models/ncf_model.onnx` | Modelo en formato ONNX | ~20 MB |
| `models/item_embeddings.npy` | Embeddings de ítems | ~50 MB |

---

## Archivos a Subir al Repositorio

> ⚠️ **NO subas el CSV de interacciones** (1.5 GB). Está en `.gitignore`.

Los archivos que SÍ debes hacer commit y push son:
```bash
git add models/ncf_weights.pth models/item_encoder.pkl models/user_encoder.pkl
git add models/ncf_model.onnx models/item_embeddings.npy
git commit -m "feat: retrained NCF model (100k users, 1.2M catalog, Pareto distribution)"
git push
```

---

## Troubleshooting

### "CUDA out of memory"
Reduce `BATCH_SIZE` en `train_ncf.py` a `8192` o `4096`.

### "Killed" durante la generación de interacciones
Tu PC se quedó sin RAM. El script ya escribe por chunks, pero si aún así falla:
- Reduce `NUM_USERS` a `50000`
- O cierra otros programas que consuman RAM

### El entrenamiento es muy lento en CPU
Asegúrate de que PyTorch detecta tu GPU:
```python
import torch
print(torch.cuda.is_available())       # True para NVIDIA
print(torch.backends.mps.is_available()) # True para Mac M-Series
```

### Error de MongoDB "timeout"
Verifica que Docker está corriendo: `docker compose ps`

---

## Arquitectura del Pipeline

```
MongoDB (1.2M canciones)
        │
        ▼
generate_interactions.py  ──►  data/processed/ncf_interactions.csv
                                        │
                                        ▼
                               train_ncf.py  ──►  models/ncf_weights.pth
                                                          │
                                                          ▼
                                              06_export_to_onnx.py  ──►  models/ncf_model.onnx
                                                                         models/item_embeddings.npy
                                                                                  │
                                                                                  ▼
                                                                      ncf_inference.py (FAISS + ONNX Runtime)
                                                                                  │
                                                                                  ▼
                                                                            api.py (FastAPI)
```
