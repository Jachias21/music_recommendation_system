# Manual del Usuario — SoundWave

¡Bienvenido a **SoundWave**! Tu nuevo compañero musical que no solo entiende tus gustos, sino también tus emociones. Este manual te guiará para que saques el máximo provecho de la plataforma.

---

## 1. Inicio de Sesión y Perfil

Para comenzar a usar SoundWave, tienes dos opciones principales:

### A. Autenticación con Spotify (Recomendado)
Haz clic en el botón **"Login con Spotify"**. Esto permitirá que SoundWave:
- Acceda a tus artistas y canciones favoritas.
- Sincronice tus playlists.
- Te ofrezca recomendaciones basadas en tu historial real de escucha.
*Nota: Asegúrate de usar `http://127.0.0.1:4200` en tu navegador para que la conexión sea segura.*

### B. Registro Local
Si prefieres no conectar tu cuenta de Spotify, puedes crear un perfil local con tu email y contraseña. Tus preferencias se guardarán directamente en nuestra base de datos.

---

## 2. Explorando la Música

### Buscador Inteligente
En la barra superior encontrarás un buscador. Puedes buscar por:
- **Canción**: Encuentra ese tema que no te sacas de la cabeza.
- **Artista**: Explora la discografía completa de tus músicos favoritos.
- **Álbum**: Descubre joyas ocultas en discos específicos.

### Filtros por Emoción
SoundWave clasifica automáticamente más de 1.2 millones de canciones en cuatro estados de ánimo:
- **Enérgico**: Ideal para entrenar o cuando necesitas un empujón de adrenalina.
- **Alegre**: Canciones con buen ritmo y vibras positivas.
- **Triste**: Temas melancólicos y acústicos para momentos de reflexión.
- **Neutro**: Música equilibrada, ideal para concentrarse o de fondo.

---

## 3. Sistema de Recomendaciones

Nuestra IA trabaja en segundo plano para ofrecerte tres tipos de descubrimientos:

1.  **"Porque te gusta..."**: Basado en la similitud acústica. Si te gusta una canción con mucha guitarra y ritmo rápido, te sugeriremos otras con características técnicas similares.
2.  **Descubrimiento Semanal (NCF)**: Una red neuronal profunda que aprende de los patrones de miles de usuarios para predecir qué canción será tu próxima favorita, incluso si es de un género que no sueles escuchar.
3.  **Exploración de Comunidades (Node2Vec)**: Te sugerimos música que pertenece a tu mismo "ecosistema musical", conectando artistas y estilos de forma inteligente.

---

## 4. El Reproductor y Controles

Cuando seleccionas una canción, verás el reproductor en la parte inferior:
- **Play/Pausa**: Control total de la reproducción.
- **Barra de Progreso**: Salta a cualquier parte de la canción.
- **Volumen**: Ajusta el sonido a tu gusto.
- **Información de Audio**: Haz clic en el icono de información para ver los detalles técnicos (energía, valencia, tempo) que nuestra IA usó para clasificar la canción.

---

## 5. Preguntas Frecuentes (FAQ)

**¿Por qué no puedo escuchar algunas canciones completas?**
SoundWave utiliza las vistas previas oficiales de Spotify. Para escuchar la canción completa, encontrarás un enlace directo para abrirla en tu aplicación de Spotify.

**¿Cómo cambio mi estado de ánimo?**
En la sección "Explorar", puedes seleccionar directamente la emoción que sientes en ese momento y la lista de canciones se actualizará instantáneamente.

**¿Mis datos están seguros?**
Sí. Si usas Spotify, no guardamos tu contraseña. Si usas el registro local, tus datos están cifrados en nuestra base de datos privada.

---
*SoundWave — La música que sientes.*
