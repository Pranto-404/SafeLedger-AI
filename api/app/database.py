"""SQLite locally; primary-only Turso Hrana HTTP remotely. No local-cloud replicas.

Protocol: https://github.com/tursodatabase/libsql/blob/main/docs/HTTP_V2_SPEC.md
A failed/lost stream is permanently unusable; financial transactions are never retried.
"""
import os
import sqlite3
from urllib.parse import urlsplit
import httpx


class NamedRow(tuple):
    def __new__(cls, values, columns):
        row = super().__new__(cls, values)
        row.columns = columns
        return row

    def keys(self):
        return self.columns

    def __getitem__(self, key):
        return super().__getitem__(self.columns.index(key) if isinstance(key, str) else key)


def encode(value):
    if value is None:return {'type':'null'}
    if isinstance(value,int):return {'type':'integer','value':str(value)}
    if isinstance(value,str):return {'type':'text','value':value}
    if isinstance(value,float):return {'type':'float','value':value}
    raise sqlite3.InterfaceError('Unsupported parameter type')


def decode(value):
    if value['type']=='null':return None
    if value['type']=='integer':return int(value['value'])
    if value['type']=='text':return value['value']
    if value['type']=='float':return float(value['value'])
    raise sqlite3.DatabaseError('Unsupported database value')


class Cursor:
    def __init__(self, result, named):
        columns = [column['name'] for column in result['cols']]
        self.rows = iter([NamedRow([decode(v) for v in row],columns) if named else tuple(decode(v) for v in row) for row in result['rows']])

    def fetchone(self):return next(self.rows,None)
    def fetchall(self):return list(self.rows)
    def __iter__(self):return self.rows


class RemoteConnection:
    def __init__(self, url, token, *, transport=None):
        self.base = 'https://' + urlsplit(url).netloc
        self.client = httpx.Client(headers={'Authorization':'Bearer '+token},timeout=10,follow_redirects=False,transport=transport)
        self.baton = None
        self.started = False
        self.failed = False
        self.in_transaction = False
        self.row_factory = None

    def _request(self, request, *, allow_close=False):
        if self.failed:raise sqlite3.DatabaseError('Database stream unavailable')
        try:
            requests=([{'type':'execute','stmt':{'sql':'PRAGMA foreign_keys=ON'}}] if self.baton is None and request['type']!='close' else [])+[request]
            response=self.client.post(self.base+'/v2/pipeline',json={'baton':self.baton,'requests':requests})
            response.raise_for_status()
            body=response.json()
            baton=body['baton']
            if not allow_close and request['type']!='close' and not isinstance(baton,str):raise ValueError('Closed stream')
            self.baton=baton;self.started=True
            if body.get('base_url'):
                target=urlsplit(body['base_url'])
                if target.scheme!='https' or not target.hostname or not target.hostname.endswith('.turso.io') or target.username or target.password or target.port or target.query or target.fragment:
                    raise ValueError('Invalid routing URL')
                self.base=body['base_url'].rstrip('/')
            if len(body['results'])!=len(requests):raise ValueError('Invalid result count')
            if len(requests)>1 and (body['results'][0]['type']!='ok' or body['results'][0]['response']['type']!='execute'):raise ValueError('Foreign key configuration failed')
            result=body['results'][-1]
            if result['type']=='error':
                code=result['error'].get('code','')
                if code.startswith('SQLITE_CONSTRAINT'):
                    # Constraint failure aborts the statement, not the stream. Caller rolls back.
                    raise sqlite3.IntegrityError('Database constraint rejected operation')
                raise ValueError('Remote operation rejected')
            if result['type']!='ok' or result['response']['type']!=request['type']:raise ValueError('Invalid response')
            return result['response']
        except sqlite3.IntegrityError:
            raise
        except (httpx.HTTPError,ValueError,KeyError,TypeError):
            # Never send a new null baton and silently continue a lost transaction.
            self.failed=True
            raise sqlite3.DatabaseError('Remote database operation failed') from None

    def execute(self, sql, parameters=()):
        operation=sql.lstrip().split(None,1)[0].upper()
        if operation in {'INSERT','UPDATE','DELETE','REPLACE'} and not self.in_transaction:
            self.execute('BEGIN')
        result=self._request({'type':'execute','stmt':{'sql':sql,'args':[encode(v) for v in parameters],'want_rows':True}},allow_close=operation in {'COMMIT','ROLLBACK','END'} or (not self.in_transaction and operation!='BEGIN'))
        if operation=='BEGIN':self.in_transaction=True
        if operation in {'COMMIT','ROLLBACK','END'}:self.in_transaction=False
        return Cursor(result['result'],self.row_factory is not None)

    def executemany(self, sql, parameters):
        for row in parameters:self.execute(sql,row)

    def executescript(self, sql):
        self.commit()
        return self._request({'type':'sequence','sql':sql},allow_close=True)

    def commit(self):
        if self.in_transaction:self.execute('COMMIT')

    def rollback(self):
        if self.in_transaction:self.execute('ROLLBACK')

    def close(self):
        try:
            if self.baton is not None and not self.failed:self._request({'type':'close'})
        finally:
            self.failed=True
            self.client.close()

    def __enter__(self):return self

    def __exit__(self, kind, value, traceback):
        if kind is not None:
            if not self.failed:self.rollback()
        else:
            try:self.commit()
            except BaseException:
                if not self.failed:self.rollback()
                raise


def connect():
    url,token=os.environ.get('TURSO_DATABASE_URL'),os.environ.get('TURSO_AUTH_TOKEN')
    if url or token:
        parsed=urlsplit(url or '')
        if not token or parsed.scheme!='libsql' or not parsed.hostname or not parsed.hostname.endswith('.turso.io') or parsed.username or parsed.password or parsed.port or parsed.query or parsed.fragment or parsed.path not in ('','/'):
            raise sqlite3.DatabaseError('Invalid remote database configuration')
        connection=RemoteConnection(url,token)
    else:
        if os.environ.get('VERCEL')=='1':raise sqlite3.DatabaseError('Persistent database required on Vercel')
        connection=sqlite3.connect(os.environ.get('SAFELEDGER_DB','./safeledger.sqlite3'),timeout=5,check_same_thread=False)
    connection.execute('PRAGMA foreign_keys=ON')
    return connection
