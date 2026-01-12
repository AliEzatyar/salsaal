from django.contrib import admin
from django_otp.plugins.otp_totp.models import TOTPDevice
from django.urls import path
from django.shortcuts import render
from django.http import JsonResponse
from django.db.models import Sum, Count, F, Q
from django.utils import timezone
from datetime import timedelta
from order.models import Order
from vendor.models import Vendor
from django.contrib import messages
from multiVend.country.info import PLATFORM_SHARE


def is_order_manager(user):
    """Check if user is an order manager or superuser"""
    return user.groups.filter(name='Order Manager').exists() or user.is_superadmin


@admin.register(TOTPDevice)
class TOTPDeviceAdmin(admin.ModelAdmin):
    list_display = ("name", "user", "confirmed", "last_used")
    list_filter = ("confirmed",)
    search_fields = ("user__username", "name")

    # Optional: define a method if you want to show last TOTP usage
    def last_used(self, obj):
        # This returns the last login time via this device if available
        return getattr(obj, "last_t", None)  # adjust according to your model

    last_used.short_description = "Last TOTP"


class RevenueAnalyticsAdminSite(admin.AdminSite):
    """Custom admin site with revenue analytics"""

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('revenue-analytics/', self.admin_view(self.revenue_analytics_view), name='revenue_analytics'),
            path('api/revenue-data/', self.admin_view(self.revenue_data_api), name='revenue_data_api'),
        ]
        return custom_urls + urls

    def revenue_analytics_view(self, request):
        """Main analytics dashboard view"""
        # Check if user is order manager
        if not is_order_manager(request.user):
            from django.http import HttpResponseForbidden
            return HttpResponseForbidden("You don't have permission to access this page.")
        
        context = {
            **self.each_context(request),
            'title': 'Revenue Analytics',
            'vendors': Vendor.objects.all().order_by('vendor_name'),
        }
        return render(request, 'admin/admins/revenue_analytics.html', context)

    def revenue_data_api(self, request):
        """API endpoint for revenue data"""
        try:
            # Check if user is order manager
            # Temporarily disabled for debugging
            # if not is_order_manager(request.user):
            #     from django.http import HttpResponseForbidden
            #     return HttpResponseForbidden("You don't have permission to access this page.")

            period = request.GET.get('period', 'month')
            vendor_id = request.GET.get('vendor_id')
            chart_type = request.GET.get('chart_type', 'vendor_revenue')
            start_date = request.GET.get('start_date')
            end_date = request.GET.get('end_date')

            # Validate period
            if period not in ['day', 'week', 'month', 'custom']:
                return JsonResponse({'error': 'Invalid period. Must be day, week, month, or custom.'}, status=400)

            # Validate chart_type
            valid_chart_types = ['vendor_revenue', 'trends', 'status', 'payment', 'hourly', 'order_value', 'vendor_performance']
            if chart_type not in valid_chart_types:
                return JsonResponse({'error': f'Invalid chart_type. Must be one of: {", ".join(valid_chart_types)}'}, status=400)

            # Validate vendor_id if provided
            if vendor_id and vendor_id != '':
                try:
                    vendor_id = int(vendor_id)
                    if not Vendor.objects.filter(id=vendor_id).exists():
                        return JsonResponse({'error': 'Vendor not found.'}, status=404)
                except (ValueError, TypeError):
                    return JsonResponse({'error': 'Invalid vendor_id. Must be a number.'}, status=400)
            else:
                vendor_id = None

            # Validate custom date range
            if period == 'custom':
                if not start_date or not end_date:
                    return JsonResponse({'error': 'start_date and end_date are required for custom period.'}, status=400)
                try:
                    start_date = timezone.datetime.fromisoformat(start_date).replace(tzinfo=timezone.get_current_timezone())
                    end_date = timezone.datetime.fromisoformat(end_date).replace(tzinfo=timezone.get_current_timezone())
                    if start_date > end_date:
                        return JsonResponse({'error': 'start_date cannot be after end_date.'}, status=400)
                except ValueError:
                    return JsonResponse({'error': 'Invalid date format. Use YYYY-MM-DD.'}, status=400)
            else:
                start_date = None
                end_date = None

            now = timezone.now()

            if chart_type == 'trends':
                return self._get_trends_data(period, vendor_id, now, start_date, end_date)
            elif chart_type == 'status':
                return self._get_status_distribution(period, vendor_id, now, start_date, end_date)
            elif chart_type == 'payment':
                return self._get_payment_method_analysis(period, vendor_id, now, start_date, end_date)
            elif chart_type == 'hourly':
                return self._get_hourly_distribution(period, vendor_id, now, start_date, end_date)
            elif chart_type == 'order_value':
                return self._get_order_value_distribution(period, vendor_id, now, start_date, end_date)
            elif chart_type == 'vendor_performance':
                return self._get_vendor_performance(period, vendor_id, now, start_date, end_date)
            else:
                return self._get_vendor_revenue_data(period, vendor_id, now, start_date, end_date)

        except Exception as e:
            # Log the error for debugging
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error in revenue_data_api: {str(e)}", exc_info=True)
            return JsonResponse({'error': 'An internal server error occurred.'}, status=500)

    def _get_vendor_revenue_data(self, period, vendor_id, now, start_date=None, end_date=None):
        """Get revenue data aggregated by vendor"""
        try:
            if period == 'custom' and start_date and end_date:
                # Use custom date range
                start_date = start_date
                end_date = end_date
            else:
                # Use preset periods
                if period == 'day':
                    start_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
                elif period == 'week':
                    start_date = now - timedelta(days=now.weekday())
                    start_date = start_date.replace(hour=0, minute=0, second=0, microsecond=0)
                else:  # month
                    start_date = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
                end_date = now

            # Filter orders
            orders = Order.objects.filter(
                status='delivered',
                created_at__range=(start_date, end_date)
            )

            if vendor_id:
                orders = orders.filter(vendor_id=vendor_id)

            # Aggregate by vendor
            vendor_revenue = orders.values('vendor__vendor_name').annotate(
                total_revenue=Sum('total_price'),
                order_count=Count('id')
            ).order_by('-total_revenue')

            # Apply platform share to revenue and handle empty results
            labels = []
            revenue_data = []
            order_data = []

            for item in vendor_revenue:
                vendor_name = item['vendor__vendor_name'] or 'Unknown Vendor'
                labels.append(vendor_name)

                total_revenue = float(item['total_revenue'] or 0) * float(PLATFORM_SHARE)
                revenue_data.append(total_revenue)

                order_data.append(item['order_count'])

            # If no data, provide default empty state
            if not labels:
                labels = ['No Data']
                revenue_data = [0]
                order_data = [0]

            return JsonResponse({
                'labels': labels,
                'revenue_data': revenue_data,
                'order_data': order_data,
                'period': period,
                'total_revenue': sum(revenue_data),
                'total_orders': sum(order_data)
            })

        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error in _get_vendor_revenue_data: {str(e)}", exc_info=True)
            return JsonResponse({'error': 'Failed to retrieve vendor revenue data.'}, status=500)

    def _get_trends_data(self, period, vendor_id, now, start_date=None, end_date=None):
        """Get revenue trends over time"""
        try:
            if period == 'custom' and start_date and end_date:
                # Use custom date range for trends
                start_date = start_date
                end_date = end_date
                # For custom range, show daily data
                time_points = []
                current_date = start_date
                while current_date <= end_date:
                    time_points.append(current_date)
                    current_date += timedelta(days=1)
                date_format = '%m-%d'
            else:
                # Use preset periods
                if period == 'day':
                    # Last 24 hours, hourly data
                    start_date = now - timedelta(hours=24)
                    time_points = []
                    for i in range(24):
                        time_points.append(start_date + timedelta(hours=i))
                    date_format = '%H:%M'
                elif period == 'week':
                    # Last 7 days, daily data
                    start_date = now - timedelta(days=7)
                    time_points = []
                    for i in range(7):
                        time_points.append(start_date + timedelta(days=i))
                    date_format = '%m-%d'
                else:  # month
                    # Last 30 days, daily data
                    start_date = now - timedelta(days=30)
                    time_points = []
                    for i in range(30):
                        time_points.append(start_date + timedelta(days=i))
                    date_format = '%m-%d'

            # Get revenue data
            labels = []
            revenue_data = []

            for i, time_point in enumerate(time_points):
                if period == 'day' and period != 'custom':
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
                # Apply platform share
                total = float(total) * float(PLATFORM_SHARE)
                labels.append(time_point.strftime(date_format))
                revenue_data.append(total)

            return JsonResponse({
                'labels': labels,
                'revenue_data': revenue_data,
                'period': period
            })

        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error in _get_trends_data: {str(e)}", exc_info=True)
            return JsonResponse({'error': 'Failed to retrieve trends data.'}, status=500)

    def _get_status_distribution(self, period, vendor_id, now, start_date=None, end_date=None):
        """Get order status distribution"""
        try:
            if period == 'custom' and start_date and end_date:
                start_date = start_date
                end_date = end_date
            else:
                if period == 'day':
                    start_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
                elif period == 'week':
                    start_date = now - timedelta(days=now.weekday())
                    start_date = start_date.replace(hour=0, minute=0, second=0, microsecond=0)
                else:  # month
                    start_date = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
                end_date = now

            orders = Order.objects.filter(created_at__range=(start_date, end_date))
            if vendor_id:
                orders = orders.filter(vendor_id=vendor_id)

            status_counts = orders.values('status').annotate(
                count=Count('id'),
                revenue=Sum('total_price')
            ).order_by('status')

            labels = []
            count_data = []
            revenue_data = []

            for item in status_counts:
                labels.append(item['status'].title())
                count_data.append(item['count'])
                # Apply platform share to revenue
                revenue = float(item['revenue'] or 0) * float(PLATFORM_SHARE)
                revenue_data.append(revenue)

            # If no data, provide empty state
            if not labels:
                labels = ['No Orders']
                count_data = [0]
                revenue_data = [0]

            return JsonResponse({
                'labels': labels,
                'count_data': count_data,
                'revenue_data': revenue_data,
                'period': period
            })

        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error in _get_status_distribution: {str(e)}", exc_info=True)
            return JsonResponse({'error': 'Failed to retrieve status distribution data.'}, status=500)

    def _get_payment_method_analysis(self, period, vendor_id, now, start_date=None, end_date=None):
        """Get payment method analysis"""
        try:
            if period == 'custom' and start_date and end_date:
                start_date = start_date
                end_date = end_date
            else:
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

            payment_analysis = orders.values('payment_type').annotate(
                count=Count('id'),
                revenue=Sum('total_price'),
                avg_order_value=Sum('total_price') / Count('id')
            ).order_by('-revenue')

            labels = []
            count_data = []
            revenue_data = []
            avg_order_data = []

            for item in payment_analysis:
                labels.append(item['payment_type'].replace('_', ' ').title())
                count_data.append(item['count'])
                revenue = float(item['revenue'] or 0) * float(PLATFORM_SHARE)
                revenue_data.append(revenue)
                avg_order_data.append(float(item['avg_order_value'] or 0))

            # If no data, provide empty state
            if not labels:
                labels = ['No Payments']
                count_data = [0]
                revenue_data = [0]
                avg_order_data = [0]

            return JsonResponse({
                'labels': labels,
                'count_data': count_data,
                'revenue_data': revenue_data,
                'avg_order_data': avg_order_data,
                'period': period
            })

        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error in _get_payment_method_analysis: {str(e)}", exc_info=True)
            return JsonResponse({'error': 'Failed to retrieve payment method analysis data.'}, status=500)

    def _get_hourly_distribution(self, period, vendor_id, now, start_date=None, end_date=None):
            """Get hourly order distribution"""
            try:
                if period == 'custom' and start_date and end_date:
                    # For custom range, show daily distribution instead of hourly
                    start_date = start_date
                    end_date = end_date
                    days = (end_date - start_date).days + 1
                    labels = []
                    count_data = []
                    revenue_data = []
                    
                    for day_offset in range(days):
                        day_start = start_date + timedelta(days=day_offset)
                        labels.append(day_start.strftime('%m-%d'))
                        day_orders = Order.objects.filter(
                            status='delivered',
                            created_at__date=day_start.date()
                        )
                        if vendor_id:
                            day_orders = day_orders.filter(vendor_id=vendor_id)
                        
                        count_data.append(day_orders.count())
                        revenue = float(day_orders.aggregate(total=Sum('total_price'))['total'] or 0) * float(PLATFORM_SHARE)
                        revenue_data.append(revenue)
                else:
                    if period == 'day':
                        start_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
                        hours = 24
                    elif period == 'week':
                        start_date = now - timedelta(days=7)
                        hours = 7 * 24  # 168 hours
                    else:  # month
                        start_date = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
                        # Approximate month as 30 days
                        hours = 30 * 24  # 720 hours

                    end_date = now

                    orders = Order.objects.filter(
                        status='delivered',
                        created_at__range=(start_date, end_date)
                    )
                    if vendor_id:
                        orders = orders.filter(vendor_id=vendor_id)

                    # Group by hour
                    hourly_data = orders.extra(
                        select={'hour': 'EXTRACT(hour FROM created_at)'}
                    ).values('hour').annotate(
                        count=Count('id'),
                        revenue=Sum('total_price')
                    ).order_by('hour')

                    # Create labels for all hours
                    labels = []
                    count_data = []
                    revenue_data = []

                    if period == 'day':
                        for hour in range(24):
                            labels.append(f"{hour:02d}:00")
                            hour_data = next((item for item in hourly_data if int(item['hour']) == hour), None)
                            count_data.append(hour_data['count'] if hour_data else 0)
                            revenue = float(hour_data['revenue'] or 0) * float(PLATFORM_SHARE) if hour_data else 0
                            revenue_data.append(revenue)
                    else:
                        # For week/month, group by day
                        for day_offset in range(7 if period == 'week' else 30):
                            day_start = start_date + timedelta(days=day_offset)
                            labels.append(day_start.strftime('%m-%d'))
                            day_orders = orders.filter(
                                created_at__date=day_start.date()
                            )
                            count_data.append(day_orders.count())
                            revenue = float(day_orders.aggregate(total=Sum('total_price'))['total'] or 0) * float(PLATFORM_SHARE)
                            revenue_data.append(revenue)

                # If no data, provide empty state
                if not any(count_data):
                    if period == 'custom':
                        days = (end_date - start_date).days + 1 if start_date and end_date else 7
                        labels = [(start_date + timedelta(days=i)).strftime('%m-%d') for i in range(days)] if start_date else [f"Day {i+1}" for i in range(7)]
                    elif period == 'day':
                        labels = [f"{hour:02d}:00" for hour in range(24)]
                    else:
                        days = 7 if period == 'week' else 30
                        labels = [(start_date + timedelta(days=i)).strftime('%m-%d') for i in range(days)] if 'start_date' in locals() else [f"Day {i+1}" for i in range(days)]
                    count_data = [0] * len(labels)
                    revenue_data = [0] * len(labels)

                return JsonResponse({
                    'labels': labels,
                    'count_data': count_data,
                    'revenue_data': revenue_data,
                    'period': period
                })

            except Exception as e:
                import logging
                logger = logging.getLogger(__name__)
                logger.error(f"Error in _get_hourly_distribution: {str(e)}", exc_info=True)
                return JsonResponse({'error': 'Failed to retrieve hourly distribution data.'}, status=500)

    def _get_order_value_distribution(self, period, vendor_id, now, start_date=None, end_date=None):
        """Get order value distribution"""
        try:
            if period == 'custom' and start_date and end_date:
                start_date = start_date
                end_date = end_date
            else:
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

            # Create value ranges based on order total price (before platform share)
            # These are the actual order values in AFN
            ranges = [
                (0, 50),        # 0-50 AFN
                (50, 100),      # 50-100 AFN
                (100, 250),     # 100-250 AFN
                (250, 500),     # 250-500 AFN
                (500, 750),     # 500-750 AFN
                (750, 1250),    # 750-1250 AFN
                (1250, 2500),   # 1250-2500 AFN
                (2500, float('inf'))  # 2500+ AFN
            ]

            labels = []
            count_data = []
            revenue_data = []

            for min_val, max_val in ranges:
                if max_val == float('inf'):
                    # For orders >= min_val
                    range_orders = orders.filter(total_price__gte=min_val)
                    label = f"{min_val}+ AFN"
                else:
                    # For orders in range [min_val, max_val)
                    range_orders = orders.filter(
                        total_price__gte=min_val,
                        total_price__lt=max_val
                    )
                    label = f"{min_val}-{max_val} AFN"

                labels.append(label)
                count_data.append(range_orders.count())
                revenue = float(range_orders.aggregate(total=Sum('total_price'))['total'] or 0) * float(PLATFORM_SHARE)
                revenue_data.append(revenue)

            # If no data, provide empty state
            if not any(count_data):
                labels = [f"{min_val}{'+' if max_val == float('inf') else f'-{max_val}'} AFN" for min_val, max_val in ranges]
                count_data = [0] * len(ranges)
                revenue_data = [0] * len(ranges)

            return JsonResponse({
                'labels': labels,
                'count_data': count_data,
                'revenue_data': revenue_data,
                'period': period
            })

        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error in _get_order_value_distribution: {str(e)}", exc_info=True)
            return JsonResponse({'error': 'Failed to retrieve order value distribution data.'}, status=500)

    def _get_vendor_performance(self, period, vendor_id, now, start_date=None, end_date=None):
        """Get vendor performance metrics"""
        try:
            if period == 'custom' and start_date and end_date:
                start_date = start_date
                end_date = end_date
            else:
                if period == 'day':
                    start_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
                elif period == 'week':
                    start_date = now - timedelta(days=now.weekday())
                    start_date = start_date.replace(hour=0, minute=0, second=0, microsecond=0)
                else:  # month
                    start_date = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

                end_date = now

            orders = Order.objects.filter(created_at__range=(start_date, end_date))
            if vendor_id:
                orders = orders.filter(vendor_id=vendor_id)

            vendor_performance = orders.values('vendor__vendor_name').annotate(
                total_orders=Count('id'),
                delivered_orders=Count('id', filter=Q(status='delivered')),
                cancelled_orders=Count('id', filter=Q(status='cancelled')),
                total_revenue=Sum('total_price', filter=Q(status='delivered'))
            ).order_by('-total_orders')

            labels = []
            delivery_rate_data = []
            avg_order_value_data = []
            total_orders_data = []

            for item in vendor_performance:
                vendor_name = item['vendor__vendor_name'] or 'Unknown Vendor'
                labels.append(vendor_name)
                total_orders = item['total_orders']
                delivered_orders = item['delivered_orders']
                delivery_rate = (delivered_orders / total_orders * 100) if total_orders > 0 else 0
                delivery_rate_data.append(round(delivery_rate, 1))

                total_revenue = float(item['total_revenue'] or 0) * float(PLATFORM_SHARE)
                avg_order_value = total_revenue / delivered_orders if delivered_orders > 0 else 0
                avg_order_value_data.append(round(avg_order_value, 2))

                total_orders_data.append(total_orders)

            # If no data, provide empty state
            if not labels:
                labels = ['No Vendors']
                delivery_rate_data = [0]
                avg_order_value_data = [0]
                total_orders_data = [0]

            return JsonResponse({
                'labels': labels,
                'delivery_rate_data': delivery_rate_data,
                'avg_order_value_data': avg_order_value_data,
                'total_orders_data': total_orders_data,
                'period': period
            })

        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error in _get_vendor_performance: {str(e)}", exc_info=True)
            return JsonResponse({'error': 'Failed to retrieve vendor performance data.'}, status=500)


# Create a custom admin site instance
revenue_admin_site = RevenueAnalyticsAdminSite(name='revenue_admin')

# Register TOTPDevice with the custom admin site
revenue_admin_site.register(TOTPDevice, TOTPDeviceAdmin)

from django_celery_beat.models import (
    PeriodicTask,
    IntervalSchedule,
    CrontabSchedule,
    SolarSchedule,
    ClockedSchedule,
)

revenue_admin_site.register(PeriodicTask)
revenue_admin_site.register(IntervalSchedule)
revenue_admin_site.register(CrontabSchedule)
revenue_admin_site.register(SolarSchedule)
revenue_admin_site.register(ClockedSchedule)