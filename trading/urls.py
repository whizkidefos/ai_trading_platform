from django.urls import path, include
from . import views

app_name = 'trading'

urlpatterns = [
    # Main pages
    path('', views.home, name='home'),
    path('register/', views.register, name='register'),
    path('dashboard/', views.user_dashboard, name='user_dashboard'),  # Changed name to match template
    path('profile/', views.profile, name='profile'),
    path('profile/edit/', views.edit_profile, name='edit_profile'),
    
    # API endpoints - v1
    path('api/v1/trading/start/', views.start_trading, name='start_trading'),
    path('api/v1/trading/stop/', views.stop_trading, name='stop_trading'),
    path('api/v1/trading/update-parameters/', views.update_trading_parameters, name='update_trading_parameters'),
    path('api/v1/trading/status/', views.trading_status, name='trading_status'),
    path('api/v1/account/deposit/', views.process_deposit, name='api_deposit'),
    path('api/v1/account/withdraw/', views.process_withdrawal, name='api_withdraw'),
    
    # Asset info endpoint
    path('api/asset-info/', views.get_asset_info, name='get_asset_info'),
    
    # Regular payment endpoints
    path('deposit/', views.process_deposit, name='deposit'),
    path('withdraw/', views.process_withdrawal, name='withdraw'),
    path('paypal-ipn/', views.paypal_ipn, name='paypal-ipn'),
    path('paypal/', include('paypal.standard.ipn.urls')),
    
    # Success/Cancel pages
    path('deposit/success/', views.deposit_success, name='deposit_success'),
    path('deposit/cancelled/', views.deposit_cancelled, name='deposit_cancelled'),
]