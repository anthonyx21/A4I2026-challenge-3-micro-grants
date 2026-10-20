"""Signed demo reviewer sessions and internal task authentication."""
import hashlib
import hmac
import os
import time
from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel

def signing_key():
    return os.getenv('SESSION_SECRET',os.getenv('DATABASE_URL','reliefiq-local-development')).encode()

def task_token():
    return hmac.new(signing_key(),b'reliefiq-task-worker',hashlib.sha256).hexdigest()

def session_token():
    expiry=str(int(time.time())+8*3600)
    return expiry+'.'+hmac.new(signing_key(),expiry.encode(),hashlib.sha256).hexdigest()

def valid(token):
    try:
        expiry,signature=token.split('.')
        return int(expiry)>time.time() and hmac.compare_digest(signature,hmac.new(signing_key(),expiry.encode(),hashlib.sha256).hexdigest())
    except (ValueError,AttributeError): return False

class Login(BaseModel):
    password: str

def attach_auth(app):
    @app.middleware('http')
    async def authenticate(request: Request,call_next):
        if request.url.path.startswith('/api/') and request.url.path not in ('/api/login','/api/health') and os.getenv('REQUIRE_REVIEWER_LOGIN')=='true':
            internal=request.url.path.startswith('/api/internal/') and hmac.compare_digest(request.headers.get('X-ReliefIQ-Task',''),task_token())
            if not internal and not valid(request.cookies.get('reliefiq_session','')):
                return JSONResponse({'detail':'Reviewer login required'},status_code=401)
        return await call_next(request)
    @app.post('/api/login')
    def login(req: Login):
        if not hmac.compare_digest(req.password,os.getenv('REVIEWER_PASSWORD','demopassword')):
            raise HTTPException(401,'Invalid reviewer password')
        response=JSONResponse({'status':'authenticated','mode':'challenge_demo_reviewer'})
        response.set_cookie('reliefiq_session',session_token(),httponly=True,secure=bool(os.getenv('K_SERVICE')),samesite='strict',max_age=8*3600)
        return response

    @app.post('/api/logout')
    def logout():
        response=JSONResponse({'status':'logged_out'})
        response.delete_cookie('reliefiq_session')
        return response
