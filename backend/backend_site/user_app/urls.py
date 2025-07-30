from django.urls import path
from .views import * 

urlpatterns = [
    # POST register
    path('register/', RegisterView.as_view(), name='register'),
    # POST login
    path('login/', LoginView.as_view(), name='login'),
    # GET logout
    path('logout/', LogoutView.as_view(), name='logout'),

    # GET, DELETE user profile
    path('me/', ProfileView.as_view(), name='profile'),
    path('me/edit/', ProfileEditView.as_view(), name='edit'),
]   