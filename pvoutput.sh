#! /usr/bin/zsh
: ${1:=.}
pip install random-user-agent --quiet --root-user-action=ignore
cd $1
python << END

import foxess as f
f.set_pvoutput(tou=1)

END
