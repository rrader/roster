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
    
    for group in user_groups:
        # Check for non_sequential feature
        feature = group.features.filter(feature_key='non_sequential', enabled=True).first()
        if feature:
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

            # Get placements of other students in this group
            group_student_ids = group.students.exclude(id=user.id).values_list('id', flat=True)
            placements = WorkplaceUserPlacement.objects.filter(
                user_id__in=group_student_ids,
                created_at__gte=start_time,
                created_at__lte=end_time
            )

            min_distance = feature.parameters.get('min_distance', 1)

            for p in placements:
                try:
                    match = re.search(r'-(\d+)', p.workplace_id)
                    if match:
                        other_number = int(match.group(1))
                        if abs(current_number - other_number) <= min_distance:
                            return False, f"Ви не можете сідати поруч з одногрупниками (Група: {group.name}, мін. відстань: {min_distance})"
                except (TypeError, ValueError):
                    continue

    return True, None
