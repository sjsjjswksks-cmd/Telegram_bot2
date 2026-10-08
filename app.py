import os,json,time,uuid,shutil,signal,subprocess,threading,html,zipfile,re,base64,hmac,secrets
from pathlib import Path
from urllib.parse import parse_qs
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer

BASE=Path(os.getenv("DATA_DIR","data")); FILES=BASE/"files"; LOGS=BASE/"logs"
FILES.mkdir(parents=True,exist_ok=True); LOGS.mkdir(parents=True,exist_ok=True)
DB=BASE/"files.json"; PROCESSES={}
ADMIN_USER=os.getenv("ADMIN_USER","admin")
ADMIN_PASSWORD=os.getenv("ADMIN_PASSWORD") or secrets.token_urlsafe(12)
if not os.getenv("ADMIN_PASSWORD"): print("ADMIN_PASSWORD not set. Temporary password:",ADMIN_PASSWORD,flush=True)

def db():
    try:return json.loads(DB.read_text("utf-8")) if DB.exists() else {}
    except:return {}
def save(x):
    t=DB.with_suffix(".tmp"); t.write_text(json.dumps(x,ensure_ascii=False,indent=2),"utf-8"); t.replace(DB)
def allowed(n): return Path(n).suffix.lower() in {".py",".js",".php",".sh",".zip"}
def stop(fid):
    x=PROCESSES.pop(fid,None)
    if not x:return
    p,f=x
    try: os.killpg(p.pid,signal.SIGTERM)
    except: 
        try:p.terminate()
        except:pass
    try:f.close()
    except:pass
def run(fid,p,ext):
    cmds={".py":["python3",str(p)],".js":["node",str(p)],".php":["php",str(p)],".sh":["bash",str(p)]}
    if ext not in cmds:return "ZIP uploaded; extract only."
    f=open(LOGS/f"{fid}.log","a",encoding="utf-8")
    try:
        q=subprocess.Popen(cmds[ext],stdout=f,stderr=subprocess.STDOUT,start_new_session=True)
        PROCESSES[fid]=(q,f); return f"Running (PID {q.pid})"
    except Exception as e:
        f.write(str(e)); f.close(); return "Error: "+str(e)
def monitor():
    while 1:
        for fid,(p,f) in list(PROCESSES.items()):
            if p.poll() is not None:
                try:f.write(f"\nEXIT {p.returncode}\n");f.close()
                except:pass
                PROCESSES.pop(fid,None)
        time.sleep(5)
threading.Thread(target=monitor,daemon=True).start()

def page():
    rows=[]
    for fid,x in reversed(list(db().items())):
        live=fid in PROCESSES and PROCESSES[fid][0].poll() is None
        rows.append(f"<tr><td>{html.escape(x['name'])}</td><td>{x['type'].upper()}</td><td>{'🟢 Running' if live else '🔴 Stopped'}</td><td><a href='/logs?id={fid}'>Logs</a> | <a href='/action?op=stop&id={fid}'>Stop</a> | <a href='/action?op=delete&id={fid}'>Delete</a></td></tr>")
    return """<!doctype html><html lang="fa" dir="rtl"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Python Bot Builder</title><style>body{font-family:Arial;max-width:1050px;margin:25px auto;padding:15px;background:#f4f4f4}.card{background:#fff;padding:20px;border-radius:14px;margin-bottom:18px;box-shadow:0 2px 10px #ddd}table{width:100%;border-collapse:collapse}td,th{padding:10px;border-bottom:1px solid #ddd}input,button{padding:10px;margin:5px}</style><div class="card"><h1>🤖 ربات‌ساز Python</h1><p>پنل Railway/VPS بدون FastAPI و Flask</p><form action="/upload" method="post" enctype="multipart/form-data"><input type="file" name="file" required><button>📤 آپلود و اجرا</button></form><p><a href="/health">Health</a></p></div><div class="card"><h2>📋 فایل‌ها</h2><table><tr><th>نام</th><th>نوع</th><th>وضعیت</th><th>مدیریت</th></tr>""" + "".join(rows) + """</table></div></html>"""

class H(BaseHTTPRequestHandler):
    def authed(self):
        h=self.headers.get("Authorization","")
        try:
            u,_,p=base64.b64decode(h.split(" ",1)[1]).decode().partition(":")
            if hmac.compare_digest(u,ADMIN_USER) and hmac.compare_digest(p,ADMIN_PASSWORD):return True
        except Exception:pass
        self.send_response(401);self.send_header("WWW-Authenticate",'Basic realm="Panel"');self.send_header("Content-Length","0");self.end_headers();return False
    def out(self,c,b,typ="text/html; charset=utf-8"):
        z=b.encode();self.send_response(c);self.send_header("Content-Type",typ);self.send_header("Content-Length",str(len(z)));self.end_headers();self.wfile.write(z)
    def do_GET(self):
        p,_,s=self.path.partition("?");q=parse_qs(s)
        if p=="/health":return self.out(200,json.dumps({"ok":True,"running":len(PROCESSES)}),"application/json")
        if not self.authed():return
        if p=="/":return self.out(200,page())
        if p=="/logs":
            fid=q.get("id",[""])[0]; f=LOGS/f"{fid}.log"; c=f.read_text("utf-8",errors="replace")[-12000:] if f.exists() else "No log"
            return self.out(200,"<pre dir='ltr'>"+html.escape(c)+"</pre><a href='/'>بازگشت</a>")
        if p=="/action":
            op=q.get("op",[""])[0];fid=q.get("id",[""])[0];D=db()
            if op=="stop":stop(fid)
            if op=="delete":
                stop(fid);x=D.pop(fid,None);save(D)
                if x:
                    try:shutil.rmtree(Path(x["path"]).parent)
                    except:pass
            self.send_response(303);self.send_header("Location","/");self.end_headers();return
        self.out(404,"Not Found")
    def do_POST(self):
        if self.path!="/upload":return self.out(404,"Not Found")
        if not self.authed():return
        n=int(self.headers.get("Content-Length","0"))
        if n>55*1024*1024:return self.out(413,"File too large")
        b=self.rfile.read(n);m=re.search(br'filename="([^"]*)"',b)
        name=Path((m.group(1).decode("utf-8","ignore") if m else "upload")).name
        if not allowed(name):return self.out(400,"Only py/js/php/sh/zip")
        sep=self.headers.get("Content-Type","").split("boundary=")[-1].encode()
        parts=b.split(b"--"+sep); data=None
        for part in parts:
            if b'name="file"' in part and b"\r\n\r\n" in part:data=part.split(b"\r\n\r\n",1)[1].rsplit(b"\r\n",1)[0];break
        if data is None:return self.out(400,"File missing")
        fid="file_"+time.strftime("%Y%m%d%H%M%S")+"_"+uuid.uuid4().hex[:6];folder=FILES/fid;folder.mkdir();target=folder/name;target.write_bytes(data)
        D=db();D[fid]={"id":fid,"name":name,"type":Path(name).suffix[1:],"path":str(target),"created":time.time()}
        if target.suffix.lower()==".zip":
            try:
                with zipfile.ZipFile(target) as z:z.extractall(folder/"extracted")
            except Exception as e:D[fid]["error"]=str(e)
        else:D[fid]["status"]=run(fid,target,target.suffix.lower())
        save(D);self.send_response(303);self.send_header("Location","/");self.end_headers()

if __name__=="__main__":
    ThreadingHTTPServer(("0.0.0.0",int(os.getenv("PORT","8080"))),H).serve_forever()
