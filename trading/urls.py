from django.urls import path, include
from . import views
from paypal.standard.ipn import views as paypal_views

urlpatterns = [
    path('dashboard/', views.user_dashboard, name='user_dashboard'),
    path('admin-dashboard/', views.admin_dashboard, name='admin_dashboard'),
    path('admin-transactions/', views.admin_transactions, name='admin_transactions'),
    path('profile/', views.profile, name='profile'),
    path('profile/edit/', views.edit_profile, name='edit_profile'),
    path('execute_trade/', views.execute_trade, name='execute_trade'),
    
    path('paypal/', include('paypal.standard.ipn.urls')),  # PayPal IPN URLs
    path('paypal-deposit/', views.paypal_deposit, name='paypal_deposit'),
    path('stripe-checkout/', views.stripe_checkout, name='stripe_checkout'),
]