#!/bin/bash
python3 - <<'PY'
import subprocess, xml.etree.ElementTree as ET
x = subprocess.run(["onetemplate","show","vrouter","-x"],capture_output=True,text=True).stdout
t = ET.fromstring(x).find("TEMPLATE")
def emit(e, ind=""):
    kids = [k for k in e if k.tag!="TOKEN" and "ONEGATE" not in k.tag]
    if not kids: return f'{ind}{e.tag}="{(e.text or "").replace(chr(34), chr(92)+chr(34))}"'
    return f'{ind}{e.tag}=[\n' + ",\n".join(emit(k, ind+"  ") for k in kids) + " ]"
out=[]
for c in t:
    if c.tag in ("USER_INPUTS","INPUTS_ORDER"): continue
    out.append(emit(c))
open("/tmp/vr_clean.tpl","w").write("NAME=\"vrouter-clean\"\n"+"\n".join(out)+"\n")
PY
grep -c . /tmp/vr_clean.tpl
onetemplate delete vrouter-clean </dev/null 2>/dev/null; onetemplate create /tmp/vr_clean.tpl </dev/null
onevrouter instantiate vr1 vrouter-clean --name vr1-vm -m 1 </dev/null 2>&1 | tail -3
sleep 40; onevm list </dev/null
onevm show vr1-vm </dev/null | grep -E "^STATE|LCM_STATE|NAT4|ROUTER4|ETH._IP|ETH._MAC"
