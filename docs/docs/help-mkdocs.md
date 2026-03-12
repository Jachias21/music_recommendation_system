# Ayuda y Comandos de MkDocs

Para la documentación completa, puedes visitar alternativamente el sitio oficial en [mkdocs.org](https://www.mkdocs.org).

## Comandos Principales

* `mkdocs new [dir-name]` - Crea un nuevo proyecto desde cero.
* `mkdocs serve` - Levanta el servidor local con recarga en vivo para previsualizar los cambios.
* `mkdocs build` - Construye la documentación estática (HTML/CSS) lista para su despliegue en producción.
* `mkdocs -h` - Imprime el mensaje de ayuda de consola.

## Estructura del Proyecto

Tu documentación debería organizarse bajo este patrón básico:

    mkdocs.yml    # El archivo maestro de configuración del proyecto (Nav, Temas, etc.).
    docs/
        index.md  # La página principal o 'Home' de la documentación.
        ...       # Otras páginas en formato Markdown, imágenes y assets adicionales.
