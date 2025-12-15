"""
URL configuration for multiVend project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.0/topics/http/urls/
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
from django.urls import include, path
from accounts.views import jwtks_view
from two_factor.urls import urlpatterns as tf_urls
from two_factor.admin import AdminSiteOTPRequired

admin.site.__class__ = AdminSiteOTPRequired

urlpatterns = [
    path("", include(tf_urls)),
    path("hello-world-3000/", admin.site.urls),
    path("api/", include("api.urls", namespace="api")),
    path("jwtks/", jwtks_view),
]


# # in foodion, NGINX does it, but in debug mode, django should do
# if settings.DEBUG and settings.LOCAL:
#     urlpatterns += static(settings.MEDIA_URL,document_root =settings.MEDIA_ROOT)
