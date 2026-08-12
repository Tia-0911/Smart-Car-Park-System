"""
URL configuration for monolish project.

The `urlpatterns` list routes URLs to views.
"""

from django.contrib import admin
from django.urls import path, include
from django.contrib.auth import views as auth_views
from back1.views import RoleAwareLoginView


urlpatterns = [
    path('admin/', admin.site.urls),

    path(
        'login/',
        RoleAwareLoginView.as_view(),
        name='login'
    ),

    path(
        'logout/',
        auth_views.LogoutView.as_view(),
        name='logout'
    ),

    path('', include('back1.urls')),
]
