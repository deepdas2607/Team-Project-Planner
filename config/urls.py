"""
URL configuration for config project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.http import JsonResponse
from django.urls import include, path


def home(_request):
    # simple landing response so opening / in browser is not a 404
    return JsonResponse({'message': 'FactWise API is running', 'api_base': '/api/'})

urlpatterns = [
    # root path returns a quick health-style JSON response
    path('', home, name='home'),
    # default Django admin (not used for JSON persistence but handy during development)
    path('admin/', admin.site.urls),
    # mount the factwise JSON API under /api/
    path('api/', include('factwise.urls')),
]
