import requests
from django.http import JsonResponse
import random
from igdb_token import get_igdb_access_token
import os


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
            cover_url = f"https://images.igdb.com/igdb/image/upload/t_thumb/{image_id}.jpg"
        results.append({
            'id': games.get('id'),
            'name': games.get('name'),
            'cover_url': cover_url,
        })

    return JsonResponse(results, safe=False)