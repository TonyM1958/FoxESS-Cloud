#! /usr/bin/zsh
pip install random-user-agent --quiet --root-user-action=ignore
cd ${1:-.}
python << END

import foxess as f
f.get_device()
f.set_pvoutput(tou=1, today=${2:-False})

END