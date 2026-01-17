from math import sin, cos, radians, sqrt, atan2
import redis
from django.conf import settings as s
from os import environ as env
import requests as req
from rest_framework.pagination import PageNumberPagination
import geohash
from rest_framework.exceptions import ValidationError
from .info import CITY_TRANSLATIONS, CITY_TRANSLATIONS_REVERSED
 
r = redis.Redis(s.REDIS_HOST, s.REDIS_PORT, s.REDIS_DB,password=s.REDIS_PASSWORD)
DEFAULT_H3_RESOLUTION = 9
DEFAULT_H3_EDGE_LENGTH = 0.357
DEFAULT_AVG_SPEED = 5

uws_redis = redis.Redis(s.REDIS_HOST, s.REDIS_PORT, "1",password=s.REDIS_PASSWORD)

class BoughtTogetherRecommender:
    """
    this class provides suggestions for one or more fooditems.
    """

    def __init__(self):
        """this initilaizes the connection with redis"""
        self.redis = r

    def get_food_key(self, pk):
        return f"food:{pk}:purchased_with"

    def update_together_bought(self, pks):
        """it is called both in order creation and add to card"""
        for this_food in pks:
            for another_food in pks:
                if another_food != this_food:
                    self.redis.zincrby(self.get_food_key(this_food), 1, another_food)

    def suggest_foods_for(self, food_ids, max_results=5):
        """
        input: foods ids
        output: a list of ids of suggested foods
        """
        pks = [f for f in food_ids]
        if len(pks) < 1:
            return []

        if len(pks) == 1:
            # this is mostly used in food detail page where we suggest for 1 fooditem.
            key = self.get_food_key(pks[0])
            suggestions = self.redis.zrange(key, 0, -1, desc=True)[:max_results]

        else:
            # this is mostly used in cart and order creating page
            ids = "".join([str(pk) for pk in pks])
            all_food_keys = [
                self.get_food_key(pk) for pk in pks
            ]  # list of keys of each food sorted-set
            temp_key = f"temp_{ids}"
            # unioning and aggregating
            self.redis.zunionstore(
                temp_key, all_food_keys
            )  # this makes a union and  aggregates by sum

            # removing for food itself
            self.redis.zrem(temp_key, *all_food_keys)

            # extracting suggestions
            suggestions = self.redis.zrange(temp_key, 0, -1, desc=True)[:max_results]
            # removing temporary key
            self.redis.delete(temp_key)
        suggestions_ids = list(map(int, suggestions))
        return suggestions_ids


class BestVendorsCounter:
    """THis class save view counts and return most viewd vendor ids"""

    def __init__(self, city):
        self.redis = r
        self.top_vendors_key = f"top_vendors:{city}:city"

    def update_counts(self, pk):
        """increases view count of a vendor in the sorted set"""
        r.zincrby(self.top_vendors_key, 1, pk)

    def read_counts(self, max_results=5):
        """returns ids of most viewed vendors in the city"""
        top = r.zrange(self.top_vendors_key, 0, -1, desc=True)[:max_results]
        
        return list(map(int, top))


class BestFoodsCounter:
    """THis class save view counts and return most viewd food ids"""

    def __init__(self, city):
        self.redis = r
        self.best_foods_key = f"best_foods:{city}:city"

    def update_counts(self, pk):
        """increases view count of a food in the sorted set"""
        r.zincrby(self.best_foods_key, 1, pk)

    def read_counts(self, max_results=5):
        """returns ids of most viewed foods in the city"""
        best = r.zrange(self.best_foods_key, 0, -1, desc=True)[:max_results]
        return list(map(int, best))


def haversine_distance(lat1, lon1, lat2, lon2):
    """this function estimates distance, 90 degree traingle, A-start, B , C-goal, then distance
    is b+c"""
    lat1, lon1, lat2, lon2 = float(lat1), float(lon1), float(lat2), float(lon2)
    R = 6371  # Earth radius in kilometers

    phi1 = radians(lat1)
    phi2 = radians(lat2)

    d_phi = radians(lat2 - lat1)
    d_lambda = radians(lon2 - lon1)

    a = sin(d_phi / 2) ** 2 + cos(phi1) * cos(phi2) * sin(d_lambda / 2) ** 2

    c = 2 * atan2(sqrt(a), sqrt(1 - a))

    return R * c  # distance in kilometers


def estimate_travel_time_graphhopper(origin, destination):
    """
    this function makes a call to Graphhopper web api locally hosted.
    How graphhopper is set up?
    help: https://libreselfhosted.com/project/graphhopper/
    * download osm.pbf file of afghanistan or ...
    * install java
        sudo apt install openjdk-17-jdk
    * download graphhopper .jar file from:
        https://github.com/graphhopper/graphhopper/releases
    * write config.json and custom-car.json
    * run using java
        java -Ddw.graphhopper.datareader.file=afghanistan-latest.osm.pbf -jar *.jar server prod-config.json
    Faced a lot of errors when first set up: see

    """
    hopper_host = env.get("GRAPHHOPPER_HOST")
    response = req.get(
        f"http://{hopper_host}:8989/route?point={origin[0]},{origin[1]}&point={destination[0]},{destination[1]}&profile=car&calc_points=false&instructions=false"
    )
    response = response.json()
    distance = 0
    travel_time = 0
    if not response.get("paths",None):
        distance = haversine_distance(origin[0],origin[1],destination[0],destination[1])
        travel_time = distance_to_travel_time(distance)
    else:
        distance = round(float(response["paths"][0]["distance"]) / 1000, 1)
        travel_time = int(response["paths"][0]["time"]) / 60000
    return (distance, travel_time)


def h3_distance_to_km(val, edge_length=DEFAULT_H3_EDGE_LENGTH):
    return (val) * edge_length


def distance_to_travel_time(distance, avg_speed=DEFAULT_AVG_SPEED):
    """distance in km"""
    return distance * 1000 / (avg_speed) / 60


class StandardResultSetPagination(PageNumberPagination):
    page_size = 10

    def __init__(self, page_size=10):
        super().__init__()
        self.page_size = page_size



def distance_reach_time(qs, lat, lon, typ="food"):
    """
    this utility function calculates rough distance using haversine formula
    typ is either food or vendor
    """
    for obj in qs:
        distance = round(
            haversine_distance(
                (obj.vendor.latitude if typ == "food" else obj.latitude),
                (obj.vendor.longitude if typ == "food" else obj.longitude),
                lat,
                lon,
            ),
            1,
        )
        obj.distance = distance
        obj.reach_time = round(distance_to_travel_time(distance), 1)


def get_user_info(request):
    """
    Extracts user info from request object. If not provided, takes from user profile.
    Returns: city (str), lat (float), lon (float)
    not used yet, for future use
    """
    request_data = request.query_params
    city = request_data.get("city")
    location = request_data.get("location")

    # fallback to user profile if missing
    if not city:
        if hasattr(request.user, "profile"):
            city = request.user.profile.city
        else:
            raise ValidationError({"detail": "city_required"})
    if not location:
        if hasattr(request.user, "profile"):
            lat = float(request.user.profile.latitude)
            lon = float(request.user.profile.longitude)
        else:
            raise ValidationError({"detail": "Location_required"})
    else:
        try:
            lat, lon = geohash.decode(location)
        except Exception:
            if hasattr(request.user, "profile"):
                lat = float(request.user.profile.latitude)
                lon = float(request.user.profile.longitude)
            else:
                raise ValidationError({"detail": "Location_required"})
    # ----- identifying foreign users
    # if dari city name given, convert to english
    if city in CITY_TRANSLATIONS_REVERSED.keys():
        # converting to english
        city = CITY_TRANSLATIONS_REVERSED[city]
    # user is foreign
    is_foreign = False
    if city.title() not in CITY_TRANSLATIONS.keys():
        city = "kabul"  # default city for foreign users
        lat, lon = 34.53429766405601, 69.17093145586269  # Kabul coordinates
        is_foreign = True
    city = str(city).lower()
    return city, lat, lon, is_foreign
