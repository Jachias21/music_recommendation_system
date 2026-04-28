import streamlit as st
import pandas as pd
from src.modeling.recommendation_engine import get_mongodb_data, create_user_profile, get_contextual_recommendations
from src.process_data import MONGO_URI, DB_NAME, COLLECTION_NAME

# Configuración inicial de la página
st.set_page_config(page_title="Sistema de Recomendación Musical", layout="wide")

# Carga de datos con caché para no consultar MongoDB en cada interacción
@st.cache_data
def load_data():
    df = get_mongodb_data(MONGO_URI, DB_NAME, COLLECTION_NAME)
    # Por defecto 'id' es la columna. Si se llama '_id', homogenizamos para facilitar la búsqueda
    if '_id' in df.columns and 'id' not in df.columns:
        df['id'] = df['_id'].astype(str)
    elif 'id' in df.columns:
        df['id'] = df['id'].astype(str)
    return df

df = load_data()

# ---------------------------------------------------------
# Sección 0: Autenticación (Login / Registro)
# ---------------------------------------------------------
import pymongo
import bcrypt

@st.cache_resource
def get_users_collection():
    client = pymongo.MongoClient(MONGO_URI)
    db = client[DB_NAME]
    return db["users"]

users_col = get_users_collection()

if "user" not in st.session_state:
    st.session_state.user = None

if st.session_state.user is None:
    st.title("🎵 Bienvenido al Sistema de Recomendación Musical")
    st.subheader("Por favor, inicia sesión o regístrate para continuar.")
    
    tab1, tab2 = st.tabs(["Iniciar Sesión", "Registrarse"])
    
    with tab1:
        with st.form("login_form"):
            login_email = st.text_input("Correo electrónico")
            login_password = st.text_input("Contraseña", type="password")
            submit_login = st.form_submit_button("Entrar")
            
            if submit_login:
                user = users_col.find_one({"email": login_email})
                if user and bcrypt.checkpw(login_password.encode('utf-8'), user["password_hash"].encode('utf-8')):
                    st.session_state.user = {"name": user["name"], "email": user["email"]}
                    st.success(f"¡Bienvenido de nuevo, {user['name']}!")
                    st.rerun()
                else:
                    st.error("Correo o contraseña incorrectos.")
                    
    with tab2:
        with st.form("register_form"):
            reg_name = st.text_input("Nombre")
            reg_email = st.text_input("Correo electrónico")
            reg_password = st.text_input("Contraseña", type="password")
            submit_register = st.form_submit_button("Crear Cuenta")
            
            if submit_register:
                if users_col.find_one({"email": reg_email}):
                    st.error("Ya existe una cuenta con este correo.")
                elif len(reg_password) < 6:
                    st.error("La contraseña debe tener al menos 6 caracteres.")
                else:
                    hashed_pw = bcrypt.hashpw(reg_password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
                    new_user = {
                        "name": reg_name,
                        "email": reg_email,
                        "password_hash": hashed_pw,
                        "onboarding_complete": False,
                        "seed_song_ids": []
                    }
                    users_col.insert_one(new_user)
                    st.success("Cuenta creada exitosamente. ¡Ya puedes iniciar sesión!")
                    
    st.stop() # Detener la ejecución del resto de la app hasta que inicie sesión

# Si hay usuario, mostramos el botón de cerrar sesión en la barra lateral
st.sidebar.markdown(f"👤 **Usuario:** {st.session_state.user['name']}")
if st.sidebar.button("Cerrar Sesión"):
    st.session_state.user = None
    st.rerun()
st.sidebar.markdown("---")

# ---------------------------------------------------------
# Sección 1: Cabecera
# ---------------------------------------------------------
st.title("🎵 Generador de Playlists Contextuales")
st.markdown("Descubre nueva música basada en tu ADN musical y la emoción que estés buscando.")

# ---------------------------------------------------------
# Sección 2: Onboarding (Perfil de Usuario)
# ---------------------------------------------------------

# 1. Gestión de Estado (Session State)
if "selected_songs" not in st.session_state:
    st.session_state.selected_songs = []

st.sidebar.header("1. Selecciona tu base musical (3 canciones)")

# 2. Componente de Búsqueda (Panel Lateral)
search_query = st.sidebar.text_input("Busca una canción o artista:")

if len(search_query) >= 2:
    search_terms = search_query.lower().split()
    mask = pd.Series([True]*len(df), index=df.index)
    for term in search_terms:
        mask = mask & (
            df['name'].str.lower().str.contains(term, regex=False, na=False) | 
            df['artist'].str.lower().str.contains(term, regex=False, na=False)
        )
    
    filtered_df = df[mask]
    
    # Limitar a máximo 10 resultados
    results = filtered_df.head(10)
    
    st.sidebar.markdown("### Resultados:")
    if results.empty:
        st.sidebar.info("No se encontraron coincidencias.")
    else:
        # 3. Visualización de Resultados y Selección
        for idx, row in results.iterrows():
            col1, col2 = st.sidebar.columns([3, 1])
            with col1:
                st.markdown(f"**{row['name']}** - *{row['artist']}*")
            with col2:
                # Botón de añadir con clave única basada en el ID
                song_id = row['id']
                if st.button("Añadir", key=f"add_{song_id}"):
                    # Comprobar si ya existe
                    is_duplicate = any(s['track_id'] == song_id for s in st.session_state.selected_songs)
                    
                    if is_duplicate:
                        st.sidebar.warning("Ya añadida")
                    elif len(st.session_state.selected_songs) < 3:
                        # Añadir canción a la lista
                        st.session_state.selected_songs.append({
                            'track_id': song_id,
                            'name': row['name'],
                            'artist': row['artist']
                        })
                        st.rerun()  # Recargar la interfaz
                    else:
                        st.sidebar.error("Límite de 3 canciones")
elif len(search_query) > 0:
    st.sidebar.caption("Introduce al menos 2 caracteres...")

st.sidebar.markdown("---")

# 4. Interfaz del "Carrito" de Canciones
st.sidebar.subheader("Tu Selección (Carrito)")

if len(st.session_state.selected_songs) == 0:
    st.sidebar.info("Aún no has seleccionado ninguna canción.")
else:
    for i, song in enumerate(st.session_state.selected_songs):
        col_c1, col_c2 = st.sidebar.columns([4, 1])
        with col_c1:
            st.markdown(f"{i+1}. **{song['name']}** - {song['artist']}")
        with col_c2:
            # Botón con icono para quitar
            if st.button("🗑️", key=f"remove_{song['track_id']}_{i}"):
                st.session_state.selected_songs.pop(i)
                st.rerun()  # Recargar para actualizar el estado

# Progreso visual
st.sidebar.progress(len(st.session_state.selected_songs) / 3.0)

# ---------------------------------------------------------
# Sección 3: Panel Central (Contexto y Generación)
# ---------------------------------------------------------

st.header("2. Elige tu contexto emocional")

# Extraer emociones disponibles si la columna existe (o fallback)
emotion_col = "emocion" if "emocion" in df.columns else "emotion"
if emotion_col in df.columns:
    available_emotions = df[emotion_col].dropna().unique().tolist()
else:
    available_emotions = ["Energetic", "Happy", "Sad", "Calm", "Aggressive", "Romantic"]

target_emotion = st.selectbox(
    "¿Qué tipo de música buscas hoy?",
    options=available_emotions
)

# 5. Bloqueo de la Generación
is_ready = len(st.session_state.selected_songs) == 3

if not is_ready:
    st.warning(f"⚠️ Necesitas seleccionar exactamente 3 canciones en la barra lateral para continuar. Tienes {len(st.session_state.selected_songs)}/3.")

# El botón principal deshabilitado si no están las 3 canciones
if st.button("Generar Playlist Contextual", disabled=not is_ready, type="primary"):
    with st.spinner("Analizando tu perfil y buscando el contexto perfecto..."):
        # Extraer los IDs de las 3 canciones seleccionadas
        selected_ids = [s['track_id'] for s in st.session_state.selected_songs]
        
        # Llamar al motor de recomendaciones
        # Fase A: Crear Perfil Centroide
        user_vector = create_user_profile(selected_ids, df)
        
        # Fase B: Recomendar en base al vector y contexto emocional
        recommendations = get_contextual_recommendations(
            user_vector=user_vector,
            target_emotion=target_emotion,
            dataframe_base=df,
            top_n=10
        )
        
        st.success("¡Playlist generada con éxito!")
        
        # Mostrar las recomendaciones de forma atractiva
        if recommendations:
            st.subheader(f"Tus recomendaciones para '{target_emotion}':")
            for idx, rec in enumerate(recommendations, 1):
                col_r1, col_r2 = st.columns([1, 4])
                with col_r1:
                    score = float(rec['similarity_score']) * 100
                    st.metric("Afinidad", f"{score:.1f}%")
                with col_r2:
                    st.markdown(f"**{rec['name']}**")
                    st.caption(f"Artista: {rec['artist']}")
                st.markdown("---")
        else:
            st.error("No encontramos suficientes canciones que encajen con esta emoción. Prueba con otra o cambia tu base rítmica.")
