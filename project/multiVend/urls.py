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
from admins.admin import revenue_admin_site
from two_factor.admin import AdminSiteOTPRequired

# Apply OTP requirement to the default admin site
admin.site.__class__ = AdminSiteOTPRequired

# Add revenue analytics URLs to the default admin site
from django.urls import path
from django.shortcuts import render
from django.contrib.auth.decorators import user_passes_test
from django.http import JsonResponse
from django.db.models import Sum, Count
from django.utils import timezone
from datetime import timedelta
from order.models import Order
from vendor.models import Vendor

def is_order_manager(user):
    """Check if user is an order manager or superuser"""
    return user.groups.filter(name='Order Manager').exists() or user.is_superuser

@user_passes_test(is_order_manager)
def revenue_analytics_view(request):
    """Main analytics dashboard view"""
    context = {
        **admin.site.each_context(request),
        'title': 'Revenue Analytics',
        'vendors': Vendor.objects.all().order_by('vendor_name'),
    }
    return render(request, 'admin/admins/revenue_analytics.html', context)

@user_passes_test(is_order_manager)
def revenue_data_api_view(request):
    """API endpoint for revenue data"""
    period = request.GET.get('period', 'month')
    vendor_id = request.GET.get('vendor_id')
    chart_type = request.GET.get('chart_type', 'vendor_revenue')

    now = timezone.now()

    if chart_type == 'trends':
        # Get revenue trends over time
        if period == 'day':
            start_date = now - timedelta(hours=24)
            time_points = [start_date + timedelta(hours=i) for i in range(24)]
            date_format = '%H:%M'
        elif period == 'week':
            start_date = now - timedelta(days=7)
            time_points = [start_date + timedelta(days=i) for i in range(7)]
            date_format = '%m-%d'
        else:  # month
            start_date = now - timedelta(days=30)
            time_points = [start_date + timedelta(days=i) for i in range(30)]
            date_format = '%m-%d'

        labels = []
        revenue_data = []

        for time_point in time_points:
            if period == 'day':
                start_range = time_point
                end_range = time_point + timedelta(hours=1)
            else:
                start_range = time_point.replace(hour=0, minute=0, second=0, microsecond=0)
                end_range = time_point.replace(hour=23, minute=59, second=59, microsecond=999999)

            orders = Order.objects.filter(
                status='delivered',
                created_at__range=(start_range, end_range)
            )
            if vendor_id:
                orders = orders.filter(vendor_id=vendor_id)

            total = orders.aggregate(total=Sum('total_price'))['total'] or 0
            labels.append(time_point.strftime(date_format))
            revenue_data.append(float(total))

        return JsonResponse({
            'labels': labels,
            'revenue_data': revenue_data,
            'period': period
        })
    else:
        # Get revenue data aggregated by vendor
        if period == 'day':
            start_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
        elif period == 'week':
            start_date = now - timedelta(days=now.weekday())
            start_date = start_date.replace(hour=0, minute=0, second=0, microsecond=0)
        else:  # month
            start_date = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

        end_date = now

        orders = Order.objects.filter(
            status='delivered',
            created_at__range=(start_date, end_date)
        )

        if vendor_id:
            orders = orders.filter(vendor_id=vendor_id)

        vendor_revenue = orders.values('vendor__vendor_name').annotate(
            total_revenue=Sum('total_price'),
            order_count=Count('id')
        ).order_by('-total_revenue')

        labels = [item['vendor__vendor_name'] or 'Unknown' for item in vendor_revenue]
        revenue_data = [float(item['total_revenue'] or 0) for item in vendor_revenue]
        order_data = [item['order_count'] for item in vendor_revenue]

        return JsonResponse({
            'labels': labels,
            'revenue_data': revenue_data,
            'order_data': order_data,
            'period': period,
            'total_revenue': sum(revenue_data),
            'total_orders': sum(order_data)
        })

urlpatterns = [
    path("", include(tf_urls)),
    path("hello-world-3000/", revenue_admin_site.urls),
    path("api/", include("api.urls", namespace="api")),
    path("jwtks/", jwtks_view),
]


# # in foodion, NGINX does it, but in debug mode, django should do
# if settings.DEBUG and settings.LOCAL:
#     urlpatterns += static(settings.MEDIA_URL,document_root =settings.MEDIA_ROOT)
