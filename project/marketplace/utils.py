from math import sin, cos, radians, sqrt, atan2
import redis
from django.conf import settings as s

r = redis.Redis(s.REDIS_HOST, s.REDIS_PORT, s.REDIS_DB)


def haversine_distance(lat1, lon1, lat2, lon2):
    lat1, lon1, lat2, lon2 = float(lat1), float(lon1), float(lat2), float(lon2)
    R = 6371  # Earth radius in kilometers

    phi1 = radians(lat1)
    phi2 = radians(lat2)

    d_phi = radians(lat2 - lat1)
    d_lambda = radians(lon2 - lon1)

    a = sin(d_phi / 2) ** 2 + cos(phi1) * cos(phi2) * sin(d_lambda / 2) ** 2

    c = 2 * atan2(sqrt(a), sqrt(1 - a))

    return R * c  # distance in kilometers


class BoughtTogetherRecommender:
    """
    this class provides suggestions for one or more fooditems which are purchased together
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
    def __init__(self, city="Kabul"):
        self.redis = r
        self.top_vendors_key = "top_vendors:{city}:city"

    def update_counts(self, pk):
        """increases view count of a vendor in the sorted set """
        r.zincrby(self.top_vendors_key, 1, pk)

    def read_counts(self, max_results=5):
        """returns ids of most viewed vendors in the city"""
        top = r.zrange(self.top_vendors_key, 0, -1, desc=True)[:max_results]
        return list(map(int,top))
