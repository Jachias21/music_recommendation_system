# Sistema de Recomendación Musical

Bienvenido al portal oficial de la documentación técnica del proyecto.

Este sistema está dividido modularmente en un pipeline de datos, un motor de recomendación, un backend API y un frontend. A continuación, puedes consultar el índice general para navegar directamente a la documentación de interés:

### 🧩 Módulos del Sistema

* **[Extracción de Datos](ingest_data_documentation.md)**: Documentación sobre el script inicial (`src/ingest_data.py`), explicando cómo actúa de capa Bronze descargando, vectorizando masivamente y clasificando emociones desde 1.2M de canciones.
* **[Carga y Procesamiento](process_data_documentation.md)**: Documentación de `src/process_data.py`, enfocada en cómo se estructuran y cargan las pistas limpias directo a nuestra Base de Datos (MongoDB).
* **[Motor de Recomendación](recommendator_engine.md)**: La lógica algorítmica y el funcionamiento tras el perfilado de usuarios basados en su ADN Musical usando similitud coseno de Scikit-learn.
* **[Frontend y Arquitectura (App)](app_documentation.md)**: Toda la arquitectura explicada sobre nuestra interfaz final en Angular 21 y la conexión con FastAPI.

---
<small>¿Problemas técnicos levantando este sitio web? Consulta nuestra sección de **[Ayuda de MkDocs](help-mkdocs.md)** para listar los comandos básicos de ejecución.</small>
