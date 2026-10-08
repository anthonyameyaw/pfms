"""Security controls for PFMS on this computer only."""
import hmac
import os
from pathlib import Path
import re
import secrets
from urllib.parse import urlsplit
from flask import abort, request, session, render_template
from database import db


def load_secret(path):
    path=Path(path)
    try:
        descriptor=os.open(str(path),os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    except FileExistsError:
        pass
    else:
        with os.fdopen(descriptor,'w') as stream:
            stream.write(secrets.token_hex(32))
    secret=path.read_text().strip()
    if not re.fullmatch(r'[a-f0-9]{64}',secret):
        raise RuntimeError('PFMS session key is invalid. Restore the local key file before starting the app.')
    if path.stat().st_mode & 0o077:os.chmod(path,0o600)
    return secret


def csrf_token():
    token=session.get('_csrf_token')
    if not token:
        token=secrets.token_hex(32)
        session['_csrf_token']=token
    return token


def protect_request():
    # Reject forged hostnames used by DNS rebinding to reach a local service.
    if urlsplit(request.host_url).hostname not in {'127.0.0.1','localhost'}:
        abort(400,description='Open PFMS using http://127.0.0.1:5001 on this computer.')
    if request.method in {'GET','HEAD','OPTIONS'}:return None
    origin=request.headers.get('Origin')
    if origin and origin.rstrip('/')!=request.host_url.rstrip('/'):
        abort(400,description='This submission came from another website. Open PFMS and submit the form there.')
    if request.headers.get('Sec-Fetch-Site')=='cross-site':
        abort(400,description='Open PFMS and submit the form there.')
    expected=session.get('_csrf_token','')
    submitted=request.form.get('csrf_token') or request.headers.get('X-CSRF-Token','')
    if not re.fullmatch(r'[a-f0-9]{64}',submitted) or not expected or not hmac.compare_digest(expected,submitted):
        abort(400,description='This form has expired or could not be verified. Reload the PFMS page and try again. Nothing was saved.')


def configure_security(app):
    app.secret_key=load_secret(Path(db.DB_PATH).parent/'.session_secret')
    app.config.update(DEBUG=False, SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE='Strict')
    app.jinja_env.globals['csrf_token']=csrf_token
    app.before_request(protect_request)

    @app.after_request
    def security_headers(response):
        response.headers['X-Content-Type-Options']='nosniff'
        response.headers['X-Frame-Options']='DENY'
        response.headers['Content-Security-Policy']="frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
        response.headers['Referrer-Policy']='same-origin'
        if response.mimetype=='text/html':response.headers['Cache-Control']='no-store'
        return response

    @app.errorhandler(400)
    def bad_request(error):
        return render_template('security_error.html',message=error.description),400
