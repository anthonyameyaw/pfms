import ast
import re
import secrets
import tempfile
import unittest
from pathlib import Path
from flask.testing import FlaskClient
import test_financials as base
from database import db
from database.security import load_secret

class SecurityTests(unittest.TestCase):
    setUp=base.FinancialTests.setUp
    def raw(self):return FlaskClient(base.app,base.app.response_class)
    def token(self,client):
        html=client.get('/transport/maintenance/add').get_data(as_text=True)
        return re.search(r'name="csrf_token" value="([a-f0-9]+)"',html).group(1)
    def form(self,token=None):
        data=dict(date='2026-10-02',cost='10')
        if token is not None:data['csrf_token']=token
        return data
    def test_missing_wrong_and_other_session_tokens_reject_without_writes(self):
        client=self.raw();other=self.raw()
        foreign=self.token(other);own=self.token(client)
        for token in [None,'bad','☃',foreign]:
            response=client.post('/transport/maintenance/add',data=self.form(token))
            self.assertEqual(response.status_code,400)
            self.assertIn('Submission not saved',response.get_data(as_text=True))
        self.assertEqual(db.query('SELECT * FROM pickup_maintenance'),[])
        self.assertEqual(client.post('/transport/maintenance/add',data=self.form(own)).status_code,302)
        self.assertEqual(len(db.query('SELECT * FROM pickup_maintenance')),1)
    def test_delete_requires_token(self):
        tid=db.execute("INSERT INTO pickup_maintenance(date,cost) VALUES('2026-10-02',10)")
        client=self.raw()
        self.assertEqual(client.post('/transport/maintenance/%s/delete'%tid).status_code,400)
        self.assertEqual(len(db.query('SELECT * FROM pickup_maintenance')),1)
        self.assertEqual(client.post('/transport/maintenance/%s/delete'%tid,data={'csrf_token':self.token(client)}).status_code,302)
        self.assertEqual(db.query('SELECT * FROM pickup_maintenance'),[])
    def test_cross_origin_and_forged_host_are_rejected(self):
        client=self.raw();token=self.token(client)
        for headers in [{'Origin':'https://example.com'},{'Origin':'null'},{'Sec-Fetch-Site':'cross-site'}]:
            self.assertEqual(client.post('/transport/maintenance/add',data=self.form(token),headers=headers).status_code,400)
        self.assertEqual(client.get('/',headers={'Host':'evil.example:5001'}).status_code,400)
        self.assertEqual(db.query('SELECT * FROM pickup_maintenance'),[])
        self.assertEqual(client.post('/transport/maintenance/add',data=self.form(token),headers={'Origin':'http://localhost'}).status_code,302)
    def test_key_is_private_persistent_and_random(self):
        with tempfile.TemporaryDirectory() as temp:
            a=Path(temp)/'a';b=Path(temp)/'b'
            key=load_secret(a)
            self.assertEqual(key,load_secret(a))
            self.assertNotEqual(key,load_secret(b))
            self.assertEqual(a.stat().st_mode & 0o777,0o600)
    def test_headers_cookie_and_every_template_post_form_has_token(self):
        response=self.raw().get('/transport/add')
        self.assertEqual(response.headers['X-Frame-Options'],'DENY')
        self.assertEqual(response.headers['Cache-Control'],'no-store')
        cookie=response.headers['Set-Cookie']
        self.assertIn('HttpOnly',cookie);self.assertIn('SameSite=Strict',cookie)
        for path in (base.ROOT/'templates').rglob('*.html'):
            forms=re.findall(r'<form\b[^>]*method=["\']POST["\'][^>]*>(.*?)</form>',path.read_text(),re.I|re.S)
            for form in forms:self.assertIn('name="csrf_token"',form,str(path))
    def test_local_only_startup_and_safe_farm_text(self):
        tree=ast.parse((base.ROOT/'app.py').read_text())
        runs=[n for n in ast.walk(tree) if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute) and n.func.attr=='run']
        options={kw.arg:ast.literal_eval(kw.value) for kw in runs[0].keywords}
        self.assertEqual(options['host'],'127.0.0.1');self.assertFalse(options['debug']);self.assertFalse(options['use_reloader'])
        self.assertFalse(base.app.config['DEBUG'])
        for name in ['add','edit']:
            source=(base.ROOT/f'templates/activities/{name}.html').read_text()
            self.assertNotIn('alertText.innerHTML',source)
            self.assertIn('alertText.textContent',source)
