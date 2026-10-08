"""Start or reuse this local PFMS instance without terminating other processes."""
from pathlib import Path
import fcntl, hashlib, json, os, socket, subprocess, sys, time, urllib.request

ROOT=Path(__file__).resolve().parent
URL='http://127.0.0.1:5001'
IDENTITY=hashlib.sha256(str(ROOT).encode()).hexdigest()

def healthy():
    try:
        with urllib.request.urlopen(URL+'/health',timeout=1) as response:
            data=json.load(response)
        return data.get('app')=='PFMS' and data.get('instance')==IDENTITY
    except (OSError,ValueError):return False

def occupied():
    with socket.socket() as sock:
        sock.settimeout(1)
        return sock.connect_ex(('127.0.0.1',5001))==0

def launch():
    runtime=ROOT/'.runtime';runtime.mkdir(mode=0o700,exist_ok=True)
    with (runtime/'launch.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        if healthy():return 'PFMS is already running.'
        if occupied():
            raise RuntimeError('Port 5001 is occupied by a service that could not be verified as this PFMS app. No process was stopped. Close that service or ask for help, then retry.')
        check=subprocess.run([sys.executable,'-c','import flask, reportlab'],capture_output=True,text=True)
        if check.returncode:
            raise RuntimeError('The configured Python environment is missing Flask or ReportLab. Install requirements.txt using '+sys.executable+'. Details: '+check.stderr.strip())
        with (runtime/'server.log').open('ab') as log:
            process=subprocess.Popen([sys.executable,'-B',str(ROOT/'app.py')],cwd=ROOT,
                stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
        (runtime/'server.pid').write_text(str(process.pid))
        deadline=time.monotonic()+30
        while time.monotonic()<deadline:
            if healthy():return 'PFMS is ready.'
            if process.poll() is not None:
                raise RuntimeError('PFMS could not start. See '+str(runtime/'server.log'))
            time.sleep(.25)
        raise RuntimeError('PFMS did not become ready within 30 seconds. See '+str(runtime/'server.log')+'. No unrelated process was stopped.')

def main():
    try:
        print(launch())
        result=subprocess.run(['/usr/bin/open',URL])
        if result.returncode:print('Open '+URL+' in your browser.')
        return 0
    except (OSError,RuntimeError) as error:
        print('PFMS startup error: '+str(error),file=sys.stderr)
        return 1

if __name__=='__main__':sys.exit(main())
