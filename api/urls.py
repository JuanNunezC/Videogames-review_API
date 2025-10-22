from django.urls import path
from .views import random_number, get_igdb_access_token_view, search_games, get_game_by_id

urlpatterns = [
    path("random/", random_number),
    path("igdb-token/", get_igdb_access_token_view),
    path("search-games/", search_games),
    path("game/<int:id>/", get_game_by_id), 
]