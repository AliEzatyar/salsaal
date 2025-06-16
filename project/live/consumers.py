from channels.generic.websocket import AsyncWebsocketConsumer
from asgiref.sync import sync_to_async
from json import loads, dumps
import os
from live.models import Notification


class NotificationConsumer(AsyncWebsocketConsumer):

    async def connect(self):
        """performs connection settings"""
        # prevent unauthenticated users
        user = self.scope["user"]
        if not user.is_authenticated:
            await self.close()
            return
        # set up group and accept connection
        self.notf_for = self.scope["url_route"]["kwargs"]["for"]
        self.group_id = self.scope["url_route"]["kwargs"]["id"]  # vendor id
        if self.notf_for in ["vdor", "crir", "cstmr"]:
            self.group_name = f"notf_{self.notf_for}_{self.group_id}"  # notf_vendor_5
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

    async def receive(self, text_data=None, bytes_data=None):
        """performs logic and share recived data into layers"""
        print("layers received data ", text_data)
        data = loads(text_data)
        if data["type"] == "share_notf":
            try:
                notf_type = data["notf_type"]
                if notf_type == "new_order":
                    notf_id = int(data["notf_id"])
                    notf = await Notification.objects.aget(id=notf_id)  # must use await
                    notf_data = notf.data
                    await self.channel_layer.group_send(
                        self.group_name,
                        {
                            "type": "share_notf",
                            "notf_type": notf_type,
                            "data": notf_data,
                        },
                    )
                elif notf_type == "vendor_answer":
                    await self.channel_layer.group_send(
                        self.group_name,
                        {
                            "type": "share_notf",
                            "notf_type": notf_type,
                            "data": data["data"],
                        },
                    )

                elif notf_type == "customer_answer":
                    await self.channel_layer.group_send(
                        self.group_name,
                        {
                            "type": "share_notf",
                            "notf_type": notf_type,
                            "data": {"answer":data["data"]['answer'],"order_id":data['data']['order_id']},
                        },
                    )
            except Exception as e:
                print("errror in consumer...", e.args, e)
                pass

    async def share_notf(self, event):
        """takes data out of layers"""
        print("message sent out of layers")
        await self.send(
            text_data=dumps(
                {
                    "type": "recv_notf",
                    "notf_type": event["notf_type"],
                    "data": event["data"],
                }
            )
        )
