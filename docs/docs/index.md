# Sistema de Recomendación Musical

Bienvenido al portal oficial de la documentación técnica del proyecto.

Este sistema está dividido modularmente. A continuación, puedes consultar el índice general para navegar directamente a la documentación de interés:

### 🧩 Módulos del Sistema

* **[Extracción de Datos](ingest_data_documentation.md)**: Documentación sobre el script inicial (`src/ingest_data.py`), explicando cómo actúa de capa Bronze descargando y filtrando masivamente la información.
* **[Carga y Procesamiento](process_data_documentation.md)**: Documentación de `src/process_data.py`, enfocada en cómo se estructuran y cargan las pistas limpias directo a nuestra Base de Datos (MongoDB).
* **[Motor de Recomendación](recommendator_engine.md)**: La lógica algorítmica y el funcionamiento tras el perfilado de usuarios basados en su ADN Musical usando la magnitud de Scikit-learn.
* **[Frontend y UI](app_documentation.md)**: Toda la arquitectura explicada sobre nuestra interfaz final programada sobre el framework de Streamlit (`app.py`).

---
<small>¿Problemas técnicos levantando este sitio web? Consulta nuestra sección de **[Ayuda de MkDocs](help-mkdocs.md)** para listar los comandos básicos de ejecución.</small>
