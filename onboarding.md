# 🚀 Onboarding: SoundWave (Rama "marcos")

Esta guía explica paso a paso cómo arrancar el proyecto desde cero tras haber hecho un `pull` o clonado la rama `marcos`. 

El proyecto consta de 3 piezas principales:
1. **Base de Datos** (MongoDB en Docker)
2. **Backend / Modelo Recomendador** (FastAPI + Python)
3. **Frontend** (Angular)

---

## 📦 1. Levantar la Base de Datos (MongoDB)

El sistema utiliza MongoDB para almacenar usuarios y las canciones procesadas.

1. Asegúrate de tener **Docker** y **Docker Desktop** instalado y abierto.
2. En la raíz del proyecto, ejecuta el siguiente comando para levantar el contenedor:
   ```bash
   docker-compose up -d
   ```
   *Esto iniciará MongoDB en el puerto `27018` en segundo plano.*

---

## ⚙️ 2. Configurar el Backend (Python / FastAPI)

1. **Crear entorno virtual e instalar dependencias:**
   ```bash
   # Crear entorno virtual (en Windows)
   python -m venv venv
   
   # Activar el entorno
   .\venv\Scripts\activate
   
   # (En Mac/Linux: source venv/bin/activate)
   
   # Instalar dependencias (requiere tener pip instalado)
   pip install -r requirements.txt
   ```

2. **Variables de entorno (`.env`):**
   Asegúrate de crear un archivo `.env` en la raíz del proyecto con la siguiente estructura (rellenando las credenciales de Spotify):
   ```env
   SPOTIFY_CLIENT_ID=tu_client_id_aqui
   SPOTIFY_CLIENT_SECRET=tu_client_secret_aqui
   MONGO_URI=mongodb://admin:admin123@127.0.0.1:27018/
   JWT_SECRET=un_secreto_super_seguro_para_tokens
   ```

3. **Carga de Datos Inicial (Si la BD está vacía):**
   Si es tu primera vez, necesitas tener el CSV de canciones (dataset) y ejecutar el script que puebla MongoDB:
   *(Asegúrate de que la ruta al CSV dentro del script apunte al lugar correcto).*
   ```bash
   python src/process_data.py
   ```

4. **Entrenar el Modelo (Node2Vec):**
   Para que la serendipia y la diversidad funcionen, el modelo de grafos KNN/Node2Vec debe ejecutarse y generar su caché inicial (`node2vec.cache`).
   ```bash
   python src/modeling/node2vec_engine.py
   ```

5. **Levantar la API (FastAPI):**
   Una vez poblado todo, arranca el servidor backend:
   ```bash
   uvicorn api:app --port 8000
   ```
   *(El backend quedará escuchando en `http://127.0.0.1:8000`)*

---

## 🎨 3. Levantar el Frontend (Angular)

1. Abre una **nueva terminal** (manteniendo la del backend abierta).
2. Navega a la carpeta del frontend:
   ```bash
   cd frontend
   ```
3. Instala las dependencias de Node:
   ```bash
   npm install
   ```
4. Levanta el servidor de desarrollo de Angular:
   ```bash
   npm start
   # o bien: ng serve
   ```
5. Accede a la aplicación abriendo en tu navegador:
   👉 **`http://localhost:4200`**

---

## 🧪 4. Qué probar y comprobar (Checklist)

Una vez dentro de la app, deberías poder probar todo lo implementado en esta rama:
- [x] **Login/Registro Nativo:** Crear un usuario con email y contraseña.
- [x] **Login Social:** Iniciar sesión directamente con Spotify o Google.
- [x] **Flujo de Onboarding:** Al entrar por primera vez, el sistema te pedirá elegir 3 canciones "semilla".
- [x] **Ajustes Dinámicos:** Ve a *Ajustes*, modifica los sliders (Serendipia, Instrumentalidad, Diversidad). No necesitas darle a "Aplicar", se **autoguardan**.
- [x] **Generador Node2Vec:** Genera una playlist en *Inicio*. Observa cómo la afinidad (porcentaje) cambia, y cómo una *Serendipia* al 100% lanza resultados muy variados preservando la lógica del grafo.
- [x] **Exportación a Spotify:** Desde "Mi Playlist", haz clic en *Exportar a Spotify* y verifica en tu app real de Spotify que la lista de reproducción aparece con las canciones exactas.
