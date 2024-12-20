from django import forms
from django.conf import settings


alphabet = 'абвгґдеєжзиіїйклмнопрстуфхцчшщьюя'


class EnterForm(forms.Form):
    surname = forms.CharField(label="Прізвище", max_length=100)
    name = forms.CharField(label="Імʼя", max_length=100)
    username = forms.CharField(label="Логін", max_length=100, required=False)
    uid = forms.IntegerField(label="UserId", required=False)
    email = forms.EmailField(label="Email", required=False)
    workplace_id = forms.CharField(label="WorkplaceId", required=False)
    access_key = forms.CharField(label="Ключ доступу", required=True)

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

    def clean_access_key(self):
        key = self.cleaned_data['access_key']
        if key != settings.ACCESS_KEY:
            raise forms.ValidationError("Помилковий ключ доступу")
        return key


class KeyForm(forms.Form):
    username = forms.CharField(label="Логін", max_length=100, required=True)
    uid = forms.IntegerField(label="UserId", required=True)
    key = forms.CharField(label="Ключ", required=True)
