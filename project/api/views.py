from rest_framework import views
from marketplace.utils import r
from rest_framework.response import Response
from json import  loads, dumps

class AppInfoAPIView(views.APIView):
    
    def get(self, request):
        app_info  = r.get("app_info_data")
        if app_info:
            app_info = loads(app_info)
        else:
            app_info = {
            "zayton_business_version": "1.5.1",
            "zayton_business_ios_update_url": "https://apps.apple.com/us/app/zayton-business/id6755327947",
            "zayton_business_android_update_url": "https://play.google.com/store/apps/details?id=llc.zayton.business",
            "zayton_business_windows_update_url": "https://example.com/windows/update",
            "zayton_business_message": "A new version is available! Please update to enjoy the latest features.",
            "zayton_food_version": "1.2.3",
            "zayton_food_ios_update_url": "https://apps.apple.com/us/app/zayton-food/id6755328024",
            "zayton_food_android_update_url": "https://play.google.com/store/apps/details?id=llc.zayton.zayton",
            "zayton_food_message": "A new version is available",
            "zayton_delivery_version": "1.5.7",
            "zayton_delivery_ios_update_url": "https://apps.apple.com/us/app/zayton-delivery/id6755328028",
            "zayton_delivery_android_update_url": "https://play.google.com/store/apps/details?id=llc.zayton.delivery",
            "zayton_delivery_message": "A new version is available",
            }
            r.set("app_info_data", dumps(app_info))  # cache for 1 day
        return Response(app_info)