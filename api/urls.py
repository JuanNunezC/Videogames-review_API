from django.urls import path
from .views import( random_number, get_igdb_access_token_view, search_games, get_game_by_id 
,csrf_token,create_session,logout,get_profile
)
urlpatterns = [
    path("random/", random_number),
    path("igdb-token/", get_igdb_access_token_view),
    path("search-games/", search_games),
    path("game/<int:id>/", get_game_by_id), 

    #Auth (Firebase)
    path("auth/session/", create_session),
    path("auth/logout/", logout),
    path("profile/", get_profile),
    path("auth/csrf/", csrf_token),

]