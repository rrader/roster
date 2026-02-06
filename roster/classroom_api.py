import datetime
import re
from collections import defaultdict

from django.conf import settings
from django.contrib.auth.models import User
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
import json

from roster.models import WorkplaceUserPlacement, Classroom
from roster.features import check_group_constraints
from roster.views import current_lesson, sort_ukrainian


def serialize_placement(placement):
    """Serialize a WorkplaceUserPlacement object to JSON-friendly dict"""
    return {
        'id': placement.id,
        'user': {
            'id': placement.user.id,
            'first_name': placement.user.first_name,
            'last_name': placement.user.last_name,
            'username': placement.user.username,
        },
        'workplace_id': placement.workplace_id,
        'created_at': placement.created_at.isoformat(),
    }


@require_http_methods(["GET"])
def get_classroom_329(request):
    """
    GET /api/classrooms/329/
    Retrieve classroom 329 state with optional filters
    """
    # Get filter parameters
    today = datetime.date.today().strftime('%Y-%m-%d')
    date_str = request.GET.get('date', today)
    singles = request.GET.get('singles', 'off') == 'on'
    
    try:
        date = datetime.datetime.strptime(date_str, '%Y-%m-%d').date()
    except ValueError:
        return JsonResponse({'error': 'Invalid date format. Use YYYY-MM-DD'}, status=400)
    
    lesson = int(request.GET.get('lesson', current_lesson(datetime.datetime.now())))
    
    if lesson < 0 or lesson > 7:
        return JsonResponse({'error': 'Lesson must be between 0 and 7'}, status=400)
    
    # Calculate lesson range
    if singles:
        lesson_from = lesson
        lesson_to = lesson
    else:
        # For paired lessons: lesson 0 -> 0-1, lesson 2 -> 2-3, etc.
        lesson_from = lesson
        lesson_to = lesson + 1
    
    # Get lesson times
    lesson_start = datetime.datetime.combine(date, settings.LESSONS_SCHEDULE[lesson_from]['start'])
    lesson_end = datetime.datetime.combine(date, settings.LESSONS_SCHEDULE[lesson_to]['end'])
    
    # Query placements
    placements = WorkplaceUserPlacement.objects.filter(
        created_at__gte=lesson_start,
        created_at__lte=lesson_end
    ).select_related('user').order_by('created_at')
    
    # Group by workplace
    uniq = 0
    usernames = []
    classroom = defaultdict(list)
    
    for p in placements:
        regex = r'.*-(\d+)'
        if m := re.match(regex, p.workplace_id):
            n = int(m.group(1))
            # Only add if user not already in this workplace
            if p.user.id not in [x.user.id for x in classroom[n]]:
                classroom[n].append(p)
        else:
            classroom['other'].append(p)
        
        name = f"{p.user.last_name} {p.user.first_name}"
        if name not in usernames:
            uniq += 1
            usernames.append(name)
    
    # Format workplace groups
    g1 = []
    for i in range(9, 0, -1):
        g1.append({
            'number': i,
            'placements': [serialize_placement(p) for p in classroom[i]]
        })
    
    g2 = []
    for i in range(10, 19):
        g2.append({
            'number': i,
            'placements': [serialize_placement(p) for p in classroom[i]]
        })
    
    # Get classroom settings
    classroom, _ = Classroom.objects.get_or_create(
        classroom_id='329',
        defaults={'screenshots_enabled': True}
    )
    
    return JsonResponse({
        'classroom_id': 329,
        'date': date_str,
        'lesson': lesson,
        'singles': singles,
        'lesson_from': lesson_from,
        'lesson_to': lesson_to,
        'lesson_start': lesson_start.isoformat(),
        'lesson_end': lesson_end.isoformat(),
        'workplaces_1': g1,
        'workplaces_2': g2,
        'unique_users_count': uniq,
        'usernames': sort_ukrainian(usernames),
        'last_updated': datetime.datetime.now().isoformat(),
        'screenshots_enabled': classroom.screenshots_enabled,
    })


@csrf_exempt
@require_http_methods(["POST"])
def assign_workplace_329(request, workplace_id):
    """
    POST /api/classrooms/329/workplaces/<workplace_id>/assign/
    Assign a user to a workplace
    """
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)
    
    # Get user
    user_id = data.get('user_id')
    username = data.get('username')
    
    if not user_id and not username:
        return JsonResponse({'error': 'Either user_id or username is required'}, status=400)
    
    try:
        if user_id:
            user = User.objects.get(id=user_id)
        else:
            user = User.objects.get(username=username)
    except User.DoesNotExist:
        return JsonResponse({'error': 'User not found'}, status=404)
    
    # Check group constraints
    allowed, error_msg = check_group_constraints(user, workplace_id)
    if not allowed:
        return JsonResponse({'error': error_msg}, status=403)
    
    # Create placement
    placement = WorkplaceUserPlacement.objects.create(
        user=user,
        workplace_id=workplace_id
    )
    
    return JsonResponse({
        'success': True,
        'placement': serialize_placement(placement)
    }, status=201)


@csrf_exempt
@require_http_methods(["DELETE"])
def remove_workplace_329(request, workplace_id):
    """
    DELETE /api/classrooms/329/workplaces/<workplace_id>/?placement_id=<id>
    Remove a specific placement by ID, or the most recent if no ID provided
    """
    placement_id = request.GET.get('placement_id')
    
    try:
        if placement_id:
            # Delete specific placement by ID
            try:
                placement = WorkplaceUserPlacement.objects.get(
                    id=placement_id,
                    workplace_id=workplace_id
                )
            except WorkplaceUserPlacement.DoesNotExist:
                return JsonResponse({'error': 'Placement not found'}, status=404)
        else:
            # Get the most recent placement for this workplace (backward compatibility)
            placement = WorkplaceUserPlacement.objects.filter(
                workplace_id=workplace_id
            ).order_by('-created_at').first()
            
            if not placement:
                return JsonResponse({'error': 'No placement found for this workplace'}, status=404)
        
        placement_data = serialize_placement(placement)
        placement.delete()
        
        return JsonResponse({
            'success': True,
            'removed_placement': placement_data
        })
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@csrf_exempt
@require_http_methods(["GET", "PATCH"])
def manage_screenshots_329(request):
    """
    GET /api/classrooms/329/screenshots/
    Returns current screenshot status
    
    PATCH /api/classrooms/329/screenshots/
    Updates screenshot status with JSON body: {"screenshots_enabled": true/false}
    """
    classroom, _ = Classroom.objects.get_or_create(
        classroom_id='329',
        defaults={'screenshots_enabled': True}
    )
    
    if request.method == 'GET':
        return JsonResponse({
            'classroom_id': '329',
            'screenshots_enabled': classroom.screenshots_enabled,
        })
    
    elif request.method == 'PATCH':
        try:
            data = json.loads(request.body)
            screenshots_enabled = data.get('screenshots_enabled')
            
            if screenshots_enabled is None:
                return JsonResponse({'error': 'screenshots_enabled is required'}, status=400)
            
            if not isinstance(screenshots_enabled, bool):
                return JsonResponse({'error': 'screenshots_enabled must be a boolean'}, status=400)
            
            classroom.screenshots_enabled = screenshots_enabled
            classroom.save()
            
            return JsonResponse({
                'success': True,
                'classroom_id': '329',
                'screenshots_enabled': classroom.screenshots_enabled,
            })
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON'}, status=400)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)


@require_http_methods(["GET"])
def screenshots_status_329(request):
    """
    GET /api/classrooms/329/screenshots/status/
    Simple endpoint for PowerShell scripts - returns "1" if enabled, "0" if disabled
    """
    classroom, _ = Classroom.objects.get_or_create(
        classroom_id='329',
        defaults={'screenshots_enabled': True}
    )
    
    return HttpResponse("1" if classroom.screenshots_enabled else "0", content_type="text/plain")
