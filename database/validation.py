"""Shared server-side validation for submitted PFMS records."""
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
import re
from flask import request, flash, redirect
from database.db import query


def label(field):
    return field.replace('_', ' ').capitalize()


def numeric(raw, field, integer=False, positive=False):
    raw=str(raw if raw not in (None,'') else '0').strip()
    pattern=r'\d+' if integer else r'(?:\d+(?:\.\d{0,2})?|\.\d{1,2})'
    if len(raw)>24 or not re.fullmatch(pattern,raw):
        raise ValueError(label(field)+(' must be a non-negative whole number.' if integer else ' must be a non-negative number with at most two decimal places.'))
    value=Decimal(raw)
    # Bound stored inputs so subsequent arithmetic cannot overflow SQLite/float values.
    if value>Decimal('999999999999') or (positive and value<=0):
        raise ValueError(label(field)+(' must be greater than zero and no more than 999,999,999,999.' if positive else ' is too large.'))
    return int(value) if integer else value


def calendar_day(raw, field='date', optional=False):
    if optional and not raw:return None
    try:
        if not re.fullmatch(r'\d{4}-\d{2}-\d{2}',raw or ''):raise ValueError()
        return date.fromisoformat(raw)
    except (ValueError,TypeError):
        raise ValueError(label(field)+' must be a valid date (YYYY-MM-DD).')


def money(value):
    value=Decimal(str(value))
    if not value.is_finite() or abs(value)>Decimal('999999999999'):
        raise ValueError('The calculated amount is too large. Check the entered quantities and prices.')
    return float(value.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP))


def reference(table, raw, field, optional=False):
    if optional and raw in (None,''):return None
    identifier=numeric(raw,field,integer=True,positive=True)
    row=query('SELECT * FROM '+table+' WHERE id=?',(identifier,),one=True)
    if not row:raise ValueError('Select an existing '+field.replace('_id','').replace('_',' ')+'.')
    return row


# Explicit endpoint coverage keeps unrelated forms and read-only filters unaffected.
SPECS={
 'farms.add': ('size_acres', 'total_trees'),
 'farms.edit': ('size_acres', 'total_trees'),
 'activities.add': ('labour_cost materials_cost', 'num_labourers'),
 'activities.edit': ('labour_cost materials_cost', 'num_labourers'),
 'harvests.add': ('', ''), 'harvests.edit': ('', ''),
 'pruning.add_batch': ('cost', 'trees_pruned num_labourers'),
 'transport.add': ('fuel_cost driver_pay rental_cost',''),
 'transport.add_maintenance': ('cost',''),
 'plant.add_run': ('own_farms_gallons_input outside_farmers_gallons_input outside_farmer_fees cash_collected','own_farms_bunches outside_farmers_bunches'),
 'plant.edit_run': ('own_farms_gallons_input outside_farmers_gallons_input outside_farmer_fees cash_collected','own_farms_bunches outside_farmers_bunches'),
 'plant.add_expense': ('amount',''), 'plant.add_farmer': ('',''),
 'prices.add': ('price_offered price_accepted',''),
 'investors.add': ('',''),
 'investors.add_investment': ('amount return_pct',''),
 'investors.edit_investment': ('amount return_pct',''),
 'investors.log_return': ('amount',''),
 'storage.log_purchase': ('gallons price_per_gallon',''),
 'storage.log_sale': ('gallons price_per_gallon',''),
 'storage.log_quality': ('fresh_gallons soap_gallons',''),
 'storage.revalue': ('new_price',''),
}


def validate_form(endpoint, form, args):
    decimals,integers=SPECS[endpoint]
    for field in decimals.split():numeric(form.get(field),field)
    for field in integers.split():numeric(form.get(field),field,integer=True)
    def choice(field, choices, default=None):
        if form.get(field,default) not in choices:raise ValueError('Select a valid '+field.replace('_',' ')+'.')
    no_date={'farms.add','farms.edit','investors.add','plant.add_farmer'}
    day=None
    if endpoint not in no_date:
        fallback=endpoint.startswith('storage.') or endpoint in {'investors.add_investment','investors.edit_investment','investors.log_return'}
        day=calendar_day(form.get('date') or (date.today().isoformat() if fallback else None))
    if endpoint in {'farms.add','farms.edit','investors.add','plant.add_farmer'}:
        if not form.get('name','').strip():raise ValueError('Name is required.')
    if endpoint.startswith('farms.'):
        choice('crop_type',{'Oil Palm','Cashew'})
        choice('status',{'Active','Inactive','Development'})
        if endpoint=='farms.edit':reference('farms',args['farm_id'],'farm_id')
    required_farm=endpoint.startswith('activities.') or endpoint.startswith('harvests.') or endpoint=='pruning.add_batch'
    optional_farm=endpoint=='transport.add' or endpoint in {'investors.add_investment','investors.edit_investment'}
    if required_farm or optional_farm:reference('farms',form.get('farm_id'),'farm_id',optional=optional_farm)
    if endpoint.startswith('activities.'):
        choice('activity_type',{'Harvesting','Weeding','Fertilising','Spraying','Pruning','Planting','Maintenance','Other'})
    if endpoint.startswith('harvests.') or (endpoint.startswith('activities.') and form.get('activity_type')=='Harvesting'):
        for field in ['harvester_pay','collector_pay','threshing_cost','driver_pay','fuel_cost','tricycle_rent','gallons_produced']:
            numeric(form.get(field),field)
        for field in ['bunches_harvested','num_collectors']:numeric(form.get(field),field,integer=True)
        choice('husks_processed',{'0','1'},'0')
        choice('transport_mode',{'','Pickup','Tricycle'},'')
        if form.get('activity_id'):
            activity=reference('activities',form['activity_id'],'activity_id')
            if activity['activity_type']!='Harvesting' or activity['farm_id']!=int(form['farm_id']):
                raise ValueError('The linked harvesting activity must belong to the selected farm.')
    if endpoint in {'plant.add_run','plant.edit_run'}:
        for field,whole in [('contributing_farm_ids',True),('contributing_bunches',True),('contributing_gallons',False)]:
            for raw in form.getlist(field):
                if raw:numeric(raw,field,integer=whole)
        from routes.plant import _calc_run
        _calc_run(numeric(form.get('own_farms_gallons_input'),'own_farms_gallons_input'),
                  numeric(form.get('outside_farmers_gallons_input'),'outside_farmers_gallons_input'),
                  numeric(form.get('outside_farmer_fees'),'outside_farmer_fees'))
    if endpoint in {'storage.log_purchase','storage.log_sale'}:
        choice('quality_type',{'Fresh','Soap','Unassessed'},'Unassessed')
        money(numeric(form.get('gallons'),'gallons')*numeric(form.get('price_per_gallon'),'price_per_gallon'))
    if endpoint=='transport.add':choice('transport_type',{'Pickup','Tricycle'})
    if endpoint=='plant.add_expense':choice('category',{'Maintenance','Casual Labour','Consumables','Other'})
    if endpoint=='prices.add':
        choice('product',{'FFB','Palm Oil'})
        choice('negotiation_outcome',{'Accepted','Rejected','Countered'})
    if endpoint in {'investors.add_investment','investors.edit_investment','investors.log_return'}:
        numeric(form.get('amount'),'amount',positive=True)
        if 'investor_id' in args:reference('investors',args['investor_id'],'investor_id')
        if endpoint!='investors.log_return':
            money(numeric(form.get('amount'),'amount')*(1+numeric(form.get('return_pct'),'return_pct')/100))
            choice('investment_type',{'Cash','Equipment','Land','Other'},'Cash')
            due=calendar_day(form.get('return_date'),'return_date',optional=True)
            if due and due<day:raise ValueError('Return date cannot be before the investment date.')
            if endpoint=='investors.edit_investment':
                reference('investments',args['inv_id'],'investment_id')
                choice('status',{'Active','Completed','Defaulted'},'Active')
                first=query('SELECT MIN(date) AS day FROM investor_returns WHERE investment_id=?',(args['inv_id'],),one=True)['day']
                if first and day.isoformat()>first:raise ValueError('Investment date cannot be after an existing repayment.')
        else:
            if not form.get('investment_id','').strip():
                raise ValueError('Select the investment this repayment is for.')
            investment=reference('investments',form['investment_id'],'investment_id')
            if investment['investor_id']!=args['investor_id']:raise ValueError('The selected investment belongs to another investor.')
            if day.isoformat()<investment['date']:raise ValueError('Repayment date cannot be before the investment date.')


def validate_submission():
    if request.method!='POST' or request.endpoint not in SPECS:return None
    try:
        validate_form(request.endpoint,request.form,request.view_args or {})
    except ValueError as exc:
        flash(str(exc),'error')
        return redirect(request.url)
