from channels.generic.websocket import AsyncWebsocketConsumer
import json

class TradeConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        await self.channel_layer.group_add("trade_updates", self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard("trade_updates", self.channel_name)

    async def trade_update(self, event):
        message = event['message']
        await self.send(text_data=json.dumps({'message': message}))
