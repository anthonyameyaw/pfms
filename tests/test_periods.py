import unittest
from datetime import date
from database.periods import comparison_periods, shift_month
import test_financials as fixture
from test_financials import db

class CalendarTests(unittest.TestCase):
    def test_leap_day_comparison(self):
        p=comparison_periods(date(2024,2,29))
        self.assertEqual(p['previous_year_end'],'2023-02-28')
        self.assertEqual(p['previous_month_end'],'2024-01-29')
    def test_year_and_short_month_boundaries(self):
        self.assertEqual(shift_month(date(2026,1,31),-1),date(2025,12,31))
        self.assertEqual(shift_month(date(2026,3,31),-1),date(2026,2,28))

class PeriodRouteTests(unittest.TestCase):
    setUp=fixture.FinancialTests.setUp
    context=fixture.FinancialTests.context
    def test_sparse_forecast_and_future_exclusion(self):
        for day,bunches in [('2025-11-01',120),('2026-05-01',120),('2026-10-01',900),('2027-01-01',900)]:
            db.execute('INSERT INTO harvests(farm_id,date,bunches_harvested) VALUES(4,?,?)',(day,bunches))
        c=self.context('harvests','/harvests/forecast')
        f=next(x for x in c['forecasts'] if x['farm']['id']==4)
        self.assertEqual(c['period_start'],'2025-10-01')
        self.assertEqual(c['period_end'],'2026-09-30')
        self.assertEqual(len(f['monthly']),12)
        self.assertEqual(f['average'],20)
        self.assertEqual(f['unrecorded_months'],10)
        self.assertEqual([x['month'] for x in f['projected']],['November 2026','December 2026','January 2027'])
        self.assertEqual(self.client.get('/harvests/forecast').status_code,200)
    def test_dashboard_calendar_has_empty_months_and_excludes_future(self):
        db.execute("INSERT INTO plant_expenses(date,amount) VALUES('2026-10-03',900)")
        c=self.context('dashboard','/')
        self.assertEqual(len(c['monthly_elec_maint']),12)
        self.assertEqual(sum(x['maintenance'] for x in c['monthly_elec_maint']),0)
    def test_plant_matching_year_dates_and_current_cutoff(self):
        for day,amount in [('2025-10-02',100),('2025-10-03',900),('2026-10-02',200),('2026-10-03',800)]:
            db.execute('INSERT INTO processing_runs(date,gross_revenue,outside_farmer_fees,total_output_gallons) VALUES(?,?,?,1)',(day,amount,amount))
        c=self.context('plant','/plant/')
        self.assertEqual(c['yoy_income_chg'],100.0)
        self.assertEqual(c['this_m_income'],200)
        for url in ['/','/plant/','/farms/4']:
            self.assertEqual(self.client.get(url).status_code,200,url)
