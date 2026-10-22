from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import UserCreationForm

User = get_user_model()


class SignupForm(UserCreationForm):
    nombre = forms.CharField(
        label="Nombre", max_length=120,
        widget=forms.TextInput(attrs={"placeholder": "Como quiere que lo llamemos", "autocomplete": "name"}))
    email = forms.EmailField(
        label="Correo electrónico",
        widget=forms.EmailInput(attrs={"placeholder": "usted@correo.com", "autocomplete": "email"}))
    consent = forms.BooleanField(
        label="Autorizo el tratamiento de mis datos personales con las finalidades descritas.",
        error_messages={"required": "Necesitamos su consentimiento para tratar sus datos."})

    class Meta:
        model = User
        fields = ("nombre", "email", "password1", "password2")

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("Ya existe una cuenta con ese correo.")
        return email

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data["email"]
        user.username = self.cleaned_data["email"]
        if commit:
            user.save()
        return user


class LeadForm(forms.Form):
    email = forms.EmailField(
        label="Correo",
        widget=forms.EmailInput(attrs={"placeholder": "usted@correo.com"}))
