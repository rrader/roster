from django import forms
from django.contrib.auth.models import User
from roster.models import StudentGroup


class StudentGroupForm(forms.ModelForm):
    """Form for creating and editing student groups"""
    
    class Meta:
        model = StudentGroup
        fields = ['name', 'description']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Введіть назву групи'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Опис групи (необов\'язково)'
            }),
        }


class AddStudentToGroupForm(forms.Form):
    """Form for adding a student to a group"""
    surname = forms.CharField(
        label="Прізвище",
        max_length=100,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Введіть прізвище учня'
        })
    )
    name = forms.CharField(
        label="Ім'я",
        max_length=100,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Введіть ім\'я учня (необов\'язково)'
        })
    )
    user_id = forms.IntegerField(
        widget=forms.HiddenInput(),
        required=False
    )

    def clean(self):
        cleaned_data = super().clean()
        user_id = cleaned_data.get('user_id')
        
        if user_id:
            try:
                user = User.objects.get(id=user_id)
                cleaned_data['user'] = user
            except User.DoesNotExist:
                raise forms.ValidationError("Користувача не знайдено")
        
        return cleaned_data


class StudentGroupFeatureForm(forms.Form):
    """Form for managing group features"""
    non_sequential = forms.BooleanField(
        label="Не садити поруч",
        required=False,
        help_text="Забороняє учням цієї групи сідати за комп'ютери поруч."
    )
    min_distance = forms.IntegerField(
        label="Мінімальна відстань",
        initial=1,
        min_value=1,
        required=False,
        help_text="Мінімальна різниця номерів комп'ютерів. 1 = не можна сусідні (1 і 2). 2 = не можна сусідні та через один (1 і 2, 1 і 3)."
    )
