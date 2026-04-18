import os
import requests
import base64
from dotenv import load_dotenv

# 1. Cargar credenciales
base_dir = os.path.dirname(os.path.dirname(__file__))
load_dotenv(os.path.join(base_dir, ".env"))

client_id = os.getenv("SPOTIFY_CLIENT_ID")
client_secret = os.getenv("SPOTIFY_CLIENT_SECRET")

print("⏳ Pidiendo permiso al servidor de Spotify...")

# 2. Generar el App Token manualmente
auth_str = f"{client_id}:{client_secret}"
b64_auth_str = base64.b64encode(auth_str.encode()).decode()

headers = {
    "Authorization": f"Basic {b64_auth_str}",
    "Content-Type": "application/x-www-form-urlencoded"
}
data = {"grant_type": "client_credentials"}

token_response = requests.post("https://accounts.spotify.com/api/token", headers=headers, data=data)

if token_response.status_code != 200:
    print("❌ Error al iniciar sesión en Spotify:")
    print(token_response.json())
    exit()

token = token_response.json()["access_token"]
print("✅ Token generado correctamente. Intentando leer una canción...\n")

# 3. Hacer la petición a la API pura y dura (Track ID: Testify - Rage Against The Machine)
track_id = "7lmeHLHBe4nmXzuXc0HDjk"
headers_api = {"Authorization": f"Bearer {token}"}
api_response = requests.get(f"https://api.spotify.com/v1/tracks/{track_id}", headers=headers_api)

# 4. Mostrar la verdad desnuda
print("================ RESPUESTA DE SPOTIFY ================")
print(f"Código HTTP: {api_response.status_code}")
print("Mensaje de Error Oficial:")
print(api_response.json())
print("======================================================")