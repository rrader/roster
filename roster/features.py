import re
import datetime
from django.conf import settings
from roster.models import WorkplaceUserPlacement

def current_lesson(now):
    # This function was in views.py, we might need to duplicate it or import it if it's utility.
    # For now, I'll duplicate the simple logic or better, import it if possible, but circular imports might be an issue.
    # Let's just reimplement the simple logic here or pass the lesson index.
    # Actually, let's look at views.py again. `current_lesson` depends on settings.
    last = 0
    for lesson, times in settings.LESSONS_SCHEDULE.items():
        if now.time() >= times['start']:
            last = lesson
    return last

def check_group_constraints(user, workplace_id):
    """
    Check if the user is allowed to sit at the given workplace based on group features.
    Returns (allowed: bool, error_message: str).
    """
    # Extract workplace number
    try:
        match = re.search(r'-(\d+)', workplace_id)
        if not match:
            return True, None
        current_number = int(match.group(1))
    except (TypeError, ValueError):
        return True, None

    # Get user's groups with features
    user_groups = user.student_groups.all().prefetch_related('features')
    
    # Determine current time window
    now = datetime.datetime.now()
    current_lesson_idx = current_lesson(now)
    
    if current_lesson_idx == 0:
        start_time = now - datetime.timedelta(hours=2)
        end_time = now + datetime.timedelta(hours=2)
    else:
        try:
            today = datetime.date.today()
            lesson_data = settings.LESSONS_SCHEDULE.get(current_lesson_idx)
            if lesson_data:
                start_time = datetime.datetime.combine(today, lesson_data['start']) - datetime.timedelta(minutes=15)
                end_time = datetime.datetime.combine(today, lesson_data['end']) + datetime.timedelta(minutes=15)
            else:
                start_time = now - datetime.timedelta(hours=1.5)
                end_time = now + datetime.timedelta(hours=1.5)
        except Exception:
            start_time = now - datetime.timedelta(hours=1.5)
            end_time = now + datetime.timedelta(hours=1.5)

    # Get all placements in this time window to find occupied computers
    all_placements = WorkplaceUserPlacement.objects.filter(
        created_at__gte=start_time,
        created_at__lte=end_time
    )
    
    occupied_computers = set()
    for p in all_placements:
        try:
            match = re.search(r'-(\d+)', p.workplace_id)
            if match:
                occupied_computers.add(int(match.group(1)))
        except (TypeError, ValueError):
            continue

    forbidden_computers = set()
    
    for group in user_groups:
        # Check for non_sequential feature
        feature = group.features.filter(feature_key='non_sequential', enabled=True).first()
        if feature:
            # Get placements of other students in this group
            group_student_ids = group.students.exclude(id=user.id).values_list('id', flat=True)
            
            # Filter placements for this group's students from the already fetched placements
            # This avoids an extra query, though we could also query if needed.
            # Let's just filter in python since we have all_placements
            group_placements = [p for p in all_placements if p.user_id in group_student_ids]

            min_distance = feature.parameters.get('min_distance', 1)

            for p in group_placements:
                try:
                    match = re.search(r'-(\d+)', p.workplace_id)
                    if match:
                        other_number = int(match.group(1))
                        # Mark computers around this one as forbidden
                        for i in range(other_number - min_distance, other_number + min_distance + 1):
                            forbidden_computers.add(i)
                except (TypeError, ValueError):
                    continue

    if current_number in forbidden_computers:
        # Calculate available computers
        all_computers = set(range(1, 19)) # Assuming 1-18 based on views.py
        available = sorted(list(all_computers - occupied_computers - forbidden_computers))
        available_str = ", ".join(map(str, available))
        
        return False, f"Щоб зберегти робочий темп уроку, деякі комбінації посадки тимчасово недоступні. Ось доступні варіанти для вас: {available_str}"

    return True, None
