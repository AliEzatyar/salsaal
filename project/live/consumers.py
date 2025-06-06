from channels.generic.websocket import AsyncWebsocketConsumer
from asgiref.sync import sync_to_async
from json import loads, dumps
import os
from live.models import Notification



class NotificationConsumer(AsyncWebsocketConsumer):

    async def connect(self):
        print("connected to layers")
        self.notf_for = self.scope["url_route"]["kwargs"]["for"]
        self.group_id = self.scope["url_route"]["kwargs"]["id"]  # vendor id
        if self.notf_for in ["vendor", "carrier"]:
            self.group_name = f"notf_{self.notf_for}_{self.group_id}"  # notf_vendor_5
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()
        print("accepted connection")

    async def receive(self, text_data=None, bytes_data=None):
        print("layers received data ")
        data = loads(text_data)
        if data["type"] == "share_notf":
            try:
                notf_id = int(data["notf_id"])
                notf = Notification.objects.aget(id=notf_id)
                notf_data = notf.data
                await self.channel_layer.group_send(
                    self.group_name,
                    {"type": "share_notf", "notf_data": notf_data, "rcvr": notf.to},
                )
                print("sending in layers")
            except Exception as e:
                print(e.args)
                pass

    async def share_notf(self, event):
        await self.send(
            text_data=dumps(
                {
                    "type": "recv_notf",
                    "notf_data": event["notf_data"],
                    "rcvr": event["rcvr"],
                }
            )
        )
        print("sending data out of layers")

    async def disconnect(self, code):
        print("disconnected")
        return await super().disconnect(code)
