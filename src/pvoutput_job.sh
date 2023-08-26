#! /usr/bin/bash
pip install random-user-agent --root-user-action=ignore --quiet
pip install foxesscloud --root-user-action=ignore --quiet

cat >script.py << EOF

import foxesscloud.foxesscloud as f
f.username = $FOX_USERNAME
f.password = $FOX_PASSWORD
f.device_sn = $FOX_DEVICE_SN

f.pv_api_key = $PV_API_KEY
f.pv_system_id = $PV_SYSTEM_ID

f.solcast_api_key = $SOLCAST_API_KEY
f.solcast_rids = $SOLCAST_RIDS

f.set_pvoutput(tou=1, today=False)
f.set_pvoutput(tou=1, today=True)

f.charge_needed($CHARGE_PARAMS)

EOF

python script.py