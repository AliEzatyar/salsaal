import requests
import redis
from django.conf import settings
from celery import shared_task
from marketplace.utils import r as redis_client



@shared_task
def update_afn_usd_rate():

    url = settings.EXCHANGE_URL
    access_key = settings.EXCHANGERATEHOSTKEY 
    params = {"access_key": access_key, "symbols": "USD,AFN"}

    response = requests.get(url, params=params, timeout=30)
    try:
        response.raise_for_status()
    except:
        redis_client.set("exchange:AFN_USD", 1 / 65.5599, ex=25*3600)

    data = response.json()

    # failure handle
    if not data.get("success"):
        redis_client.set("exchange:AFN_USD", 1/65.5599, ex=25*3600)
        return afn_usd

    usd_afn = data["quotes"]["USDAFN"]

    # convert USD->AFN  to  AFN->USD
    afn_usd = 1 / usd_afn
    
    # save to redis (TTL 1 hour)
    redis_client.set("exchange:AFN_USD", afn_usd, ex=25*3600)
    
    return afn_usd
