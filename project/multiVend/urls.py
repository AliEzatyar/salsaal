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
import debug_toolbar
from django.contrib import admin
from django.urls import include, path
from django.conf.urls.static import static
from django.conf import settings
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

urlpatterns = [
    path("admin/", admin.site.urls),
    path("marketplace/", include("marketplace.urls", namespace="marketplace")),
    path("order/", include("order.urls", namespace="order")),
    path("vendor/", include("vendor.urls", namespace="vendor")),
    path("account/", include("accounts.urls", namespace="accounts")),
    path("shopping-cart/", include("cart.urls", namespace="cart")),
    path("api/", include("api.urls", namespace="api")),
    # OpenAPI schema (raw)
    path("schema/", SpectacularAPIView.as_view(), name="schema"),
    # Swagger UI for easy interactive documentation
    path("docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
    path("", include("main.urls", namespace="home")),
    path("__debug__/", include(debug_toolbar.urls)),
]


# in foodion, NGINX does it, but in debug mode, django should do
if settings.DEBUG and settings.LOCAL:
    print("it is local settings")
    urlpatterns += static(settings.MEDIA_URL,document_root =settings.MEDIA_ROOT)
