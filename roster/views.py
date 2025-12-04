import datetime
import logging
import os
import re
import uuid
from collections import defaultdict

import requests
from dotenv import load_dotenv

from django.contrib.auth.models import User
from django.db import models
from django.http import JsonResponse
from django.shortcuts import render, redirect
from django.utils.translation import activate
from django.conf import settings
from translitua import translit

from roster.forms import EnterForm, KeyForm

from fuzzy_match import algorithims

from roster.models import WorkplaceUserPlacement, StudentGroup
from roster.group_forms import StudentGroupForm, AddStudentToGroupForm

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


from roster.features import check_group_constraints


def index(request):
    activate('uk')
    wantsurl = request.GET.get('wantsurl', '')
    theme = request.GET.get('theme', '')
    workplace_id = request.COOKIES.get('WorkplaceId', '')
    access_key_cookie = request.COOKIES.get('AccessKey', '')
    access_key = request.GET.get('access_key', access_key_cookie)

    if theme == 'cybermonth':
        template = 'cybermonth/index.html'
    else:
        template = 'index.html'

    if access_key != settings.ACCESS_KEY:
        access_key = ''

    if request.method == "POST":
        form = EnterForm(request.POST)
        if form.is_valid():
            if form.cleaned_data['uid'] and form.cleaned_data['uid'] > 0:
                the_user = User.objects.get(id=form.cleaned_data['uid'])

            elif form.cleaned_data['username'] == "__NEW__":

                return render(request, template, {
                    'form': form,
                    'ask_new_account': True,
                    'disable': True,
                    'wantsurl': wantsurl,
                    'workplace_id': workplace_id,
                    'access_key': access_key,
                })

            elif form.cleaned_data['uid'] == 0 and form.cleaned_data['username'] == "__CONFIRM__":
                if not form.cleaned_data['email']:
                    return render(request, template, {
                        'error': True,
                        'errortext': 'Потрібно вказати пошту',
                        'ask_new_account': True,
                        'form': form,
                        'disable': True,
                        'wantsurl': wantsurl,
                        'workplace_id': workplace_id,
                        'access_key': access_key,
                    })

                if User.objects.filter(email=form.cleaned_data['email']).exists():
                    propose = User.objects.filter(email=form.cleaned_data['email'])
                    return render(request, template, {
                        'error': True,
                        'errortext': 'Користувач з такою поштою вже існує',
                        'ask_new_account': True,
                        'form': form,
                        'proposed_users': propose,
                        'disable': True,
                        'wantsurl': wantsurl,
                        'workplace_id': workplace_id,
                        'access_key': access_key,
                    })

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

                    return render(request, template, {
                        'form': form,
                        'ask_new_account': True,
                        'proposed_users': propose,
                        'disable': True,
                        'wantsurl': wantsurl,
                        'workplace_id': workplace_id,
                        'access_key': access_key,
                    })

            if the_user.username == 'admin':
                response = redirect(f'/key_required/{the_user.id}/')
                response['Location'] += f'?wantsurl={wantsurl}'
            else:
                # create WorkplaceUserPlacement record
                if workplace_id:
                    # Check constraints
                    allowed, error_msg = check_group_constraints(the_user, workplace_id)
                    if not allowed:
                        return render(request, template, {
                            'error': True,
                            'errortext': error_msg,
                            'form': form,
                            'wantsurl': wantsurl,
                            'workplace_id': workplace_id,
                            'access_key': access_key,
                        })

                    placement = WorkplaceUserPlacement.objects.create(user=the_user, workplace_id=workplace_id)
                    placement.save()

                url = moodle_auth(the_user.first_name, the_user.last_name, the_user.username, the_user.email, wantsurl)
                response = redirect(url)

            response.set_cookie('AccessKey', form.cleaned_data['access_key'], samesite='None', secure=True)
            return response
        else:
            return render(request, template, {
                'error': form.errors.as_data(),
                'form': form,
                'wantsurl': wantsurl,
                'workplace_id': workplace_id,
                'access_key': access_key,
            })

    else:
        form = EnterForm()

    # Get suggested users for fast login if workplace_id is present
    suggested_users = []
    if workplace_id:
        suggested_users = get_suggested_users_for_workplace(workplace_id)

    response = render(request, template, {
        "form": form,
        'wantsurl': wantsurl,
        'workplace_id': workplace_id,
        'access_key': access_key,
        'suggested_users': suggested_users,
    })

    # clear the cookie
    response.set_cookie('MoodleSession', '', domain=f'.{settings.BASE_DOMAIN}')
    # set the access key cookie
    response.set_cookie('AccessKey', access_key, samesite='None', secure=True)
    return response


def search_users_ajax(request):
    surname = request.GET.get('surname')
    data = {}

    if surname:
        users = User.objects.filter(last_name__icontains=surname.capitalize())
        data = [user_json(user) for user in users]

    return JsonResponse(data, safe=False)


def user_json(user):
    return {
        'surname': user.last_name, 
        'name': user.first_name,
        'display': f"{user.last_name} {user.first_name}"
    }


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
    wantsurl = request.GET.get('wantsurl', '')
    the_user = User.objects.get(id=uid)

    if request.method == "POST":
        form = KeyForm(request.POST)
        if form.is_valid():
            if the_user.username == 'admin' and form.cleaned_data['key'] == os.environ['MOODLE_ADMIN_PASSWORD']:
                url = moodle_auth(the_user.first_name, the_user.last_name, the_user.username, the_user.email, wantsurl)
                return redirect(url)
            else:
                return render(request, 'key.html', {
                    'error': True,
                    'errortext': 'Невідомий користувач',
                    'form': form,
                    "the_user": the_user,
                    'wantsurl': wantsurl,
                })
        else:
            return render(request, 'key.html', {
                'wantsurl': wantsurl,
                'error': form.errors.as_data(),
                'form': form,
                "the_user": the_user,
            })

    else:
        form = KeyForm()

    return render(request, 'key.html', {"form": form, "the_user": the_user, 'wantsurl': wantsurl})


def classroom_workplace_login(request, workplace_id):
    activate('uk')
    access_key = request.GET.get('access_key', '')

    response = redirect(settings.CLASSROOM_URL)
    response.set_cookie('WorkplaceId', workplace_id, samesite='None', secure=True)
    response.set_cookie('AccessKey', access_key, samesite='None', secure=True)
    return response


def current_lesson(now):
    last = 0
    for lesson, times in settings.LESSONS_SCHEDULE.items():

        if now.time() >= times['start']:
            last = lesson

    return last


def get_suggested_users_for_workplace(workplace_id, limit=3):
    """
    Get top N users who most frequently use this workplace during the current time slot.
    Returns a list of User objects ordered by frequency of use.
    """
    if not workplace_id:
        return []
    
    now = datetime.datetime.now()
    lesson = current_lesson(now)
    
    if lesson == 0:
        return []
    
    # Get the time range for the current lesson
    lesson_data = settings.LESSONS_SCHEDULE.get(lesson)
    if not lesson_data:
        return []
    
    # Query placements for this workplace during similar time slots across all dates
    # We'll look at a broader time window to get historical data
    start_time = lesson_data['start']
    end_time = lesson_data['end']
    
    # Limit to last 3 months for better performance and relevance
    three_months_ago = now - datetime.timedelta(days=90)
    
    # Get all placements for this workplace in the last 3 months
    placements = WorkplaceUserPlacement.objects.filter(
        workplace_id=workplace_id,
        created_at__gte=three_months_ago
    ).select_related('user')
    
    # Filter by time of day (same lesson across different days)
    user_counts = defaultdict(int)
    for placement in placements:
        placement_time = placement.created_at.time()
        if start_time <= placement_time <= end_time:
            user_counts[placement.user] += 1
    
    # Sort by frequency and get top N
    sorted_users = sorted(user_counts.items(), key=lambda x: x[1], reverse=True)
    top_users = [user for user, count in sorted_users[:limit]]
    
    return top_users


def sort_ukrainian(usernames):
    alphabet = "абвгґдеєжзиіїйклмнопрстуфхцчшщьюя "
    return sorted(usernames, key=lambda x: [alphabet.index(c) for c in x.lower()[:2]])


def classroom(request):
    activate('uk')

    # default to today in YYYY-mm-dd format
    today: str = datetime.date.today().strftime('%Y-%m-%d')

    date_str: str = request.GET.get('date', today)
    singles: bool = request.GET.get('singles', 'off') == 'on'

    date: datetime.date = datetime.datetime.strptime(date_str, '%Y-%m-%d').date()
    lesson: int = int(request.GET.get('lesson', current_lesson(now = datetime.datetime.now())))

    if singles:
        lesson_from = lesson
        lesson_to = lesson
    else:
        lesson_from = max(1, lesson-1)
        lesson_to = lesson

    lesson_start = datetime.datetime.combine(date, settings.LESSONS_SCHEDULE[lesson_from - 1]['end'])
    lesson_end = datetime.datetime.combine(date, settings.LESSONS_SCHEDULE[lesson_to + 1]['start'])

    placements = WorkplaceUserPlacement.objects.filter(
        created_at__gte=lesson_start,
        created_at__lte=lesson_end
    ).order_by('created_at')

    uniq = 0
    usernames = []
    classroom = defaultdict(list)
    for p in placements:
        regex = r'.*-(\d+)'
        if m := re.match(regex, p.workplace_id):
            n = int(m.group(1))
            if p.user.id not in [x.user.id for x in classroom[n]]:
                classroom[n].append(p)
        else:
            classroom['other'].append(p)

        name = f"{p.user.last_name} {p.user.first_name}"
        if name not in usernames:
            uniq += 1
            usernames.append(name)

    g1 = []
    for i in range(9, 0, -1):
        g1.append((i, classroom[i]))

    g2 = []
    for i in range(10, 19):
        g2.append((i, classroom[i]))

    return render(request, 'classroom.html', {
        'date': date_str,
        'lesson': str(lesson),
        'singles': singles,
        'classroom_1': g1,
        'classroom_2': g2,
        'lesson_from': lesson_from,
        'lesson_to': lesson_to,
        'lesson_start': lesson_start,
        'lesson_end': lesson_end,
        'uniq': uniq,
        'usernames': sort_ukrainian(usernames),
    })


def logged_in(request):
    activate('uk')

    return render(request, 'logged_in.html')


# Student Groups Views

def groups_login(request):
    """Login page for groups management"""
    activate('uk')
    
    if request.session.get('groups_admin_authenticated'):
        return redirect('groups_list')
    
    if request.method == 'POST':
        password = request.POST.get('password', '')
        if password == os.environ.get('MOODLE_ADMIN_PASSWORD', ''):
            request.session['groups_admin_authenticated'] = True
            return redirect('groups_list')
        else:
            return render(request, 'groups_login.html', {
                'error': True,
                'errortext': 'Невірний пароль',
            })
    
    return render(request, 'groups_login.html')


def groups_logout(request):
    """Logout from groups management"""
    if 'groups_admin_authenticated' in request.session:
        del request.session['groups_admin_authenticated']
    return redirect('groups_login')


def groups_list(request):
    """Display list of all student groups"""
    activate('uk')
    
    if not request.session.get('groups_admin_authenticated'):
        return redirect('groups_login')

    groups = StudentGroup.objects.all().prefetch_related('students')
    
    return render(request, 'groups_list.html', {
        'groups': groups,
    })


def group_create(request):
    """Create a new student group"""
    activate('uk')
    
    if not request.session.get('groups_admin_authenticated'):
        return redirect('groups_login')

    if request.method == 'POST':
        form = StudentGroupForm(request.POST)
        if form.is_valid():
            group = form.save()
            return redirect('group_detail', group_id=group.id)
    else:
        form = StudentGroupForm()

    return render(request, 'group_form.html', {
        'form': form,
        'title': 'Створити нову групу',
    })


def group_detail(request, group_id):
    """Display group details and list of students"""
    activate('uk')
    
    if not request.session.get('groups_admin_authenticated'):
        return redirect('groups_login')

    try:
        group = StudentGroup.objects.prefetch_related('students').get(id=group_id)
    except StudentGroup.DoesNotExist:
        return redirect('groups_list')

    students = group.students.all().order_by('last_name', 'first_name')
    
    # Handle adding student
    add_form = AddStudentToGroupForm()
    proposed_users = []
    
    if request.method == 'POST':
        add_form = AddStudentToGroupForm(request.POST)
        if add_form.is_valid():
            if add_form.cleaned_data.get('user_id'):
                user = User.objects.get(id=add_form.cleaned_data['user_id'])
                if user not in group.students.all():
                    group.students.add(user)
                return redirect('group_detail', group_id=group.id)
            else:
                # Search for users
                surname = add_form.cleaned_data['surname']
                name = add_form.cleaned_data.get('name', '')
                
                if name:
                    proposed_users = User.objects.filter(
                        last_name__icontains=surname,
                        first_name__icontains=name
                    )
                else:
                    proposed_users = User.objects.filter(last_name__icontains=surname)
                
                proposed_users = proposed_users.order_by('last_name', 'first_name')[:10]

    return render(request, 'group_detail.html', {
        'group': group,
        'students': students,
        'add_form': add_form,
        'proposed_users': proposed_users,
    })


def group_edit(request, group_id):
    """Edit an existing student group"""
    activate('uk')
    
    if not request.session.get('groups_admin_authenticated'):
        return redirect('groups_login')

    try:
        group = StudentGroup.objects.get(id=group_id)
    except StudentGroup.DoesNotExist:
        return redirect('groups_list')

    from roster.group_forms import StudentGroupFeatureForm
    from roster.models import StudentGroupFeature

    if request.method == 'POST':
        form = StudentGroupForm(request.POST, instance=group)
        feature_form = StudentGroupFeatureForm(request.POST)
        
        if form.is_valid() and feature_form.is_valid():
            form.save()
            
            # Save features
            # Non-sequential
            ns_enabled = feature_form.cleaned_data.get('non_sequential', False)
            min_dist = feature_form.cleaned_data.get('min_distance', 1)
            
            feature, created = StudentGroupFeature.objects.get_or_create(
                group=group,
                feature_key='non_sequential',
                defaults={'enabled': ns_enabled}
            )
            feature.enabled = ns_enabled
            feature.parameters = {'min_distance': min_dist}
            feature.save()
            
            return redirect('group_detail', group_id=group.id)
    else:
        form = StudentGroupForm(instance=group)
        # Load initial feature state
        ns_feature = group.features.filter(feature_key='non_sequential').first()
        initial_features = {
            'non_sequential': ns_feature.enabled if ns_feature else False,
            'min_distance': ns_feature.parameters.get('min_distance', 1) if ns_feature else 1
        }
        feature_form = StudentGroupFeatureForm(initial=initial_features)

    return render(request, 'group_form.html', {
        'form': form,
        'feature_form': feature_form,
        'title': f'Редагувати групу: {group.name}',
        'group': group,
    })


def group_delete(request, group_id):
    """Delete a student group"""
    activate('uk')
    
    if not request.session.get('groups_admin_authenticated'):
        return redirect('groups_login')

    try:
        group = StudentGroup.objects.get(id=group_id)
        if request.method == 'POST':
            group.delete()
            return redirect('groups_list')
    except StudentGroup.DoesNotExist:
        pass

    return redirect('groups_list')


def group_remove_student(request, group_id, user_id):
    """Remove a student from a group"""
    activate('uk')
    
    if not request.session.get('groups_admin_authenticated'):
        return redirect('groups_login')

    try:
        group = StudentGroup.objects.get(id=group_id)
        user = User.objects.get(id=user_id)
        group.students.remove(user)
    except (StudentGroup.DoesNotExist, User.DoesNotExist):
        pass

    return redirect('group_detail', group_id=group_id)


