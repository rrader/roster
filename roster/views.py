import logging
import os
import uuid

import requests
from dotenv import load_dotenv

from django.contrib.auth.models import User
from django.http import JsonResponse
from django.shortcuts import render, redirect
from django.utils.translation import activate
from django.conf import settings
from translitua import translit

from roster.forms import EnterForm, KeyForm

from fuzzy_match import algorithims

from roster.models import WorkplaceUserPlacement

logger = logging.getLogger(__name__)

load_dotenv()


def make_username(name, surname, uid):
    # convert to lowercase, latin and remove spaces
    name_c = translit(name.lower().replace(' ', ''))
    surname_c = translit(surname.lower().replace(' ', ''))

    username = ''.join(c for c in f"{name_c[0]}{surname_c}" if c.isalpha()) + f"{uid}"
    return username


def try_fuzzy_match(form):
    surname = form.cleaned_data['surname']
    users = User.objects.filter(last_name__istartswith=surname[0])

    matched = []
    for user in users:
        d = algorithims.levenshtein(surname, user.last_name)
        if d >= 0.6:
            matched.append((user, d))

    # sort by distance
    return [k for k, v in sorted(matched, key=lambda item: item[1], reverse=True)]


def try_exact_match(form):
    surname = form.cleaned_data['surname']
    name = form.cleaned_data['name']
    try:
        user = User.objects.get(last_name=surname, first_name=name)
    except User.DoesNotExist:
        return None
    return user


def index(request):
    activate('uk')
    wantsurl = request.GET.get('wantsurl', '')
    workplace_id = request.COOKIES.get('WorkplaceId', '')

    if request.method == "POST":
        form = EnterForm(request.POST)
        if form.is_valid():
            if form.cleaned_data['uid'] and form.cleaned_data['uid'] > 0:
                the_user = User.objects.get(id=form.cleaned_data['uid'])

            elif form.cleaned_data['username'] == "__NEW__":

                return render(request, 'index.html', {
                    'form': form,
                    'ask_new_account': True,
                    'disable': True,
                    'wantsurl': wantsurl,
                    'workplace_id': workplace_id,
                })

            elif form.cleaned_data['uid'] == 0 and form.cleaned_data['username'] == "__CONFIRM__":
                if User.objects.filter(email=form.cleaned_data['email']).exists():
                    propose = User.objects.filter(email=form.cleaned_data['email'])
                    return render(request, 'index.html', {
                        'error': True,
                        'errortext': 'Користувач з такою поштою вже існує',
                        'ask_new_account': True,
                        'form': form,
                        'proposed_users': propose,
                        'disable': True,
                        'wantsurl': wantsurl,
                        'workplace_id': workplace_id,
                    })
                # return render(request, 'index.html', {'form': form, 'disable': True})
                # user should be created
                the_user = User.objects.create_user(
                    first_name=form.cleaned_data['name'],
                    last_name=form.cleaned_data['surname'],
                    username=uuid.uuid4(),
                    email=form.cleaned_data['email']
                )

                uid = the_user.id
                the_user.username = make_username(form.cleaned_data['name'], form.cleaned_data['surname'], uid)
                the_user.save()
            else:
                # try matching
                the_user = try_exact_match(form)
                if not the_user:
                    propose = try_fuzzy_match(form)

                    return render(request, 'index.html', {
                        'form': form,
                        'ask_new_account': True,
                        'proposed_users': propose,
                        'disable': True,
                        'wantsurl': wantsurl,
                        'workplace_id': workplace_id,
                    })

            if the_user.username == 'admin':
                return redirect(f'/key_required/{the_user.id}/')

            # create WorkplaceUserPlacement record
            if workplace_id:
                placement = WorkplaceUserPlacement.objects.create(user=the_user, workplace_id=workplace_id)
                placement.save()

            url = moodle_auth(the_user.first_name, the_user.last_name, the_user.username, the_user.email, wantsurl)
            return redirect(url)
        else:
            return render(request, 'index.html', {
                'error': form.errors.as_data(),
                'form': form,
                'wantsurl': wantsurl,
                'workplace_id': workplace_id,
            })

    else:
        form = EnterForm()

    return render(request, 'index.html', {
        "form": form,
        'wantsurl': wantsurl,
        'workplace_id': workplace_id,
    })


def search_users_ajax(request):
    surname = request.GET.get('surname')
    data = {}

    if surname:
        users = User.objects.filter(last_name__icontains=surname.capitalize())
        data = [user_json(user) for user in users]

    return JsonResponse(data, safe=False)


def user_json(user):
    return {'surname': user.last_name, 'name': user.first_name}


def moodle_auth(name, surname, username, email, wantsurl):
    domainname = os.environ['MOODLE_URL']
    functionname = 'auth_userkey_request_login_url'
    # dotenv
    token = os.environ['MOODLE_TOKEN']
    serverurl = f'{domainname}/webservice/rest/server.php?wstoken={token}&wsfunction={functionname}&moodlewsrestformat=json'

    param = {
        "user[username]": username,
        "user[email]": email,
        "user[firstname]": name,
        "user[lastname]": surname,
    }

    try:
        response = requests.post(serverurl, data=param)
        resp_content = response.json()
        if resp_content and 'loginurl' in resp_content:
            logger.info("Login to Moodle was successful.")

            loginurl = resp_content['loginurl']
            if wantsurl:
                loginurl += f'&wantsurl={wantsurl}'
            return loginurl
        else:
            raise ValueError(f"Error during request to Moodle: {resp_content}")
    except Exception as e:
        logger.exception(f"Error during request to Moodle: {e}")
        raise ValueError(e)


def key_required(request, uid):
    activate('uk')
    the_user = User.objects.get(id=uid)

    if request.method == "POST":
        form = KeyForm(request.POST)
        if form.is_valid():
            if the_user.username == 'admin' and form.cleaned_data['key'] == os.environ['MOODLE_ADMIN_PASSWORD']:
                url = moodle_auth(the_user.first_name, the_user.last_name, the_user.username, the_user.email, '')
                return redirect(url)
            else:
                return render(request, 'key.html', {'error': True, 'errortext': 'Невідомий користувач', 'form': form, "the_user": the_user})
        else:
            return render(request, 'key.html', {'error': form.errors.as_data(), 'form': form, "the_user": the_user})

    else:
        form = KeyForm()

    return render(request, 'key.html', {"form": form, "the_user": the_user})


def classroom_workplace_login(request, workplace_id):
    activate('uk')

    response = redirect(settings.CLASSROOM_URL)
    response.set_cookie('WorkplaceId', workplace_id, samesite='None', secure=True)
    return response
