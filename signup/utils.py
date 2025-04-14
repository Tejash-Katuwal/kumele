from django.utils import timezone
from datetime import timedelta
from .models import CustomUser, Medal
from events.models import Event, EventAttendance
from django.db.models import Q


class MedalManager:
    @staticmethod
    def get_period_dates(join_date, current_date=None):
        """Calculate the medal period based on join date."""
        if current_date is None:
            current_date = timezone.now()

        # Start from next month if joined mid-month
        if join_date.day > 1:
            period_start = (join_date.replace(day=1) + timedelta(days=32)).replace(day=1, hour=0, minute=0, second=0)
        else:
            period_start = join_date.replace(day=1, hour=0, minute=0, second=0)

        # Adjust to current or future period
        while period_start < current_date.replace(day=1, hour=0, minute=0, second=0):
            period_start = (period_start + timedelta(days=32)).replace(day=1, hour=0, minute=0, second=0)

        # End of the month
        period_end = (period_start + timedelta(days=32)).replace(day=1, hour=0, minute=0, second=0) - timedelta(seconds=1)

        return period_start, period_end

    @staticmethod
    def count_user_events(user, period_start, period_end):
        """Count distinct events created or attended by the user in the period."""
        return Event.objects.filter(
            (Q(creator=user) | Q(attendees__user=user)) &
            Q(start_time__gte=period_start) &
            Q(start_time__lte=period_end) &
            Q(is_active=True)
        ).distinct().count()

    @staticmethod
    def assign_medals(user):
        """Assign medals based on event activity."""
        period_start, period_end = MedalManager.get_period_dates(user.date_joined)

        # Skip if period is in the future
        if period_start > timezone.now():
            return

        event_count = MedalManager.count_user_events(user, period_start, period_end)
        existing_medals = Medal.objects.filter(user=user, period_start=period_start).values_list('medal_type', flat=True)

        # Gold: 3+ events, multiple allowed
        if event_count >= 3 and (event_count // 3) > existing_medals.filter(medal_type='GOLD').count():
            Medal.objects.create(
                user=user,
                medal_type='GOLD',
                discount_percentage=5.00,
                discount_expires_at=timezone.now() + timedelta(days=30),
                period_start=period_start,
                period_end=period_end
            )
        # Silver: Exactly 2 events, one-time only
        elif event_count == 2 and 'SILVER' not in existing_medals and 'GOLD' not in existing_medals:
            Medal.objects.create(
                user=user,
                medal_type='SILVER',
                discount_percentage=3.00,
                discount_expires_at=timezone.now() + timedelta(days=30),
                period_start=period_start,
                period_end=period_end
            )
        # Bronze: Exactly 1 event, one-time only
        elif event_count == 1 and 'BRONZE' not in existing_medals and 'SILVER' not in existing_medals and 'GOLD' not in existing_medals:
            Medal.objects.create(
                user=user,
                medal_type='BRONZE',
                discount_percentage=0.00,
                period_start=period_start,
                period_end=period_end
            )