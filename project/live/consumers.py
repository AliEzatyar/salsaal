# import json
# import time
# from channels.generic.websocket import AsyncWebsocketConsumer, AsyncJsonWebsocketConsumer
# from json import loads, dumps
# from live.models import Notification
# from django.conf import settings as s
# from redis.asyncio import Redis
# from carrier.models import Carrier
# from marketplace.utils import r
# from carrier.utils import get_carrier_key

# # Wrappers
# def get_redis_value(key):
#     return r.get(key)


# def set_redis_value(key, value):
#     return r.set(key, value)


# class NotificationConsumer(AsyncWebsocketConsumer):
#     """
#         This consumser is used for real-time notification system and live tracking
#     """
#     async def connect(self):
#         """performs connection settings"""
#         # prevent unauthenticated users
#         user = self.scope["user"]
#         if not user.is_authenticated:
#             await self.close()
#             return
#         self.user = user
#         # set up group and accept connection
#         self.notf_for = self.scope["url_route"]["kwargs"]["for"]
#         self.group_id = self.scope["url_route"]["kwargs"]["id"]  # vendor id
#         if self.notf_for in ["vdor", "crir", "cstmr"]:
#             self.group_name = f"notf_{self.notf_for}_{self.group_id}"  # notf_vendor_5
#         await self.channel_layer.group_add(self.group_name, self.channel_name)
#         await self.accept()

#     async def receive(self, text_data=None, bytes_data=None):
#         """performs logic and share recived data into layers"""
#         data = loads(text_data)
#         if data["type"] == "share_notf":
#             try:
#                 notf_type = data["notf_type"]
#                 if notf_type == "new_order":
#                     notf_id = int(data["notf_id"])
#                     notf = await Notification.objects.aget(id=notf_id)  # must use await
#                     notf_data = notf.data
#                     await self.channel_layer.group_send(
#                         self.group_name,
#                         {
#                             "type": "share_notf",
#                             "notf_type": notf_type,
#                             "data": notf_data,
#                         },
#                     )
#                 elif notf_type == "vendor_answer":
#                     await self.channel_layer.group_send(
#                         self.group_name,
#                         {
#                             "type": "share_notf",
#                             "notf_type": notf_type,
#                             "data": data["data"],
#                         },
#                     )

#                 elif notf_type == "customer_answer":
#                     await self.channel_layer.group_send(
#                         self.group_name,
#                         {
#                             "type": "share_notf",
#                             "notf_type": notf_type,
#                             "data": {
#                                 "answer": data["data"]["answer"],
#                                 "order_id": data["data"]["order_id"],
#                             },
#                         },
#                     )
#                 elif notf_type == "order_carrying":
#                     await self.channel_layer.group_send(
#                         self.group_name,
#                         {
#                             "type": "share_notf",
#                             "notf_type": notf_type,
#                             "data": data["data"],
#                         },
#                     )
#                 elif notf_type == "order_delivered":

#                     await self.channel_layer.group_send(
#                         self.group_name,
#                         {
#                             "type": "share_notf",
#                             "notf_type": notf_type,
#                             "data": data["data"],
#                         },
#                     )
#                 elif notf_type == "location_data":
#                     # updating carriers location in redis
#                     try:
#                         carrier = await Carrier.objects.aget(user=self.user)
#                         carrier_key = get_carrier_key(carrier.id)
#                         location_data = data["data"]
#                         location_data = (location_data["lat"], location_data["lon"])
#                         raw_data = await r.get(carrier_key)
#                         carrier_details = json.loads(raw_data)  # coroutine arg denied
#                         carrier_details["location"] = location_data
#                         await r.set(
#                             carrier_key,
#                             json.dumps(carrier_details),
#                         )

#                     except Exception as e:
#                         print(
#                             "error occured while updating carrier locaiton", e.args, e
#                         )
#                         pass
#                     await self.channel_layer.group_send(
#                         self.group_name,
#                         {
#                             "type": "share_notf",
#                             "notf_type": notf_type,
#                             "data": data["data"],
#                         },
#                     )
#             except Exception as e:
#                 print("errror in consumer...", e.args, e)
#                 pass

#     async def share_notf(self, event):
#         """takes data out of layers"""
#         print("message sent out of layers")
#         await self.send(
#             text_data=dumps(
#                 {
#                     "type": "recv_notf",
#                     "notf_type": event["notf_type"],
#                     "data": event["data"],
#                 }
#             )
#         )


# def safe_float(v, default=None):
#     try: return float(v)
#     except: return default


# class LocationConsumer(AsyncJsonWebsocketConsumer):

#     async def connect(self):
#         user = self.scope["user"]
#         if not user.is_authenticated:
#             await self.close()
#             return 

#         self.track_id = self.scope["url_route"]["kwargs"]["track_id"]
#         self.group = f"track_{self.track_id}"
#         # authorize: e.g., only driver of this order or customer tied to it
#         # if not self.scope["user"].is_authenticated: await self.close(); return
#         await self.channel_layer.group_add(self.group, self.channel_name)
#         await self.accept()

#         # optional: send last known location from cache/db
#         # last = await get_last_location(self.track_id)
#         # if last: await self.send_json({"type": "snapshot", "data": last})

#     async def receive_json(self, content, **kwargs):
#         # Expect publisher payloads like: {"role":"driver","lat":..., "lon":..., "heading":..., "speed":..., "ts":...}
#         role = content.get("role")
#         if role == "driver":  # only drivers can publish
#             lat = safe_float(content.get("lat"))
#             lon = safe_float(content.get("lon"))
#             if lat is None or lon is None:
#                 return
#             msg = {
#                 "type": "location",
#                 "track_id": self.track_id,
#                 "lat": lat,
#                 "lon": lon,
#                 "heading": safe_float(content.get("heading")),
#                 "speed": safe_float(content.get("speed")),
#                 "ts": content.get("ts") or int(time.time() * 1000),
#             }
#             # persist latest (cache/db) if you need replay
#             # await save_last_location(self.track_id, msg)
#             await self.channel_layer.group_send(
#                 self.group, {"type": "broadcast", "message": msg}
#             )

#         elif role == "ping":
#             await self.send_json({"type": "pong"})

#     async def broadcast(self, event):
#         await self.send_json(event["message"])

#     async def disconnect(self, code):
#         await self.channel_layer.group_discard(self.group, self.channel_name)

