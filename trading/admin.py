from django.contrib import admin
from .models import UserProfile, AccountBalance, Trade, TransactionHistory

admin.site.register(UserProfile)
admin.site.register(AccountBalance)
admin.site.register(Trade)
admin.site.register(TransactionHistory)