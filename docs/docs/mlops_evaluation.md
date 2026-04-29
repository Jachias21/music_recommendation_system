# MLOps y Evaluación de Modelos

El rigor científico es fundamental en SoundWave. Implementamos un pipeline de evaluación exhaustivo para comparar nuestras arquitecturas y garantizar la calidad de las recomendaciones en producción.

---

## Protocolo de Evaluación (`evaluate_models.py`)

Para medir la capacidad de ranking de los modelos, utilizamos el protocolo **Leave-One-Out** con un pool de evaluación negativo:

1. **Split de Datos:** Para cada usuario de prueba, reservamos sus últimas canciones como **Ground Truth** y el resto como historial.
2. **Generación del Pool:** Por cada ítem positivo, añadimos **500 ítems negativos** (canciones con las que el usuario nunca interactuó) seleccionados aleatoriamente.
3. **Tarea de Ranking:** El modelo debe puntuar estos 501 ítems. Medimos en qué posición queda el ítem positivo real.

### Métricas Utilizadas (Top-K = 10)
- **Hit Rate@10 (HR):** ¿Está la canción real entre las 10 recomendadas?
- **NDCG@10:** Mide la calidad del ranking, penalizando si la canción real está en posiciones bajas.
- **MRR@10:** Media del recíproco del ranking de la primera canción relevante.
- **Novelty:** Mide cuánto se aleja el modelo de las canciones extremadamente populares (evitando el sesgo de popularidad).
- **Serendipity:** Capacidad del sistema para sorprender al usuario con algo relevante pero acústicamente distinto a sus semillas.
- **Catalog Coverage:** Porcentaje de canciones del catálogo total (1.2M) que el sistema es capaz de recomendar.

---

## Optimización para Producción (ONNX)

Entrenar en PyTorch es ideal, pero la inferencia en producción requiere baja latencia y eficiencia.

### Exportación a ONNX (`export_to_onnx.py`)
Transformamos el modelo `.pth` al estándar **ONNX** para desacoplarlo del framework de entrenamiento:
- **Constant Folding:** Optimiza el grafo de la red eliminando operaciones constantes.
- **Dynamic Axes:** Permite procesar batches de tamaño variable en una sola llamada de inferencia.
- **Inferencia en Producción:** Utilizamos **ONNX Runtime** en el backend. Esto reduce la latencia de inferencia en un ~30-40% y elimina los problemas de bloqueo del GIL (Global Interpreter Lock) de Python al ejecutar el grafo de la red en C++.

---

## Dashboard de Auditoría (`dashboard.py`)

Implementado en **Streamlit**, este panel permite a los ingenieros de ML:
- Comparar visualmente las métricas HR vs NDCG entre los tres modelos.
- Realizar auditorías individuales: seleccionar un usuario y ver qué canciones recomendó cada modelo y si acertó con el Ground Truth.
- Analizar la cobertura del catálogo para evitar el estancamiento en "burbujas de filtro".
