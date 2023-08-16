import foxess as f
import private as my
f.debug_setting = 1

# setup your Fox ESS Cloud username and password here if you have not added them to private.py
f.username = my.username
f.password = my.password
f.api_key = my.api_key
f.system_id = my.system_id

# upload data
f.set_pvoutput(tou=1)
