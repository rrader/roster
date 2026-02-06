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
    
    # Calculate lesson offset
    # Frontend sends 0-based index where 0 = "1st lesson"
    # Settings has 0-th lesson (8:00), so "1st lesson" is at key 1
    # We need to shift everything by +1
    
    # Default: current_lesson returns settings key
    default_lesson_fe = current_lesson(datetime.datetime.now())
    if default_lesson_fe < 0: default_lesson_fe = 0
    
    lesson = int(request.GET.get('lesson', default_lesson_fe))
    
    if lesson < 0 or lesson > 7:
        return JsonResponse({'error': 'Lesson must be between 0 and 7'}, status=400)
    
    # Calculate lesson range (keys in settings)
    base_idx = lesson + 1
    
    if singles:
        lesson_from = base_idx
        lesson_to = base_idx
    else:
        # For paired lessons: 
        # FE 0 ("1-2") -> keys 1, 2
        # FE 6 ("7-8") -> keys 7, 8
        lesson_from = base_idx
        lesson_to = base_idx + 1
    
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


@csrf_exempt
@require_http_methods(["POST"])
def upload_screenshot_329(request, workplace_id):
    """
    POST /api/classrooms/329/workplaces/<workplace_id>/screenshot/
    Uploads a screenshot for the workplace
    """
    import os
    import glob
    import re
    from roster.models import Workplace
    
    # Extract directory name logic
    match = re.search(r'-(\d+)', workplace_id)
    if match:
        workplace_dir_name = match.group(1)
    else:
        workplace_dir_name = workplace_id

    if 'file' not in request.FILES:
        return JsonResponse({'error': 'No file part'}, status=400)
    
    file = request.FILES['file']
    if file.name == '':
        return JsonResponse({'error': 'No selected file'}, status=400)
    
    # Create directory if not exists
    dir_path = os.path.join(settings.BASE_DIR, 'data', 'screenshots', str(workplace_dir_name))
    os.makedirs(dir_path, exist_ok=True)
    
    # Generate filename with timestamp
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{timestamp}.png"
    file_path = os.path.join(dir_path, filename)
    
    try:
        with open(file_path, 'wb+') as destination:
            for chunk in file.chunks():
                destination.write(chunk)
    except Exception as e:
        return JsonResponse({'error': f'Failed to write file: {str(e)}'}, status=500)
        
    # Validation logic: keep only last 100 screenshots
    try:
        files = glob.glob(os.path.join(dir_path, "*.png"))
        files.sort(key=os.path.getmtime)
        
        if len(files) > 100:
            for f in files[:-100]:
                os.remove(f)
    except Exception as e:
        # Don't fail the request if rotation fails, but maybe log it
        print(f"Error rotating screenshots: {e}")

    # Update database only if we have a valid numbered workplace (1-18)
    try:
        workplace_num = int(workplace_dir_name)
        if 1 <= workplace_num <= 18:
            workplace, _ = Workplace.objects.get_or_create(workplace_number=workplace_num)
            workplace.last_screenshot_at = datetime.datetime.now()
            workplace.last_screenshot_filename = filename
            workplace.save()
    except ValueError:
        pass # Not a numbered workplace, just skip DB update
    
    return JsonResponse({
        'success': True,
        'workplace_dir': workplace_dir_name,
        'filename': filename
    })
