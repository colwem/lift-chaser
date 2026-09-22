import sys,json; sys.path.insert(0,'/home/claude/soar')
from data import OPS, FLEET
from gliders import TYPES, type_key
fleet=[list(f)+[type_key(f[1])] for f in FLEET]
rasp={o['id']:'https://www.soargbsc.net/rasp/' for o in OPS if o['region']=='New England' or o['id'] in ('ASA',)}
t=open('/home/claude/soar/map_template.html').read()
t=t.replace('__OPS__',json.dumps(OPS)).replace('__FLEET__',json.dumps(fleet)).replace('__TYPES__',json.dumps(TYPES)).replace('__RASP__',json.dumps(rasp))
open('/mnt/user-data/outputs/Chase-Lift Map.html','w').write(t); print('ok')
