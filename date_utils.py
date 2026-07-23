from datetime import date, timedelta

MONTH_SHORT = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def today_str() -> str:
    return date.today().isoformat()


def build_52_week_grid(end_date: date | None = None):
    """Returns a list of 53 columns (weeks), each a list of up to 7 dicts
    with date info, ending on the Saturday of the current week. Same
    layout logic as a GitHub contribution graph."""
    end_date = end_date or date.today()
    days_ahead_to_saturday = 5 - end_date.weekday() if end_date.weekday() != 6 else 6
    # Python weekday(): Mon=0..Sun=6. GitHub weeks run Sun-Sat.
    # Convert to Sun=0..Sat=6 indexing:
    dow_sun0 = (end_date.weekday() + 1) % 7
    pad_to_saturday = 6 - dow_sun0
    timeline_end = end_date + timedelta(days=pad_to_saturday)
    timeline_start = timeline_end - timedelta(days=370)  # 53*7 - 1

    days = []
    d = timeline_start
    while d <= timeline_end:
        dow_sun0 = (d.weekday() + 1) % 7
        days.append({
            "date_str": d.isoformat(),
            "day_of_week": dow_sun0,  # 0=Sun ... 6=Sat
            "month_label": MONTH_SHORT[d.month - 1],
            "is_future": d > date.today(),
            "date_obj": d,
        })
        d += timedelta(days=1)

    weeks = []
    current_week = []
    for day in days:
        current_week.append(day)
        if day["day_of_week"] == 6:
            weeks.append(current_week)
            current_week = []
    if current_week:
        weeks.append(current_week)
    return weeks


def recent_days(n: int, end_date: date | None = None):
    """Returns the last n days (oldest first) up to and including end_date,
    for the horizontal journal timeline."""
    end_date = end_date or date.today()
    return [(end_date - timedelta(days=i)).isoformat() for i in range(n - 1, -1, -1)]
