from math import sin, cos, radians, sqrt, atan2
import redis
from django.conf import settings as s
from os import environ as env
import requests as req
from rest_framework.pagination import PageNumberPagination
import geohash
from rest_framework.response import Response


r = redis.Redis(s.REDIS_HOST, s.REDIS_PORT, s.REDIS_DB)
DEFAULT_H3_RESOLUTION = 9
DEFAULT_H3_EDGE_LENGTH = 0.357
DEFAULT_AVG_SPEED = 5


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
        self.best_foods_key = "best_foods:{city}:city"

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
    return (
        int(response["paths"][0]["time"]) / 60000,
        round(float(response["paths"][0]["distance"]) / 1000, 1),
    )


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


def is_user_online(user_id):
    return r.hexists(f"ws:users:{user_id}")  # returns 1 if online, 0 if offline


def distance_reach_time(qs, lat, lon, typ="food"):
    """
    this utility function calculates rough distance using haversine formula
    typ is either food or vendor
    """
    for obj in qs:
        distance = round(
            haversine_distance(
                (
                    obj.vendor.latitude
                    if typ == "food"
                    else obj.latitude
                ),
                (
                    obj.vendor.longitude
                    if typ == "food"
                    else obj.longitude
                ),
                lat,
                lon,
            ),
            1,
        )
        obj.distance = distance
        obj.reach_time = round(distance_to_travel_time(distance), 1)


def get_user_info(request):
    """
    this utility method extracts user info from request object, if not
    provided, takes from user profile
    it is used mostly in marketplace app.
    """
    request_data = request.query_params
    city = request_data.get("city", None)
    location = request_data.get("location", None)
    if not city or not location:
        return Response(status=400)
    try:
        # decoding location
        lat, lon = geohash.decode(location)
    except:
        lat = request.user.profile.latitude
        lon = request.user.profile.longitude
        city = request.user.profile.city
    city = str(city).lower()
    return (city, lat, lon)
