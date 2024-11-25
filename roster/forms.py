from importlib.metadata import requires

from django import forms
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError


alphabet = 'абвгґдеєжзиіїйклмнопрстуфхцчшщьюя'


class EnterForm(forms.Form):
    surname = forms.CharField(label="Прізвище", max_length=100)
    name = forms.CharField(label="Імʼя", max_length=100)
    username = forms.CharField(label="Логін", max_length=100, required=False)
    uid = forms.IntegerField(label="UserId", required=False)
    email = forms.EmailField(label="Email", required=False)

    # def clean_email(self):
        # email = self.cleaned_data['email']
        # if User.objects.filter(email=email).exists():
        #     raise ValidationError("Email already exists")
        # return email

    def clean_surname(self):
        surname = self.cleaned_data['surname']
        surname = self.validate_name(surname)
        return surname

    def clean_name(self):
        name = self.cleaned_data['name']
        name = self.validate_name(name)
        return name

    def clean_username(self):
        username = self.cleaned_data['username']
        username = username.strip()

        # no spaces
        if ' ' in username:
            raise forms.ValidationError("Логін не може містити пробіли")

        # only english letters and digits
        if any(not (char.isalnum() or char == '_') for char in username):
            raise forms.ValidationError("Логін може містити тільки англійські літери, цифри")

        return username

    def validate_name(self, name):
        name = name.strip()

        name = f"{name[0].upper()}{name[1:]}"

        if not name:
            raise forms.ValidationError("Ім'я не може бути пустим")

        # if contains digits
        if any(char.isdigit() for char in name):
            raise forms.ValidationError("Ім'я не може містити цифри")

        # should be cyrillic only
        if any(not (char.lower() in alphabet or char in ['-', '`\'', 'ʼ']) for char in name):
            raise forms.ValidationError("Ім'я повинно бути українською без інших символів")

        return name
#
#
# class FillDataForm(forms.Form):
#     username = forms.CharField(label="Логін", max_length=100, required=True)
#     email = forms.EmailField(label="Email", required=True)
#
#     def clean_email(self):
#         email = self.cleaned_data['email']
#         return email
