"""ASGI request buffering capped at 1 MiB before JSON/model parsing."""
import json
from starlette.responses import JSONResponse

class BodyLimitMiddleware:
    def __init__(self,app,limit=1024*1024,large=2*1024*1024):
        self.app,self.limit,self.large=app,limit,large

    async def __call__(self,scope,receive,send):
        if scope['type']!='http' or scope['method'] not in {'POST','PUT','PATCH'}:
            return await self.app(scope,receive,send)
        headers=dict(scope.get('headers',[]))
        if headers.get(b'content-type',b'').split(b';',1)[0].strip().lower()!=b'application/json':
            return await JSONResponse({'error':{'code':'JSON_CONTENT_TYPE_REQUIRED'}},status_code=415)(scope,receive,send)
        limit=self.large if scope.get('path')=='/api/assist/scan' else self.limit
        chunks=[];size=0
        while True:
            event=await receive()
            if event['type']=='http.disconnect':return
            chunk=event.get('body',b'');size+=len(chunk)
            if size>limit:
                return await JSONResponse({'error':{'code':'REQUEST_BODY_TOO_LARGE'}},status_code=413)(scope,receive,send)
            chunks.append(chunk)
            if not event.get('more_body',False):break
        body=b''.join(chunks)
        def unique(pairs):
            result={}
            for key,value in pairs:
                if key in result:raise ValueError('duplicate JSON key')
                result[key]=value
            return result
        def finite(value):
            raise ValueError('nonfinite JSON constant')
        try:
            json.loads(body.decode('utf-8'),object_pairs_hook=unique,parse_constant=finite)
        except (ValueError,UnicodeError,RecursionError):
            return await JSONResponse({'error':{'code':'INVALID_JSON'}},status_code=422)(scope,receive,send)
        sent=False
        async def replay():
            nonlocal sent
            if not sent:
                sent=True
                return {'type':'http.request','body':body,'more_body':False}
            return await receive()
        await self.app(scope,replay,send)
