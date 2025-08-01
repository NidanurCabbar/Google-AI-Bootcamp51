from django.urls import path
from .views import * 

urlpatterns = [
    
    path('get_analyse/', GetAnalyse.as_view(), name='get_analyse')
]   