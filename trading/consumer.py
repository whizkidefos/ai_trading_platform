import json
from channels.generic.websocket import WebsocketConsumer

class TradeConsumer(WebsocketConsumer):
    def connect(self):
        # Add the WebSocket to the 'trade_notifications' group
        async_to_sync(self.channel_layer.group_add)(
            'trade_notifications',
            self.channel_name
        )
        self.accept()

    def disconnect(self, close_code):
        # Remove the WebSocket from the 'trade_notifications' group
        async_to_sync(self.channel_layer.group_discard)(
            'trade_notifications',
            self.channel_name
        )

    def trade_update(self, event):
        # Handle the custom 'trade_update' event sent from the server
        message = event['message']

        # Send the message to the WebSocket
        self.send(text_data=json.dumps({
            'message': message
        }))