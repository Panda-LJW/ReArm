import sys,json,urllib.request,time
base=sys.argv[1]
def cmd(name,payload=None):
    r=urllib.request.Request(base+"/api/command/"+name,data=json.dumps(payload or {}).encode(),headers={"Content-Type":"application/json"},method="POST")
    try: return json.load(urllib.request.urlopen(r,timeout=300))
    except Exception as e:
        try: return {"err":e.read().decode()}
        except Exception: return {"err":str(e)}
for i in range(60):
    try: urllib.request.urlopen(base+"/api/state",timeout=2); break
    except Exception: time.sleep(0.5)
steps=[("baseline",{})]+[("selfcheck",{})]*16+[("retrain",{}),("selfcheck",{}),("inject",{"kind":"j1","amount":1}),("selfcheck",{}),("selfcheck",{}),("inject",{"kind":"restore","amount":0}),("selfcheck",{}),("selfcheck",{}),("inject",{"kind":"j1","amount":1}),("selfcheck",{}),("selfcheck",{}),("inject",{"kind":"restore","amount":0}),("selfcheck",{}),("selfcheck",{})]
for n,p in steps:
    out=cmd(n,p); s=json.load(urllib.request.urlopen(base+"/api/state")); print(n, out.get("err","ok")[:80], "| shots",s["shots"],s["state"],s["head"]["id"],s["head"]["residual_id"])
