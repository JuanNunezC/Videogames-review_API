import random
import requests
import os
import json
from datetime import timedelta

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_protect, ensure_csrf_cookie
from django.views.decorators.http import require_GET, require_POST
from firebase_admin import auth
import firebase_config
from igdb_token import get_igdb_access_token


def random_number(request):
    number = random.randint(1, 100)
    return JsonResponse({"random": number})

def get_igdb_access_token_view(request):
    token = get_igdb_access_token()
    return JsonResponse({"access_token" : token})

def _igdb_escape(s: str) -> str:
    return s.replace('"', r'\"')
    
def search_games(request):
    query = request.GET.get('query', '').strip()
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

    safe_query = _igdb_escape(query)

    body = f'''
        search "{safe_query}";
        fields id, name, cover.image_id, category, version_parent;
        limit 50;
    '''
    
    response = requests.post(url, headers=headers, data=body)
    if response.status_code != 200:
        return JsonResponse({'error': 'IGDB API error', 'details': response.text}, status=response.status_code)
    
    raw = response.json() or []

    # Coincidencia exacta (si existe) -> devolver solo un juego
    exact_matches = [game for game in raw if (game.get('name') 
    or '').lower() == query.lower()]

    if exact_matches:
        # Prioriza juego principal (category 0 / sin version_parent)
        main = [game for game in exact_matches if game.get('category') in (0, None) and not game.get('version_parent')] or exact_matches
        selected = sorted(main, key=lambda x: len(x.get('name') or ''))[:3]

        results = []
        for game in selected:
            cover = game.get('cover')
            image_id = cover.get('image_id') if isinstance(cover, dict) else None
            cover_url = f"https://images.igdb.com/igdb/image/upload/t_cover_big/{image_id}.jpg" if image_id else None
            results.append({
                'id': game.get('id'),
                'name': game.get('name'),
                'cover_url': cover_url,
            })
        return JsonResponse(results, safe=False)
    
    # Sin nombre exacto: ordenar por menor longitud y luego alfabeticamente
    results = []
    for games in raw:
        cover_url = None
        cover = games.get('cover')
        image_id = cover.get('image_id') if isinstance(cover, dict) else None
        # Build a medium/large cover size. Other sizes: t_thumb, t_cover_small, t_cover_big, t_720p, t_1080p
        if image_id:
            cover_url = f"https://images.igdb.com/igdb/image/upload/t_cover_big/{image_id}.jpg"
        results.append({
            'id': games.get('id'),
            'name': games.get('name'),
            'cover_url': cover_url,
        })
    results.sort(key=lambda x: (len(x['name']), x['name'].lower()))
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
@require_GET
def csrf_token(request):
    return JsonResponse({"ok": True})

@csrf_protect
@require_POST
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
            secure= True, # Set to True in production with HTTPS
            samesite="None",
            path="/"
        )
        return response
    except Exception:
        return JsonResponse({"error": "Invalid token"},status=401)

@csrf_protect
@require_POST
def logout(request):
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)
    response = JsonResponse({"ok": True})
    response.delete_cookie("session")
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

def get_profile(request):
    cookie = request.COOKIES.get("session")
    if not cookie:
        response = JsonResponse({"authenticated": False}, status=200)
        response["Cache-Control"] = "no-store"
        return response

    # Verify session cookie using Firebase Admin SDK
    try:
        user = auth.verify_session_cookie(cookie, check_revoked=True)
    except Exception:
        response = JsonResponse({"authenticated": False}, status=200)
        response["Cache-Control"] = "no-store"
        return response

    uid = user.get("uid")
    email = user.get("email")
    name = user.get("name")
    picture = user.get("picture")

    response = JsonResponse({
        "authenticated": True,
        "uid": uid,
        "email": email,
        "name": name,
        "picture": picture,
    })
    response["Cache-Control"] = "no-store"
    return response