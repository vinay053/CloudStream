from django.urls import path
from . import views

urlpatterns = [
    # Core
    path('', views.home_view, name='home'),
    path('/Dashboard',views.Dashboard,name='dashboard'),
    path('get-upload-url/', views.get_upload_url, name='get_upload_url'),
    path('watch/<str:video_id>/', views.watch_video, name='watch_video'),
    path('api/subscribe/', views.subscribe_view, name='subscribe'),
    path('api/reaction/', views.reaction_view, name='reaction'),
]