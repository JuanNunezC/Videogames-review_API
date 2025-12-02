import os
import requests
from dotenv import load_dotenv
from django.core.cache import cache

load_dotenv()

CLIENT_ID = os.getenv('IGDB_CLIENT_ID')
CLIENT_SECRET = os.getenv('IGDB_SECRET_ID')

def get_igdb_access_token():
    # Intentamos obtener el token de la caché(no funciona a la primera) ya que se hace el set despues
    token= cache.get('igdb_access_token')
    #returns the token if exists
    if token:
        return token

    url = 'https://id.twitch.tv/oauth2/token'
    payload = {
        #esto es de acuerdo a la API de Twitch
        # https://dev.twitch.tv/docs/authentication/getting-tokens-oauth/
        'client_id': CLIENT_ID,
        'client_secret': CLIENT_SECRET,
        'grant_type': 'client_credentials'
    }
    response = requests.post(url, data=payload, timeout=5)
    # Raise an exception for HTTP errors
    response.raise_for_status()
    data = response.json()

    token = data['access_token']
    ttl = max(0, int(data.get('expires_in',0)- 60))
    cache.set('igdb_access_token',token,ttl)
    return token

if __name__ == "__main__":
    token = get_igdb_access_token()
    print(f"Access Token: {token}")
