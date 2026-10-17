"""Transport failures must not turn an interrupted approval into a fresh transaction."""
import json
import sqlite3
import httpx
import pytest
from api.app.database import RemoteConnection,connect,encode


def client(handler):
 return RemoteConnection('libsql://test.turso.io','not-a-real-token',transport=httpx.MockTransport(handler))


def ok(request,baton='next',rows=None):
 requests=json.loads(request.content)['requests']
 return httpx.Response(200,json={'baton':baton,'base_url':None,'results':[{'type':'ok','response':{'type':operation['type'],'result':{'cols':[{'name':'amount'}],'rows':rows or []}}} for operation in requests]})


def test_exact_large_integer_and_named_row():
 with client(lambda r:ok(r,rows=[[{'type':'integer','value':'9007199254740993'}]])) as db:
  db.row_factory=sqlite3.Row
  row=db.execute('SELECT amount').fetchone()
  assert row[0]==row['amount']==9007199254740993
  assert dict(row)=={'amount':9007199254740993}
  assert encode(row[0])=={'type':'integer','value':'9007199254740993'}
 db.close()


@pytest.mark.parametrize('mode',['timeout','http500','closed','wrong_type','wrong_count','unsafe_redirect','bad_json'])
def test_lost_stream_never_reopens_or_commits(mode):
 calls=[]
 def handler(request):
  calls.append(json.loads(request.content))
  if len(calls)==1:return ok(request,'first-baton')
  if mode=='timeout':raise httpx.ReadTimeout('private URL must not leak')
  if mode=='http500':return httpx.Response(500)
  if mode=='closed':return ok(request,None)
  if mode=='bad_json':return httpx.Response(200,text='<html>')
  data=json.loads(ok(request).content)
  if mode=='wrong_type':data['results'][0]['response']['type']='close'
  if mode=='wrong_count':data['results']=[]
  if mode=='unsafe_redirect':data['base_url']='https://attacker.invalid/'
  return httpx.Response(200,json=data)
 db=client(handler);db.execute('BEGIN IMMEDIATE')
 with pytest.raises(sqlite3.DatabaseError,match='Remote database operation failed'):db.execute('SELECT amount')
 with pytest.raises(sqlite3.DatabaseError):db.commit()
 with pytest.raises(sqlite3.DatabaseError):db.execute('INSERT INTO t VALUES (1)')
 assert len(calls)==2 and calls[1]['baton']=='first-baton'
 db.close()


def test_constraint_rollback_and_baton_rotation():
 calls=[]
 def handler(request):
  body=json.loads(request.content);calls.append(body)
  if len(calls)==2:return httpx.Response(200,json={'baton':'after-error','results':[{'type':'error','error':{'code':'SQLITE_CONSTRAINT_UNIQUE','message':'private SQL'}}]})
  return ok(request,'after-'+str(len(calls)))
 db=client(handler)
 with pytest.raises(sqlite3.IntegrityError):
  with db:db.execute('INSERT INTO t VALUES (?)',(7,))
 assert [x['requests'][-1]['stmt']['sql'] for x in calls]==['BEGIN','INSERT INTO t VALUES (?)','ROLLBACK']
 assert calls[2]['baton']=='after-error' and not db.in_transaction
 db.close()


@pytest.mark.parametrize('url,token',[('', ''),('libsql://demo.turso.io',''),('https://attacker.invalid','x'),('libsql://demo.turso.io?x=1','x')])
def test_vercel_never_falls_back_to_ephemeral_sqlite(monkeypatch,url,token):
 monkeypatch.setenv('VERCEL','1');monkeypatch.setenv('TURSO_DATABASE_URL',url);monkeypatch.setenv('TURSO_AUTH_TOKEN',token)
 with pytest.raises(sqlite3.DatabaseError):connect()
