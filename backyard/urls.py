from django.urls import path
from . import views

urlpatterns = [
    path('storeComments/', views.store_text),
    path('stream/<str:session_id>/', views.Summary),
    path('stream/<str:session_id>/keywords/', views.Keywords),
    path('get_article_data/', views.get_article_data, name='get_article_data'),
    path('signup/', views.signup_view, name='signup'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
]