"""Fetch official public records and optionally load separate BigQuery snapshot tables.

Run with Python 3.11+, google-cloud-bigquery and openpyxl. No grant applications
or inferred WARN-to-business foreign keys are created. Existing graph tables stay intact.
"""
import argparse
import hashlib
import io
import json
import re
import urllib.parse
import urllib.request
from datetime import date, datetime, timezone
from pathlib import Path

SF_URL = 'https://data.sf.gov/resource/g8m3-pdis.json'
WARN_URL = 'https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx'
SF_FIELDS = ('uniqueid,ttxid,dba_name,ownership_name,full_business_address,location_start_date,'
             'location_end_date,dba_end_date,administratively_closed,data_as_of,data_loaded_at,business_corridor')


def fetch(url):
    req = urllib.request.Request(url, headers={'User-Agent': 'AgentsForImpact-public-records/1.0'})
    with urllib.request.urlopen(req, timeout=60) as response:
        return response.read()


def iso_date(value):
    if value is None or str(value).strip() == '': return None
    if isinstance(value, (datetime, date)): return value.date().isoformat() if isinstance(value, datetime) else value.isoformat()
    value = str(value).strip()
    for fmt in ('%Y-%m-%d', '%m/%d/%Y', '%m/%d/%y'):
        try: return datetime.strptime(value[:10], fmt).date().isoformat()
        except ValueError: pass
    raise ValueError('Unrecognized source date: ' + value)


def sf_record(row, retrieved):
    if not row.get('uniqueid') or not row.get('ttxid'): raise ValueError('Registry identifier missing')
    return {'record_id': row['uniqueid'], 'business_id': row['ttxid'], 'name': row.get('dba_name'),
            'legal_name': row.get('ownership_name'), 'address': row.get('full_business_address'),
            'corridor': row.get('business_corridor'), 'location_start_date': iso_date(row.get('location_start_date')),
            'location_end_date': iso_date(row.get('location_end_date')), 'dba_end_date': iso_date(row.get('dba_end_date')),
            'administratively_closed': row.get('administratively_closed'),
            'source_as_of': iso_date(row.get('data_as_of')), 'source_loaded_at': row.get('data_loaded_at'),
            'source_url': SF_URL, 'retrieved_at': retrieved, 'match_method': 'exact_registry_location_id'}


def sf_snapshot(corridor, retrieved):
    rows=[]; offset=0
    while True:
        query=urllib.parse.urlencode({'$select': SF_FIELDS, '$where': "business_corridor='" + corridor.replace("'", "''") + "'",
                                    '$order': 'uniqueid', '$limit': 1000, '$offset': offset})
        batch=json.loads(fetch(SF_URL+'?'+query)); rows.extend(sf_record(r,retrieved) for r in batch)
        if len(batch)<1000: break
        offset+=1000
        if offset>100000: raise ValueError('Unexpectedly large corridor snapshot')
    if not rows or len({r['record_id'] for r in rows}) != len(rows): raise ValueError('Empty or duplicate registry keys')
    return rows


def warn_snapshot(content, retrieved):
    import openpyxl
    workbook=openpyxl.load_workbook(io.BytesIO(content),data_only=True,read_only=True)
    sheet=next(s for s in workbook if s.title.strip()=='Detailed WARN Report')
    values=list(sheet.values)
    header=[re.sub(r'\s+',' ',str(v or '')).strip() for v in values[1]]
    expected=['County/Parish','Notice Date','Processed Date','Effective Date','Company','Layoff/ Closure','No. Of Employees','Address','Related Industry']
    if header != expected: raise ValueError('WARN columns changed: '+str(header))
    title=str(values[0][0]);rows=[];seen=set()
    for number,record in enumerate(values[2:],start=3):
        county,notice,processed,effective,company,event,employees,address,industry=record[:9]
        if str(county).strip()!='San Francisco County': continue
        if not company or not event: raise ValueError('Incomplete WARN record')
        if employees is not None and (isinstance(employees,bool) or float(employees)<0 or not float(employees).is_integer()):
            raise ValueError('Invalid employee count')
        fields={'county':str(county).strip(),'notice_date':iso_date(notice),'processed_date':iso_date(processed),
                'effective_date':iso_date(effective),'company':str(company).strip(),'event_type':str(event).strip(),
                'employees_affected':int(employees) if employees is not None else None,
                'address':str(address or '').strip(),'industry':str(industry or '').strip()}
        key=hashlib.sha256(json.dumps(fields,sort_keys=True).encode()).hexdigest()
        if key in seen: continue
        seen.add(key)
        rows.append({**fields,'notice_id':key,'source_url':WARN_URL,'source_report_title':title,
                     'source_row':number,'retrieved_at':retrieved,'match_method':'county_scope_only_no_business_link'})
    if not rows: raise ValueError('No San Francisco WARN rows; inspect source before publishing')
    return rows


def load(client, dataset, table, rows):
    from google.cloud import bigquery
    date_fields={'location_start_date','location_end_date','dba_end_date','source_as_of','notice_date','processed_date','effective_date'}
    schema=[bigquery.SchemaField(k,'DATE' if k in date_fields else 'TIMESTAMP' if k=='retrieved_at' else
                                'INT64' if k in ('employees_affected','source_row') else 'STRING') for k in rows[0]]
    ref=f'{client.project}.{dataset}.{table}'
    job=client.load_table_from_json(rows,ref,job_config=bigquery.LoadJobConfig(schema=schema,write_disposition='WRITE_TRUNCATE'))
    job.result(timeout=120)
    t=client.get_table(ref);t.description=('Official dated public snapshot. Registry ID matches are exact; WARN records are county context without verified corridor or business links. Not grant applications.')
    client.update_table(t,['description'])
    assert t.num_rows==len(rows)
    return {'table':ref,'rows':t.num_rows,'load_job':job.job_id}


def main():
    p=argparse.ArgumentParser();p.add_argument('--project',default='qwiklabs-gcp-04-029c15637557')
    p.add_argument('--dataset',default='a4i_econ');p.add_argument('--corridor',default='Central Market')
    p.add_argument('--output',type=Path,default=Path('public-records-snapshot'));p.add_argument('--load',action='store_true');a=p.parse_args()
    retrieved=datetime.now(timezone.utc).isoformat()
    sf=sf_snapshot(a.corridor,retrieved);warn_bytes=fetch(WARN_URL);warn=warn_snapshot(warn_bytes,retrieved)
    a.output.mkdir(parents=True,exist_ok=True)
    for name,rows in [('public_business_status',sf),('public_warn_notices',warn)]:
        (a.output/(name+'.json')).write_text(json.dumps(rows,indent=2))
    manifest={'retrieved_at':retrieved,'corridor':a.corridor,'registry_rows':len(sf),'warn_sf_rows':len(warn),
              'registry_source_as_of':sorted({r['source_as_of'] for r in sf if r['source_as_of']}),
              'warn_report_title':warn[0]['source_report_title'],'warn_sha256':hashlib.sha256(warn_bytes).hexdigest(),
              'warn_scope':'San Francisco County; not verified corridor businesses','grant_applications':'not available from these sources'}
    if a.load:
        from google.cloud import bigquery
        c=bigquery.Client(project=a.project,location='US')
        manifest['loads']=[load(c,a.dataset,n,r) for n,r in [('public_business_status',sf),('public_warn_notices',warn)]]
        ids={r['business_id'] for r in c.list_rows(f'{a.project}.{a.dataset}.businesses')}
        manifest['existing_businesses']=len(ids);manifest['exact_status_matches']=len(ids & {r['business_id'] for r in sf})
    (a.output/'manifest.json').write_text(json.dumps(manifest,indent=2));print(json.dumps(manifest,indent=2))

if __name__=='__main__': main()
