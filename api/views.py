import random
import requests
import os
import json
from datetime import timedelta

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_protect, ensure_csrf_cookie
from firebase_admin import auth
import firebase_config
from igdb_token import get_igdb_access_token


def random_number(request):
    number = random.randint(1, 100)
    return JsonResponse({"random": number})

def get_igdb_access_token_view(request):
    token = get_igdb_access_token()
    return JsonResponse({"access_token" : token})
    
def search_games(request):
    query = request.GET.get('query', '')
    if not query:
        return JsonResponse({'error': 'No query provided'}, status=400)

    access_token = get_igdb_access_token()
    client_id = os.getenv('IGDB_CLIENT_ID')

    url = 'https://api.igdb.com/v4/games'
    headers = {
        'Client-ID': client_id,
        'Authorization': f'Bearer {access_token}',
        'Accept': 'application/json',
        'Content-Type': 'text/plain',
    }
    body = f'search "{query}"; fields id, name, cover.image_id;'

    response = requests.post(url, headers=headers, data=body)
    if response.status_code != 200:
        return JsonResponse({'error': 'IGDB API error', 'details': response.text}, status=response.status_code)

    raw = response.json()
    # Build cover_url from image_id using IGDB image CDN. Fallback to None if missing
    results = []
    for games in raw:
        cover_url = None
        cover = games.get('cover')
        image_id = None
        if isinstance(cover, dict):
            image_id = cover.get('image_id')
        # Build a medium/large cover size. Other sizes: t_thumb, t_cover_small, t_cover_big, t_720p, t_1080p
        if image_id:
            cover_url = f"https://images.igdb.com/igdb/image/upload/t_cover_big/{image_id}.jpg"
        results.append({
            'id': games.get('id'),
            'name': games.get('name'),
            'cover_url': cover_url,
        })

    return JsonResponse(results, safe=False)

def get_game_by_id(request, id):
    access_token = get_igdb_access_token()
    client_id = os.getenv('IGDB_CLIENT_ID')

    url = 'https://api.igdb.com/v4/games'
    headers = {
        'Client-ID': client_id,
        'Authorization': f'Bearer {access_token}',
        'Accept': 'application/json',
        'Content-Type': 'text/plain',
    }
    body = f'where id = {id}; fields id, name, cover.image_id; limit 1;'
    response = requests.post(url, headers=headers, data=body)
    if response.status_code != 200:
        return JsonResponse({'error': 'IGDB API error', 'details': response.text}, status=response.status_code)
    
    raw = response.json()

    game = raw[0]
    image_id = game.get('cover', {}).get('image_id') if isinstance(game.get('cover'), dict) else None
    cover_size = 't_cover_big'
    cover_url = f"https://images.igdb.com/igdb/image/upload/{cover_size}/{image_id}.jpg" if image_id else None

    return JsonResponse({
        'id': game.get('id'),
        'name': game.get('name'),
        'cover_url': cover_url,
    })

# Auth Firebase

@ensure_csrf_cookie
def csrf_token(request):
    return JsonResponse({"ok": True})

@csrf_protect
def create_session(request):
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)
    
    try:
        data = json.loads(request.body or "{}")
        id_token = data.get("token")
        if not id_token:
            return JsonResponse({"error": "Missing token"}, status=400)

        decoded_token = auth.verify_id_token(id_token)
        expires_in = timedelta(days=5)
        session_cookie = auth.create_session_cookie(id_token, expires_in=expires_in)

        response = JsonResponse({"ok": True, "uid": decoded_token["uid"]})
        response.set_cookie(
            key="session",
            value=session_cookie,
            max_age=int(expires_in.total_seconds()),
            httponly=True,
            secure= False, # Set to True in production with HTTPS
            samesite="Lax",
            path="/"
        )
        return response
    except Exception:
        return JsonResponse({"error": "Invalid token"},status=401)

@csrf_protect
def logout(request):
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)
    response = JsonResponse({"ok": True})
    response.delete_cookie("session",path="/")
    return response

def require_firebase_auth(view_func):
    def _wrapped(request, *args, **kwargs):
        cookie = request.COOKIES.get("session")
        if not cookie:
            return JsonResponse({"error": "Unauthorized"}, status=401)
        try:
            request.firebase_user = auth.verify_session_cookie(cookie,check_revoked=True)
            return view_func(request, *args, **kwargs)
        except Exception:
            return JsonResponse({"error": "Unauthorized"}, status=401)
    return _wrapped

@require_firebase_auth
def get_profile(request):
    user = getattr(request, "firebase_user", {})
    return JsonResponse({
        "uid": user.get("uid"),
        "email": user.get("email"),
        "name": user.get("name"),
        "picture": user.get("picture"),
    })