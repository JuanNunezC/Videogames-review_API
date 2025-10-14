from django.urls import path
from .views import random_number, get_igdb_access_token_view, search_games

urlpatterns = [
    path("random/", random_number),
    path("igdb-token/", get_igdb_access_token_view),
    path("search-games/", search_games),
]