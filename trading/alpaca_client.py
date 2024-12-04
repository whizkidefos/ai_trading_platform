import os
import logging
from decimal import Decimal
from typing import Dict, List, Optional

from alpaca_trade_api.rest import REST, TimeFrame
from alpaca_trade_api.stream import Stream
import alpaca_trade_api as tradeapi

logger = logging.getLogger(__name__)

class AlpacaClient:
    def __init__(self):
        self.api_key = os.getenv('ALPACA_API_KEY')
        self.api_secret = os.getenv('ALPACA_SECRET_KEY')
        self.base_url = os.getenv('ALPACA_BASE_URL', 'https://api.alpaca.markets')  # Use paper URL for testing
        
        self.api = REST(
            key_id=self.api_key,
            secret_key=self.api_secret,
            base_url=self.base_url
        )
        
        self.stream = Stream(
            key_id=self.api_key,
            secret_key=self.api_secret,
            base_url=self.base_url,
            data_feed='iex'  # Use 'sip' for production
        )

    async def get_account(self) -> Dict:
        """Get Alpaca account information"""
        try:
            account = self.api.get_account()
            return {
                'cash': Decimal(account.cash),
                'portfolio_value': Decimal(account.portfolio_value),
                'buying_power': Decimal(account.buying_power),
                'day_trade_count': account.daytrade_count,
                'trading_blocked': account.trading_blocked,
                'trades_blocked': account.trades_blocked,
                'transfers_blocked': account.transfers_blocked
            }
        except Exception as e:
            logger.error(f"Error getting Alpaca account info: {str(e)}")
            raise

    async def place_order(
        self,
        symbol: str,
        qty: float,
        side: str,
        type: str = 'market',
        time_in_force: str = 'day',
        limit_price: Optional[float] = None,
        stop_price: Optional[float] = None
    ) -> Dict:
        """Place an order on Alpaca"""
        try:
            order = self.api.submit_order(
                symbol=symbol,
                qty=qty,
                side=side,
                type=type,
                time_in_force=time_in_force,
                limit_price=limit_price,
                stop_price=stop_price
            )
            
            return {
                'id': order.id,
                'client_order_id': order.client_order_id,
                'symbol': order.symbol,
                'side': order.side,
                'qty': order.qty,
                'filled_qty': order.filled_qty,
                'type': order.type,
                'status': order.status,
                'created_at': order.created_at
            }
        except Exception as e:
            logger.error(f"Error placing Alpaca order: {str(e)}")
            raise

    async def get_position(self, symbol: str) -> Dict:
        """Get position information for a symbol"""
        try:
            position = self.api.get_position(symbol)
            return {
                'symbol': position.symbol,
                'qty': int(position.qty),
                'avg_entry_price': Decimal(position.avg_entry_price),
                'market_value': Decimal(position.market_value),
                'unrealized_pl': Decimal(position.unrealized_pl),
                'current_price': Decimal(position.current_price),
                'lastday_price': Decimal(position.lastday_price),
                'change_today': Decimal(position.change_today)
            }
        except Exception as e:
            if 'position does not exist' in str(e).lower():
                return None
            logger.error(f"Error getting Alpaca position: {str(e)}")
            raise

    async def get_positions(self) -> List[Dict]:
        """Get all open positions"""
        try:
            positions = self.api.list_positions()
            return [{
                'symbol': pos.symbol,
                'qty': int(pos.qty),
                'avg_entry_price': Decimal(pos.avg_entry_price),
                'market_value': Decimal(pos.market_value),
                'unrealized_pl': Decimal(pos.unrealized_pl),
                'current_price': Decimal(pos.current_price),
                'lastday_price': Decimal(pos.lastday_price),
                'change_today': Decimal(pos.change_today)
            } for pos in positions]
        except Exception as e:
            logger.error(f"Error getting Alpaca positions: {str(e)}")
            raise

    async def get_bars(
        self,
        symbol: str,
        timeframe: TimeFrame,
        start: Optional[str] = None,
        end: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict]:
        """Get historical bar data for a symbol"""
        try:
            bars = self.api.get_bars(
                symbol,
                timeframe,
                start=start,
                end=end,
                limit=limit
            ).df
            
            return [{
                'timestamp': bar.name.isoformat(),
                'open': Decimal(str(bar['open'])),
                'high': Decimal(str(bar['high'])),
                'low': Decimal(str(bar['low'])),
                'close': Decimal(str(bar['close'])),
                'volume': int(bar['volume'])
            } for bar in bars.itertuples()]
        except Exception as e:
            logger.error(f"Error getting Alpaca bars: {str(e)}")
            raise

    def close_all_positions(self) -> None:
        """Close all open positions"""
        try:
            self.api.close_all_positions()
        except Exception as e:
            logger.error(f"Error closing all positions: {str(e)}")
            raise

    def cancel_all_orders(self) -> None:
        """Cancel all open orders"""
        try:
            self.api.cancel_all_orders()
        except Exception as e:
            logger.error(f"Error canceling all orders: {str(e)}")
            raise
