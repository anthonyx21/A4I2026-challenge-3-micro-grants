"""Persistent application snapshots and auditable runs. PostgreSQL in Cloud Run; SQLite locally."""
import json
import os
from datetime import datetime, timezone, timedelta
from pathlib import Path
from uuid import uuid4
from sqlalchemy import create_engine, MetaData, Table, Column, String, Integer, JSON, Text, ForeignKey, select, update, text

metadata = MetaData()
schema_versions = Table('schema_versions',metadata,Column('version',Integer,primary_key=True),Column('applied_at',String,nullable=False))
applications = Table('applications', metadata, Column('id', String, primary_key=True),
                     Column('version', Integer, nullable=False), Column('payload', JSON, nullable=False))
workspace = Table('workspace', metadata, Column('id', String, primary_key=True), Column('payload', JSON, nullable=False))
runs = Table('analysis_runs', metadata, Column('id', String, primary_key=True),
             Column('application_id', String, ForeignKey('applications.id'), nullable=False), Column('status', String, nullable=False),
             Column('created_at', String, nullable=False), Column('input_snapshot', JSON, nullable=False),
             Column('evidence', JSON), Column('error', Text))
memos = Table('memo_versions', metadata, Column('id', String, primary_key=True), Column('run_id', String, ForeignKey('analysis_runs.id'), nullable=False),
              Column('application_id', String, ForeignKey('applications.id'), nullable=False), Column('created_at', String, nullable=False),
              Column('content', Text, nullable=False), Column('source', String, nullable=False))


def now(): return datetime.now(timezone.utc).isoformat()


class Store:
    def __init__(self, url=None):
        url=url or os.getenv('DATABASE_URL')
        if not url:
            if os.getenv('K_SERVICE'): raise RuntimeError('DATABASE_URL is required in Cloud Run')
            directory=Path(os.getenv('RELIEFIQ_DATA_DIR',str(Path.home()/'.reliefiq')));directory.mkdir(parents=True,exist_ok=True)
            url='sqlite:///'+str(directory/'applications.db')
        self.engine=create_engine(url,pool_pre_ping=True,connect_args={'check_same_thread':False} if url.startswith('sqlite') else {})
        with self.engine.begin() as c:
            if self.engine.dialect.name=='postgresql': c.execute(text('SELECT pg_advisory_xact_lock(4812025)'))
            metadata.create_all(c)
            if not c.execute(select(schema_versions).where(schema_versions.c.version==1)).first():
                c.execute(schema_versions.insert().values(version=1,applied_at=now()))

    def seed(self, path=None):
        data=json.loads((path or Path(__file__).with_name('seed_data.json')).read_text())
        with self.engine.begin() as c:
            if self.engine.dialect.name=='postgresql': c.execute(text('SELECT pg_advisory_xact_lock(4812026)'))
            if c.execute(select(workspace.c.id).where(workspace.c.id=='default')).first(): return
            for original in data['applications']:
                a={**original,'input_type':'simulated','cash_gap':original.get('cash_gap',original['ask']),
                   'evidence_note':'SYNTHETIC SEEDED DEMO. Financials, owners, document claims and connections are not verified facts.',
                   'operating_assumption':original['use']+'; assume full gap funding sustains operation for 90 days. Partial funding has no assumed benefit.'}
                c.execute(applications.insert().values(id=a['id'],version=1,payload=a))
            c.execute(workspace.insert().values(id='default',payload={k:v for k,v in data.items() if k!='applications'}))

    def bootstrap(self):
        with self.engine.connect() as c:
            w=c.execute(select(workspace.c.payload).where(workspace.c.id=='default')).scalar_one()
            rows=c.execute(select(applications).order_by(applications.c.id)).mappings().all()
            rr=c.execute(select(runs).order_by(runs.c.created_at.desc()).limit(50)).mappings().all()
            mm=c.execute(select(memos).order_by(memos.c.created_at.desc())).mappings().all()
        return {**w,'applications':[{**r['payload'],'version':r['version']} for r in rows],
                'analysis_runs':[{'id':r['id'],'application_id':r['application_id'],'status':r['status'],'created_at':r['created_at']} for r in rr],'memos':[dict(m) for m in mm],'provenance':'simulated_seed','database':self.engine.dialect.name}

    def application(self, id):
        with self.engine.connect() as c:
            r=c.execute(select(applications).where(applications.c.id==id)).mappings().first()
        return {**r['payload'],'version':r['version']} if r else None

    def edit(self, id, changes, version):
        with self.engine.begin() as c:
            r=c.execute(select(applications).where(applications.c.id==id).with_for_update()).mappings().first()
            if not r: raise KeyError(id)
            payload={**r['payload'],**changes}
            result=c.execute(update(applications).where(applications.c.id==id,applications.c.version==version)
                             .values(payload=payload,version=version+1))
            if result.rowcount!=1: raise ValueError('Application changed; reload before saving')
        return self.application(id)

    def create_run(self,id,snapshot):
        run_id=str(uuid4())
        with self.engine.begin() as c:
            if self.engine.dialect.name=='postgresql':
                c.execute(text('SELECT pg_advisory_xact_lock(4812027)'))
            active=c.execute(select(runs).where(runs.c.application_id==id,runs.c.status.in_(['queued','running']))).mappings().all()
            for row in active:
                if row['input_snapshot']==snapshot: return row['id']
            c.execute(runs.insert().values(id=run_id,application_id=id,status='queued',created_at=now(),input_snapshot=snapshot))
        return run_id

    def finish(self,run_id,id,evidence,content):
        memo_id=str(uuid4());created=now()
        with self.engine.begin() as c:
            c.execute(update(runs).where(runs.c.id==run_id).values(status='complete',evidence=evidence))
            c.execute(memos.insert().values(id=memo_id,run_id=run_id,application_id=id,created_at=created,
                                           content=content,source='live_grant_advisor'))
        return self.memo(memo_id)

    def fail(self,run_id,message):
        with self.engine.begin() as c:c.execute(update(runs).where(runs.c.id==run_id).values(status='failed',error=message))

    def memo(self,id):
        with self.engine.connect() as c:
            r=c.execute(select(memos).where(memos.c.id==id)).mappings().first()
        return dict(r) if r else None

    def run(self,id):
        with self.engine.begin() as c:
            cutoff=(datetime.now(timezone.utc)-timedelta(minutes=30)).isoformat()
            c.execute(update(runs).where(runs.c.id==id,runs.c.status.in_(['queued','running']),runs.c.created_at<cutoff).values(status='failed',error='Job exceeded its 30-minute recovery deadline; generate a new memo'))
            r=c.execute(select(runs).where(runs.c.id==id)).mappings().first()
        return dict(r) if r else None

    def recommend(self,id,amount):
        with self.engine.begin() as c:
            query=select(workspace).where(workspace.c.id=='default').with_for_update()
            row=c.execute(query).mappings().one();payload=dict(row['payload'])
            recommendations=dict(payload.get('recommendations',{}))
            if amount is None: recommendations.pop(id,None)
            else: recommendations[id]=amount
            available=min(payload['settings']['round_budget'],payload['settings']['pool_total']-payload['settings']['pool_committed'])
            if sum(recommendations.values())>available: raise ValueError('Recommendations exceed available round budget')
            payload['recommendations']=recommendations
            c.execute(update(workspace).where(workspace.c.id=='default').values(payload=payload))
        return recommendations

    def claim_run(self,id):
        with self.engine.begin() as c:
            row=c.execute(select(runs).where(runs.c.id==id).with_for_update()).mappings().first()
            if not row or row['status']!='queued': return False
            c.execute(update(runs).where(runs.c.id==id).values(status='running'))
        return True

    def update_budget(self,amount):
        with self.engine.begin() as c:
            row=c.execute(select(workspace).where(workspace.c.id=='default').with_for_update()).mappings().one()
            payload=dict(row['payload']);settings=dict(payload['settings'])
            if amount>settings['pool_total']-settings['pool_committed'] or amount<sum(payload.get('recommendations',{}).values()):
                raise ValueError('Round budget must fit the remaining pool and existing recommendations')
            settings['round_budget']=amount;payload['settings']=settings
            c.execute(update(workspace).where(workspace.c.id=='default').values(payload=payload))
        return settings
