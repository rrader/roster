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



# Helper for screenshot rotation
def rotate_screenshots(dir_path, workplace=None):
    """
    Implements smart retention policy:
    1. Keep 100 most recent files as is.
    2. For older files (index >= 100):
       - Keep only one file every 15 mins (based on timestamp in filename).
       - Delete others (and their DB records).
       - If kept file > 50KB, compress/resize it.
    """
    import glob
    import os
    import re
    import datetime
    from PIL import Image
    from roster.models import WorkplaceScreenshot

    try:
        files = glob.glob(os.path.join(dir_path, "*.png"))
        # Sort by modification time, newest first
        files.sort(key=os.path.getmtime, reverse=True)
        
        # files[0] is newest
        
        # We only care if we have more than 100 files
        if len(files) <= 100:
            return

        # Indices 0..99 are kept safe (recent)
        
        # Process older files
        last_kept_time = None
        
        for i in range(100, len(files)):
            file_path = files[i]
            basename = os.path.basename(file_path)
            
            # Policy: Keep one every 15 minutes of "file timestamp"
            # Filename format: YYYYMMDD_HHMMSS.png
            should_delete = False
            
            try:
                # Parse time from filename
                match = re.match(r'^(\d{8}_(\d{4}))\d{2}\.png$', basename)
                if not match:
                     # Unknown format, maybe keep it to be safe? Or delete?
                     # Let's delete to be clean if it's old
                     should_delete = True
                else:
                    ts_str = basename.split('.')[0]
                    dt = datetime.datetime.strptime(ts_str, "%Y%m%d_%H%M%S")
                    
                    if dt < datetime.datetime.now() - datetime.timedelta(days=365):
                        should_delete = True
                    elif last_kept_time is None:
                        # This is the newest of the "old" batch. Keep it.
                        last_kept_time = dt
                    else:
                        # Calculate difference
                        diff = abs((last_kept_time - dt).total_seconds())
                        if diff < 15 * 60: # 15 minutes
                            should_delete = True
                        else:
                            # Keep it
                            last_kept_time = dt
                            
            except ValueError:
                 should_delete = True
            
            if should_delete:
                try:
                    os.remove(file_path)
                    # Sync with DB
                    if workplace:
                        WorkplaceScreenshot.objects.filter(
                            workplace=workplace, 
                            screenshot_filename=basename
                        ).delete()
                except OSError as e:
                    print(f"Error deleting {file_path}: {e}")
                continue
            
            # It's a keeper check compression
            try:
                size = os.path.getsize(file_path)
                if size > 50 * 1024: # 50KB
                    # Compress
                    with Image.open(file_path) as img:
                        # As requested: "make smaller dimension"
                        w, h = img.size
                        new_w = int(w * 0.5)
                        new_h = int(h * 0.5)
                        
                        resized = img.resize((new_w, new_h), Image.Resampling.LANCZOS)
                        resized.save(file_path, optimize=True, quality=85)
            except Exception as e:
                print(f"Error compressing {file_path}: {e}")

    except Exception as e:
        print(f"Error in rotate_screenshots: {e}")

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
    # Frontend sends 1-based index where 1 = "1st lesson"
    # Settings has 0-th lesson (8:00), so "1st lesson" is at key 1
    
    # Default: current_lesson returns settings key (1-based)
    curr_lesson_1based = current_lesson(datetime.datetime.now())
    if curr_lesson_1based < 1: curr_lesson_1based = 1 # Safety
    
    if singles:
        # Map 1-based directly
        default_lesson_fe = curr_lesson_1based
    else:
        # Paired mode: Snap to pair start (1, 3, 5...)
        # 1,2 -> 1 ('1-2')
        # 3,4 -> 3 ('3-4')
        # 5,6 -> 5 ('5-6')
        default_lesson_fe = ((curr_lesson_1based - 1) // 2) * 2 + 1

    if default_lesson_fe < 1: default_lesson_fe = 1
    
    lesson = int(request.GET.get('lesson', default_lesson_fe))
    
    if lesson < 1 or lesson > 8:
        return JsonResponse({'error': 'Lesson must be between 1 and 8'}, status=400)
    
    # Calculate lesson range (keys in settings)
    base_idx = lesson
    
    if singles:
        lesson_from = base_idx
        lesson_to = base_idx
    else:
        # For paired lessons: 
        # FE 1 ("1-2") -> keys 1, 2
        # FE 3 ("3-4") -> keys 3, 4
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
    from roster.models import Workplace
    from django.db.models import OuterRef, Subquery
    from roster.models import WorkplaceScreenshot
    
    # Pre-fetch all workplaces info with latest screenshot
    newest = WorkplaceScreenshot.objects.filter(
        workplace=OuterRef('pk')
    ).order_by('-created_at')
    
    workplaces_qs = Workplace.objects.annotate(
        latest_filename=Subquery(newest.values('screenshot_filename')[:1]),
        latest_at=Subquery(newest.values('created_at')[:1])
    )
    workplaces_info = {w.workplace_number: w for w in workplaces_qs}

    def get_wp_data(i):
        w = workplaces_info.get(i)
        return {
            'number': i,
            'placements': [serialize_placement(p) for p in classroom[i]],
            'last_screenshot_filename': w.latest_filename if w else None,
            'last_screenshot_at': w.latest_at.isoformat() if w and w.latest_at else None
        }

    g1 = []
    for i in range(9, 0, -1):
        g1.append(get_wp_data(i))
    
    g2 = []
    for i in range(10, 19):
        g2.append(get_wp_data(i))
    
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
        workplace_dir_name = int(match.group(1))
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
        
    # Resolve workplace
    workplace = None
    try:
        workplace_num = int(workplace_dir_name)
        if 1 <= workplace_num <= 18:
            workplace, _ = Workplace.objects.get_or_create(workplace_number=workplace_num)
    except ValueError:
        pass

    # Validation logic: Smart Retention
    rotate_screenshots(dir_path, workplace)

    # Update database
    if workplace:
        # --- NEW: Create History Record ---
        from roster.models import WorkplaceScreenshot, WorkplaceUserPlacement
        
        # Find active user
        # Logic: Last placement created before now for this workplace
        active_user = None
        try:
            # Get the latest placement
            # Search for both 'N' and '329-N' formats
            from django.db.models import Q
            wp_str = str(workplace.workplace_number)
            last_placement = WorkplaceUserPlacement.objects.filter(
                Q(workplace_id=wp_str) | Q(workplace_id=f"329-{wp_str}")
            ).order_by('-created_at').first()
            
            if last_placement:
                # Optional: Check if placement is recent
                active_user = last_placement.user
        except Exception as e:
            print(f"Error finding user: {e}")
        
        WorkplaceScreenshot.objects.create(
            workplace=workplace,
            screenshot_filename=filename,
            user=active_user
        )
        # ----------------------------------
    
    return JsonResponse({
        'success': True,
        'workplace_dir': workplace_dir_name,
        'filename': filename
    })


@require_http_methods(["GET"])
def serve_screenshot_329(request, workplace_id, filename):
    """
    GET /api/classrooms/329/workplaces/<workplace_id>/screenshots/<filename>/
    Securely serves a screenshot file
    """
    import os
    from django.http import FileResponse, Http404
    
    # Basic validation of workplace_id to prevent directory traversal
    if not re.match(r'^[\w-]+$', workplace_id):
        raise Http404("Invalid workplace ID")
        
    # Validation of filename
    if not re.match(r'^[\w-]+\.png$', filename):
        raise Http404("Invalid filename")

    file_path = os.path.join(settings.BASE_DIR, 'data', 'screenshots', workplace_id, filename)
    
    if not os.path.exists(file_path):
        raise Http404("Screenshot not found")
        
    return FileResponse(open(file_path, 'rb'), content_type='image/png')


@require_http_methods(["GET"])
def list_screenshots_329(request, workplace_id):
    """
    GET /api/classrooms/329/workplaces/<workplace_id>/screenshots/
    Returns list of available screenshots for a workplace
    """
    import os
    import glob
    from roster.models import WorkplaceScreenshot, Workplace
    
    # Basic validation of workplace_id
    if not re.match(r'^[\w-]+$', workplace_id):
        return JsonResponse({'error': 'Invalid workplace ID'}, status=400)
    
    # Try to fetch from DB first (WorkplaceScreenshot)
    try:
        workplace_num = int(workplace_id)
        if 1 <= workplace_num <= 18:
            try:
                workplace = Workplace.objects.get(workplace_number=workplace_num)
                screenshots = WorkplaceScreenshot.objects.filter(workplace=workplace).select_related('user').order_by('-created_at')
                
                data = []
                for s in screenshots:
                    user_name = None
                    if s.user:
                        user_name = f"{s.user.last_name} {s.user.first_name}"
                        
                    data.append({
                        'filename': s.screenshot_filename,
                        'created_at': s.created_at.isoformat(),
                        'user_name': user_name
                    })
                
                # If we have DB records, return them
                if data:
                    return JsonResponse(data, safe=False)
            except Workplace.DoesNotExist:
                pass
    except ValueError:
        pass
    
    # Fallback to file system if no DB records found (backward compatibility)
    dir_path = os.path.join(settings.BASE_DIR, 'data', 'screenshots', workplace_id)
    
    if not os.path.exists(dir_path):
        return JsonResponse([])
        
    try:
        # Get all png files
        files = glob.glob(os.path.join(dir_path, "*.png"))
        # Sort by modification time (newest first)
        files.sort(key=os.path.getmtime, reverse=True)
        
        # Extract just filenames and return as objects (mocking the new structure)
        data = []
        for f in files:
            filename = os.path.basename(f)
            # Try to get timestamp from filename or mtime
            timestamp = datetime.datetime.fromtimestamp(os.path.getmtime(f)).isoformat()
            
            data.append({
                'filename': filename,
                'created_at': timestamp,
                'user_name': None # No user info for legacy files
            })
        
        return JsonResponse(data, safe=False)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)
