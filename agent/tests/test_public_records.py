import importlib.util
from pathlib import Path
import pytest
from neighborhood_context.public_records import summarize_public_records

spec=importlib.util.spec_from_file_location('loader',Path(__file__).parents[2]/'scripts/load_public_records.py')
loader=importlib.util.module_from_spec(spec);spec.loader.exec_module(loader)

def row(id='a',record='1',**values):
    return {'business_id':id,'record_id':record,'source_as_of':'2026-10-20',**values}

def test_missing_status_is_not_open():
    r=summarize_public_records('a',[],[])
    assert r['registry_status']=='no_matching_record'
    assert r['warn_scope'].endswith('no verified business or corridor link')

def test_mixed_ownership_records_are_not_collapsed_to_open():
    r=summarize_public_records('a',[row(),row(record='2',location_end_date='2020-01-01')],[])
    assert r['registry_status']=='mixed_registry_records'
    assert summarize_public_records('a',[row(administratively_closed='***Administratively Closed')],[])['registry_status']=='closure_recorded'

def test_status_latest_source_date_and_exact_identifiers():
    old=row(record='2',location_end_date='2020-01-01');old['source_as_of']='2020-01-01'
    assert summarize_public_records('a',[row(),old],[])['registry_status']=='no_closure_recorded'
    with pytest.raises(ValueError):summarize_public_records('a',[row('b')],[])
    with pytest.raises(ValueError):summarize_public_records('a',[row(),row()],[])

def test_registry_normalization_preserves_dates_and_provenance():
    r=loader.sf_record({'uniqueid':'r','ttxid':'a','data_as_of':'2026-10-20T00:00:00.000'},'2026-10-20T18:00:00Z')
    assert r['source_as_of']=='2026-10-20' and r['location_end_date'] is None
    assert r['match_method']=='exact_registry_location_id'
    with pytest.raises(ValueError):loader.sf_record({'ttxid':'a'},'now')

def test_warn_parser_filters_county_without_invented_business_match():
    import io,openpyxl
    from datetime import datetime
    w=openpyxl.Workbook();s=w.active;s.title='Detailed WARN Report'
    s.append(['WARN report'])
    s.append(['County/Parish','Notice\nDate','Processed\nDate','Effective \nDate','Company','Layoff/\nClosure','No. Of\nEmployees','Address','Related Industry'])
    for county in ['San Francisco County','San Mateo County']:
        s.append([county,datetime(2026,10,1),datetime(2026,10,2),datetime(2026,11,1),'Example Co','Layoff Permanent',12,'Example address','Industry'])
    f=io.BytesIO();w.save(f)
    r=loader.warn_snapshot(f.getvalue(),'2026-10-20T18:00:00Z')
    assert len(r)==1 and r[0]['employees_affected']==12
    assert 'business_id' not in r[0] and r[0]['effective_date']=='2026-11-01'
