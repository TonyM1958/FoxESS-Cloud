#! /usr/bin/bash
pip install random-user-agent --root-user-action=ignore --quiet
pip install foxesscloud --root-user-action=ignore --quiet

cat >/tmp/script.py << EOF

import foxesscloud.foxesscloud as f
f.username = $FOX_USERNAME
f.password = $FOX_PASSWORD
f.device_sn = $FOX_DEVICE_SN
f.api_key = $PV_API_KEY
f.system_id = $PV_SYSTEM_ID

f.set_pvoutput(tou=1, today=False)
f.set_pvoutput(tou=1, today=True)

EOF

python /tmp/script.py