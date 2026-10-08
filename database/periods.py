"""Shared calendar periods for farm reporting."""
from datetime import date
from calendar import monthrange


def business_today():
    return date.today()


def shift_month(day, offset):
    year,month=divmod(day.year*12+day.month-1+offset,12)
    return date(year,month+1,min(day.day,monthrange(year,month+1)[1]))


def comparison_periods(today):
    previous_month=shift_month(today,-1)
    previous_year=date(today.year-1,today.month,min(today.day,monthrange(today.year-1,today.month)[1]))
    return dict(previous_month_start=previous_month.replace(day=1).isoformat(),
                previous_month_end=previous_month.isoformat(),
                previous_year_start=previous_year.replace(month=1,day=1).isoformat(),
                previous_year_end=previous_year.isoformat())
