# Motores de Recomendación

SoundWave implementa una estrategia tri-modelo para garantizar recomendaciones precisas, diversas y robustas frente a problemas como el "Cold Start".

---

## 1. Content-Based Filtering (`recommendation_engine.py`)

Este es el motor base del sistema. Utiliza las características acústicas (audio features) para encontrar canciones técnicamente similares.

- **Perfil de Usuario (Centroide):** Se calcula como el valor medio de los vectores de audio features (8 dimensiones) de las canciones favoritas del usuario.
- **Similitud del Coseno:** Se compara el vector del centroide contra los candidatos filtrados por emoción en MongoDB.
- **Fórmula:** $cos(\theta) = \frac{\mathbf{A} \cdot \mathbf{B}}{\|\mathbf{A}\| \|\mathbf{B}\|}$

---

## 2. Neural Collaborative Filtering (NCF)

Basado en la arquitectura MLP (Multi-Layer Perceptron) para aprender interacciones latentes entre usuarios y canciones.

- **Arquitectura (`ncf_model.py`):**
  - **User/Item Embeddings:** Representaciones de 64 dimensiones inicializadas con Xavier Uniform.
  - **MLP Layers:** Tres capas densas de [128, 64, 32] neuronas con activación ReLU y Dropout (0.2).
  - **Output:** Una neurona con activación Sigmoid que predice la probabilidad de interacción.
- **Entrenamiento e Interacciones (`generate_interactions.py`):**
  - **Negative Sampling:** Se generan 4 muestras negativas por cada positiva.
  - **Simulación de Popularidad:** Se utiliza una **distribución de Pareto** (agresividad del 80/20 con exponente 2.0) para asignar pesos de probabilidad a las canciones según su popularidad teórica.

---

## 3. Node2Vec (Graph Embeddings)

Este motor utiliza la topología del grafo para descubrir comunidades musicales que la similitud acústica lineal no puede captar.

- **Grafo K-NN:** Se construye un grafo donde cada canción está conectada a sus 10 vecinos más cercanos en el espacio de audio features.
- **Biased Random Walks:** Utiliza parámetros $p=1.0$ (neutralidad de retorno) y $q=0.5$ (sesgo hacia la exploración de comunidades - DFS).
- **Ajustes de Post-Procesamiento:**
  - **Serendipity:** Inyección de ruido controlado (hasta 20%) para fomentar el descubrimiento de canciones inesperadas.
  - **Novelty:** Priorización de ítems con menor popularidad relativa dentro del pool de candidatos.

---

## Estrategia de Cold Start (Fallback Híbrido)

Cuando un usuario es nuevo o introduce canciones que no estaban en el conjunto de entrenamiento del modelo NCF, el sistema activa el **Fallback Híbrido Subrogado** (`ncf_inference.py`):

1. **Detección de OOV (Out-of-Vocabulary):** Si las canciones "semilla" no tienen embeddings en el NCF.
2. **Resolución Acústica:** Se buscan en el catálogo las canciones más similares acústicamente (vía Audio Features) que *sí* hayan sido entrenadas por el NCF.
3. **Inferencia por Proxy:** Estas canciones actúan como "subrogados" para generar la recomendación neuronal inicial.
4. **Fallback Final:** Si falla la resolución acústica, el sistema degrada automáticamente al modelo Content-Based puro.
