from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth.models import User
from django.db import models


# Model to extend the User model with additional trading-related fields
class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    phone_number = models.CharField(max_length=15, blank=True)
    date_of_birth = models.DateField(null=True, blank=True)
    verified = models.BooleanField(default=False)

    def __str__(self):
        return self.user.username


# Model to track account balances in multiple currencies
class AccountBalance(models.Model):
    user = models.OneToOneField(UserProfile, on_delete=models.CASCADE)
    balance_usd = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    balance_gbp = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)

    def __str__(self):
        return f"{self.user.user.username}'s balance"


# Model to track individual trades made by the AI
class Trade(models.Model):
    user = models.ForeignKey(UserProfile, on_delete=models.CASCADE)
    trade_time = models.DateTimeField(auto_now_add=True)
    asset = models.CharField(max_length=100)  # The asset being traded (e.g., stock, forex pair)
    trade_type = models.CharField(max_length=10, choices=[('buy', 'Buy'), ('sell', 'Sell')])
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    profit_or_loss = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)

    def __str__(self):
        return f"Trade by {self.user.user.username} on {self.trade_time}"


# Model to track user transactions such as deposits, withdrawals, and trade activity
class TransactionHistory(models.Model):
    TRANSACTION_CHOICES = [
        ('deposit', 'Deposit'),
        ('withdrawal', 'Withdrawal'),
        ('trade', 'Trade'),
    ]

    user = models.ForeignKey(UserProfile, on_delete=models.CASCADE)
    transaction_type = models.CharField(max_length=10, choices=TRANSACTION_CHOICES)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    transaction_time = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.transaction_type.capitalize()} - {self.amount} by {self.user.user.username}"


@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        UserProfile.objects.create(user=instance)
        AccountBalance.objects.create(user=user_profile)


@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    instance.userprofile.save()
