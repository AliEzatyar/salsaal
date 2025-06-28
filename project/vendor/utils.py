from django.conf import settings as s
from redis import Redis
r = Redis(s.REDIS_HOST, s.REDIS_PORT, s.REDIS_DB)


def to_af_weekday(index):
    return (9 + index) % 7 + 1

