from django import forms
from django.contrib.auth.models import User
from .models import UserProfile
from django.contrib.auth.forms import UserCreationForm
from datetime import date

class UserForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email']

class UserProfileForm(forms.ModelForm):
    class Meta:
        model = UserProfile
        fields = ['avatar', 'bio', 'phone_number', 'country', 'city', 'trading_experience', 'risk_tolerance', 'preferred_currency']
        widgets = {
            'bio': forms.Textarea(attrs={'rows': 4}),
            'trading_experience': forms.Select(choices=UserProfile.TRADING_EXPERIENCE_CHOICES),
            'risk_tolerance': forms.Select(choices=UserProfile.RISK_TOLERANCE_CHOICES),
            'preferred_currency': forms.Select(choices=UserProfile.CURRENCY_CHOICES),
        }

class UserRegistrationForm(UserCreationForm):
    email = forms.EmailField(required=True)
    first_name = forms.CharField(required=True)
    last_name = forms.CharField(required=True)
    date_of_birth = forms.DateField(
        widget=forms.DateInput(attrs={'type': 'date'}),
        required=True
    )
    phone_number = forms.CharField(required=False)
    avatar = forms.ImageField(required=False)
    bio = forms.CharField(
        widget=forms.Textarea(attrs={'rows': 3}),
        required=False
    )
    country = forms.CharField(required=False)
    city = forms.CharField(required=False)
    trading_experience = forms.ChoiceField(
        choices=UserProfile._meta.get_field('trading_experience').choices,
        required=True
    )
    risk_tolerance = forms.ChoiceField(
        choices=UserProfile._meta.get_field('risk_tolerance').choices,
        required=True
    )
    preferred_currency = forms.ChoiceField(
        choices=UserProfile._meta.get_field('preferred_currency').choices,
        required=True
    )

    class Meta:
        model = User
        fields = ('username', 'email', 'first_name', 'last_name', 'password1', 'password2')

    def clean_date_of_birth(self):
        dob = self.cleaned_data['date_of_birth']
        today = date.today()
        age = today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
        if age < 18:
            raise forms.ValidationError('You must be at least 18 years old to register.')
        return dob

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        user.first_name = self.cleaned_data['first_name']
        user.last_name = self.cleaned_data['last_name']
        
        if commit:
            user.save()
            user_profile = user.userprofile
            user_profile.date_of_birth = self.cleaned_data['date_of_birth']
            user_profile.phone_number = self.cleaned_data['phone_number']
            user_profile.avatar = self.cleaned_data.get('avatar')
            user_profile.bio = self.cleaned_data['bio']
            user_profile.country = self.cleaned_data['country']
            user_profile.city = self.cleaned_data['city']
            user_profile.trading_experience = self.cleaned_data['trading_experience']
            user_profile.risk_tolerance = self.cleaned_data['risk_tolerance']
            user_profile.preferred_currency = self.cleaned_data['preferred_currency']
            user_profile.save()
        
        return user
