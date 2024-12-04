from django.urls import path, include
from . import views
from paypal.standard.ipn import views as paypal_views

urlpatterns = [
    path('', views.home, name='home'),
    path('dashboard/', views.user_dashboard, name='user_dashboard'),
    path('profile/', views.profile, name='profile'),
    path('profile/edit/', views.edit_profile, name='edit_profile'),
    path('deposit/paypal/', views.paypal_deposit, name='paypal_deposit'),
    path('deposit/stripe/', views.stripe_checkout, name='stripe_checkout'),
    path('payment/success/', views.payment_success, name='payment_success'),
    path('payment/cancelled/', views.payment_cancelled, name='payment_cancelled'),
    path('payment/success/stripe/', views.payment_success_stripe, name='payment_success_stripe'),
    path('handle-asset/', views.handle_selected_asset, name='handle_selected_asset'),
    
    # New automated trading endpoints
    path('api/start-trading/', views.start_automated_trading, name='start_trading'),
    path('api/stop-trading/', views.stop_automated_trading, name='stop_trading'),
    path('api/trading-status/', views.get_trading_status, name='trading_status'),
    path('api/manual-trade/', views.manual_trade, name='manual_trade'),
    path('api/market-data/', views.get_market_data, name='market_data'),
    path('api/trading-news/', views.get_trading_news, name='trading_news'),
    path('api/process-deposit/', views.process_deposit, name='process_deposit'),
    path('api/process-withdrawal/', views.process_withdrawal, name='process_withdrawal'),
    path('admin-dashboard/', views.admin_dashboard, name='admin_dashboard'),
    path('admin-transactions/', views.admin_transactions, name='admin_transactions'),
    path('execute_trade/', views.execute_trade, name='execute_trade'),
    path('paypal/', include('paypal.standard.ipn.urls')),  # PayPal IPN URLs
]