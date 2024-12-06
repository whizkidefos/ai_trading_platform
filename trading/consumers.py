import json
from channels.generic.websocket import AsyncWebsocketConsumer
from django.db.models import Sum
from django.utils import timezone
from asgiref.sync import database_sync_to_async
from .models import Trade
import yfinance as yf
import numpy as np
import asyncio

class TradeConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        await self.channel_layer.group_add("trades", self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard("trades", self.channel_name)

    async def receive(self, text_data):
        text_data_json = json.loads(text_data)
        message = text_data_json['message']

        # Send message to room group
        await self.channel_layer.group_send(
            "trades",
            {
                'type': 'trade_message',
                'message': message
            }
        )

    async def trade_message(self, event):
        message = event['message']

        # Send message to WebSocket
        await self.send(text_data=json.dumps({
            'message': message
        }))

class AutomatedTradingConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.user = self.scope["user"]
        if not self.user.is_authenticated:
            await self.close()
            return

        self.room_name = f"auto_trading_{self.user.id}"
        self.room_group_name = f"auto_trading_group_{self.user.id}"
        self.update_task = None

        # Join room group
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )

        await self.accept()
        
        # Send initial status and start market data updates
        await self.send_trading_status()
        self.update_task = asyncio.create_task(self.send_market_updates())

    async def disconnect(self, close_code):
        # Cancel the update task if it exists
        if self.update_task:
            self.update_task.cancel()
            try:
                await self.update_task
            except asyncio.CancelledError:
                pass

        # Leave room group
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )

    async def receive(self, text_data):
        # Handle any messages from the client if needed
        pass

    async def send_trading_status(self):
        # Get today's trading stats
        today = timezone.now().date()
        trades = await self.get_today_trades(today)
        profit_loss = sum(trade.profit_loss for trade in trades) if trades else 0
        
        await self.send(text_data=json.dumps({
            'type': 'status',
            'message': 'Automated trading system initialized',
            'stats': {
                'trades_count': len(trades),
                'profit_loss': profit_loss
            }
        }))

    @database_sync_to_async
    def get_today_trades(self, date):
        return list(Trade.objects.filter(
            user=self.user,
            timestamp__date=date,
            automated=True
        ))

    def calculate_rsi(self, prices, periods=14):
        deltas = np.diff(prices)
        gain = np.where(deltas > 0, deltas, 0)
        loss = np.where(deltas < 0, -deltas, 0)
        
        avg_gain = np.mean(gain[:periods])
        avg_loss = np.mean(loss[:periods])
        
        if avg_loss == 0:
            return 100
        
        rs = avg_gain / avg_loss
        return 100 - (100 / (1 + rs))

    def calculate_macd(self, prices, fast=12, slow=26, signal=9):
        # Calculate EMAs
        exp1 = prices.ewm(span=fast, adjust=False).mean()
        exp2 = prices.ewm(span=slow, adjust=False).mean()
        macd = exp1 - exp2
        signal_line = macd.ewm(span=signal, adjust=False).mean()
        return macd.iloc[-1], signal_line.iloc[-1]

    @database_sync_to_async
    def get_market_data(self):
        # Get the current asset from user's settings or default to 'AAPL'
        symbol = 'AAPL'  # You should get this from user's settings
        
        try:
            # Fetch historical data
            ticker = yf.Ticker(symbol)
            hist = ticker.history(period='1d', interval='1m')
            
            if hist.empty:
                return None
            
            # Calculate technical indicators
            close_prices = hist['Close']
            volume = hist['Volume'].iloc[-1]
            
            # Calculate RSI
            rsi = self.calculate_rsi(close_prices)
            
            # Calculate MACD
            macd, signal = self.calculate_macd(close_prices)
            
            return {
                'price': float(close_prices.iloc[-1]),
                'volume': int(volume),
                'technical': {
                    'rsi': float(rsi),
                    'macd': float(macd)
                }
            }
        except Exception as e:
            print(f"Error fetching market data: {e}")
            return None

    async def send_market_updates(self):
        while True:
            try:
                # Get market data
                market_data = await self.get_market_data()
                
                if market_data:
                    # Get today's P/L
                    today = timezone.now().date()
                    trades = await self.get_today_trades(today)
                    profit_loss = sum(trade.profit_loss for trade in trades) if trades else 0
                    
                    # Add P/L to market data
                    market_data['profitLoss'] = profit_loss
                    
                    # Send update
                    await self.send(text_data=json.dumps({
                        'type': 'market_update',
                        **market_data
                    }))
                
                # Wait for 1 minute before next update
                await asyncio.sleep(60)
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"Error in market updates: {e}")
                await asyncio.sleep(60)  # Wait before retrying

    async def trading_update(self, event):
        # Send message to WebSocket
        await self.send(text_data=json.dumps(event))
