from django.test import TestCase
import unittest
from decimal import Decimal
from unittest.mock import patch, MagicMock
from django.contrib.auth.models import User
from .models import UserProfile, Trade, AccountBalance
from .automated_trading import AutomatedTrading
from .ai_trading import make_trade_prediction, apply_combined_strategy
from .alpaca_client import AlpacaClient

class TestAutomatedTrading(TestCase):
    def setUp(self):
        # Create a test user first
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )
        
        # Create UserProfile with correct fields
        self.user_profile = UserProfile.objects.create(
            user=self.user,
            trading_experience='intermediate',
            risk_tolerance='moderate',
            preferred_currency='USD'
        )
        self.trading = AutomatedTrading(self.user_profile)

    @patch('trading.alpaca_client.AlpacaClient')
    def test_risk_management(self, mock_alpaca):
        """Test risk management rules"""
        # Test position sizing
        account_value = Decimal('10000.00')
        risk_per_trade = self.trading.risk_per_trade
        max_loss = account_value * risk_per_trade
        self.assertLessEqual(max_loss, Decimal('100.00'))  # 1% max risk

        # Test stop loss
        position_size = Decimal('1000.00')
        stop_loss = position_size * self.trading.stop_loss_percent
        self.assertEqual(stop_loss, Decimal('20.00'))  # 2% stop loss

    @patch('trading.ai_trading.make_trade_prediction')
    def test_trading_strategy(self, mock_predict):
        """Test trading strategy logic"""
        mock_predict.return_value = ('BUY', 0.75)
        
        # Test strategy with mock market data
        test_data = {
            'close': [100, 101, 102, 103, 104],
            'volume': [1000, 1100, 1200, 1300, 1400]
        }
        
        signal, confidence = make_trade_prediction(None, test_data)
        self.assertEqual(signal, 'BUY')
        self.assertGreater(confidence, 0.7)

    @patch('trading.alpaca_client.AlpacaClient')
    def test_order_execution(self, mock_alpaca):
        """Test order execution"""
        mock_alpaca.return_value.place_order.return_value = {
            'id': '12345',
            'status': 'filled',
            'filled_qty': '100',
            'filled_avg_price': '150.00'
        }
        
        # Test order placement
        order = self.trading.alpaca.place_order('AAPL', 100, 'buy', 'market')
        self.assertEqual(order['status'], 'filled')
        self.assertEqual(order['filled_qty'], '100')

class TestAlpacaClient(TestCase):
    def setUp(self):
        self.client = AlpacaClient()

    @patch('alpaca_trade_api.REST')
    def test_account_info(self, mock_rest):
        """Test account information retrieval"""
        mock_rest.return_value.get_account.return_value = MagicMock(
            cash='10000.00',
            portfolio_value='15000.00',
            buying_power='20000.00'
        )
        
        account = self.client.get_account()
        self.assertEqual(account['cash'], Decimal('10000.00'))
        self.assertEqual(account['portfolio_value'], Decimal('15000.00'))

    @patch('alpaca_trade_api.REST')
    def test_error_handling(self, mock_rest):
        """Test API error handling"""
        mock_rest.return_value.get_account.side_effect = Exception('API Error')
        
        with self.assertRaises(Exception):
            self.client.get_account()

if __name__ == '__main__':
    unittest.main()
