##################################################################################################
"""
Module:   Fox ESS Cloud
Updated:  06 August 2024
By:       Tony Matthews
"""
##################################################################################################
# Code for getting and setting inverter data via the Fox ESS cloud web site, including
# getting forecast data from solcast.com.au and sending inverter data to pvoutput.org
# ALL RIGHTS ARE RESERVED © Tony Matthews 2023
##################################################################################################

version = "1.4.9"
print(f"FoxESS-Cloud version {version}")

debug_setting = 1

# constants
month_names = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December']
day_names = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']

# global plot parameters
figure_width = 9       # width of plots
legend_location = "upper right"
plot_file = None
plot_no = 0
plot_dpi = 150
plot_bbox = 'tight'
last_plot_filename = None

# show a plot and optionally save as an image to a file
def plot_show():
    global plot_file, plot_no, plot_dpi, plot_bbox, last_plot_filename
    if plot_file is not None:
        last_plot_filename = plot_file.replace('###', f"{plot_no:03d}")
        plt.savefig(last_plot_filename, dpi=plot_dpi, bbox_inches=plot_bbox)
        if '###' in plot_file:
            plot_no += 1
    plt.show()
    return

import os.path
import json
import time
from datetime import datetime, timedelta, timezone
from copy import deepcopy
import requests
from requests.auth import HTTPBasicAuth
import hashlib
#from random_user_agent.user_agent import UserAgent
#from random_user_agent.params import SoftwareName, OperatingSystem
import math
import matplotlib.pyplot as plt

#software_names = [SoftwareName.CHROME.value]
#operating_systems = [OperatingSystem.WINDOWS.value, OperatingSystem.LINUX.value]
#user_agent_rotator = UserAgent(software_names=software_names, operating_systems=operating_systems, limit=100)

fox_domain = "https://www.foxesscloud.com"
fox_client_id = "5245784"
fox_user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
time_zone = 'Europe/London'

##################################################################################################
##################################################################################################
# Fox ESS Cloud API Section
##################################################################################################
##################################################################################################

def query_date(d, offset = None):
    if d is not None and len(d) < 18:
        if len(d) == 10:
            d += ' 00:00:00'
        elif len(d) == 13:
            d += ':00:00'
        else:
            d += ':00'
    try:
        t = datetime.now() if d is None else datetime.strptime(d, "%Y-%m-%d %H:%M:%S")
    except Exception as e:
        output(f"** query_date(): {str(e)}")
        return None
    if offset is not None:
        t += timedelta(days = offset)
    return {'year': t.year, 'month': t.month, 'day': t.day, 'hour': t.hour, 'minute': t.minute, 'second': t.second}

# interpolate a result from a list of values
def interpolate(f, v):
    if len(v) == 0:
        return None
    if f < 0.0:
        return v[0]
    elif f >= len(v) - 1:
        return v[-1]
    i = int(f)
    x = f - i
    return v[i] * (1-x) + v[i+1] * x

# build request header with signing
http_timeout = 55       # http request timeout in seconds
http_tries = 2
response_time = {}

class MockResponse:
    def __init__(self, status_code, reason):
        self.status_code = status_code
        self.reason = reason
        self.json = None

def signed_header(path, login = 0):
    global token_store, debug_setting
    headers = {}
    token = token_store['token'] if login == 0 else ""
    lang = token_store['lang']
    timestamp = str(round(time.time() * 1000))
    headers['Token'] = token
    headers['Lang'] = lang
    headers['User-Agent'] = token_store['user_agent']
    headers['Timezone'] = token_store['time_zone']
    headers['Timestamp'] = timestamp
    headers['Content-Type'] = 'application/json;charset=UTF-8'
    headers['Signature'] = hashlib.md5(fr"{path}\r\n{headers['Token']}\r\n{headers['Lang']}\r\n{headers['Timestamp']}".encode('UTF-8')).hexdigest() + '.' + token_store['client_id']
    output(f"path = {path}", 3)
    output(f"headers = {headers}", 3)
    return headers

def signed_get(path, params = None, login = 0):
    global fox_domain, http_timeout, http_tries, response_time
    message = None
    for i in range(0, http_tries):
        headers = signed_header(path, login)
        try:
            t_now = time.time()
            response = requests.get(url=fox_domain + path, headers=headers, params=params, timeout=http_timeout)
            response_time[path] = time.time() - t_now
            return response
        except Exception as e:
            message = str(e)
            output(f"** signed_get(): {message}\n  path = {path}\n  headers = {headers}")
            continue
    return MockResponse(999, message)

def signed_post(path, data = None, login = 0):
    global fox_domain, http_timeout, http_tries, response_time
    message = None
    for i in range(0, http_tries):
        headers = signed_header(path, login)
        try:
            t_now = time.time()
            response = requests.post(url=fox_domain + path, headers=headers, data=json.dumps(data), timeout=http_timeout)
            response_time[path] = time.time() - t_now
            return response
        except Exception as e:
            message = str(e)
            output(f"** signed_post(): {message}\n  path = {path}\n  headers = {headers}")
            continue
    return MockResponse(999, message)

# implement minimum time between updates for inverter remote settings

update_delay = 2       # delay between inverter setting updates in seconds
update_time = {}       # last inverter setting update time

def setting_delay():
    global update_delay, update_time, device_sn
    sn = device_sn if device_sn is not None else ''
    t_now = time.time()
    t_last = update_time.get(sn)
    delta = t_now - t_last if t_last is not None else update_delay
    if delta < update_delay:
        time.sleep(update_delay - delta)
        t_now = time.time()
        output(f"-- setting_delay() --", 2)
    update_time[sn] = t_now
    return


##################################################################################################
# get error messages
##################################################################################################

messages = None
user_agent = None

def get_messages():
    global debug_setting, messages, fox_user_agent
    output(f"getting messages", 2)
    headers = {'User-Agent': fox_user_agent, 'Content-Type': 'application/json;charset=UTF-8', 'Connection': 'keep-alive'}
    response = signed_get(path="/c/v0/errors/message", login=1)
    if response.status_code != 200:
        output(f"** get_messages() got response code {response.status_code}: {response.reason}")
        return None
    result = response.json().get('result')
    if result is None:
        errno = response.json().get('errno')
        output(f"** get_messages(), no result data, {errno}")
        return None
    messages = result.get('messages')
    return messages

def errno_message(errno, lang='en'):
    global messages
    errno = f"{errno}"
    s = f"errno = {errno}"
    if messages is None or messages.get(lang) is None or messages[lang].get(errno) is None:
        return s
    return s + f": {messages[lang][errno]}"


##################################################################################################
# get login token
##################################################################################################

# global username and password settings
username = None
password = None

token_store = None
token_save = "token.txt"
token_renewal = timedelta(hours=2).seconds       # interval before token needs to be renewed

# login and get token if required. Check if token has expired and renew if required.
def get_token():
    global username, password, fox_user_agent, fox_client_id, time_zone, token_store, device_list, device, device_id, debug_setting, token_save, token_renewal, messages
    if token_store is None:
        token_store = {'token': None, 'valid_from': None, 'valid_for': token_renewal, 'user_agent': fox_user_agent, 'lang': 'en', 'time_zone': time_zone, 'client_id': fox_client_id}
    if token_store['token'] is None and os.path.exists(token_save):
        file = open(token_save)
        token_store = json.load(file)
        file.close()
        if token_store.get('time_zone') is None:
            token_store['time_zone'] = time_zone
        if token_store.get('client_id') is None:
            token_store['client_id'] = fox_client_id
    if messages is None:
        get_messages()
    time_now = datetime.now()
    if token_store.get('token') is not None and token_store['valid_from'] is not None:
        if time_now < datetime.fromisoformat(token_store['valid_from']) + timedelta(seconds=token_store['valid_for']):
            output(f"token is still valid", 3)
            return token_store['token']
    output(f"loading new token", 2)
    device_list = None
    device = None
    if username is None or password is None or username == 'my.fox_username' or password == 'my.fox_password':
        output(f"** please configure your Fox ESS Cloud username and password")
        return None
    credentials = {'user': username, 'password': hashlib.md5(password.encode()).hexdigest()}
    response = signed_post(path="/c/v0/user/login", data=credentials, login=1)
    if response.status_code != 200:
        output(f"** could not login to Fox ESS Cloud - check your username and password - got response code {response.status_code}: {response.reason}")
        return None
    result = response.json().get('result')
    if result is None:
        errno = response.json().get('errno')
        output(f"** get_token(), no result data, {errno_message(errno)}")
        return None
    token_store['token'] = result.get('token')
    if token_store['token'] is None:
        output(f"** no token  in result data")
    token_store['valid_from'] = time_now.isoformat()
    if token_save is not None :
        file = open(token_save, 'w')
        json.dump(token_store, file, indent=4, ensure_ascii=False)
        file.close()
    return token_store['token']

##################################################################################################
# get user / access info
##################################################################################################

info = None

def get_info():
    global token, debug_setting, info, messages
    if get_token() is None:
        return None
    output(f"getting access", 2)
    response = signed_get(path="/c/v0/user/info")
    if response.status_code != 200:
        output(f"** get_info() got info response code {response.status_code}: {response.reason}")
        return None
    result = response.json().get('result')
    if result is None:
        errno = response.json().get('errno')
        output(f"** get_info(), no result data, {errno_message(errno)}")
        return None
    info = result
    response = signed_get(path="/c/v0/user/access")
    if response.status_code != 200:
        output(f"** get_info() got access response code {response.status_code}: {response.reason}")
        return None
    result = response.json().get('result')
    if result is None:
        output(f"** no access result")
        return None
    info['access'] = result['access']
    return info

##################################################################################################
# get status
##################################################################################################

status = None

def get_status(station=0):
    global token, debug_setting, info, messages, status
    if get_token() is None:
        return None
    output(f"getting status", 2)
    path = "/c/v0/device/status/all" if station == 0 else "/c/v0/plant/status/all"
    response = signed_get(path=path)
    if response.status_code != 200:
        output(f"** get_status() got response code {response.status_code}: {response.reason}")
        return None
    result = response.json().get('result')
    if result is None:
        errno = response.json().get('errno')
        output(type(errno))
        output(f"** get_status(), no result data, {errno_message(errno)}")
        return None
    status = result
    return result


##################################################################################################
# get list of sites
##################################################################################################

site_list = None
site = None
station_id = None

def get_site(name=None):
    global token, site_list, site, debug_setting, messages, station_id
    if get_token() is None:
        return None
    if site is not None and name is None:
        return site
    output(f"getting sites", 2)
    site = None
    station_id = None
    query = {'pageSize': 10, 'currentPage': 1, 'total': 0, 'condition': {'status': 0, 'contentType': 2, 'content': ''} }
    response = signed_post(path="/c/v1/plant/list", data=query)
    if response.status_code != 200:
        output(f"** get_sites() got response code {response.status_code}: {response.reason}")
        return None
    result = response.json().get('result')
    if result is None:
        errno = response.json().get('errno')
        output(f"** get_site(), no result data, {errno_message(errno)}")
        return None
    total = result.get('total')
    site_list = result.get('plants')
    if total is None or total == 0 or total > 100 or type(site_list) is not list:
        output(f"** invalid list of sites returned: {total}")
        return None
    n = None
    if len(site_list) > 1:
        if name is not None:
            for i in range(len(site_list)):
                if site_list[i]['name'][:len(name)].upper() == name.upper():
                    n = i
                    break
        if n is None:
            output(f"\nget_site(): please provide a name from the list:")
            for s in site_list:
                output(f"Name={s['name']}")
            return None
    else:
        n = 0
    site = site_list[n]
    station_id = site['stationID']
    return site

##################################################################################################
# get list of data loggers
##################################################################################################

logger_list = None
logger = None

def get_logger(sn=None):
    global token, logger_list, logger, debug_setting, messages
    if get_token() is None:
        return None
    if logger is not None and sn is None:
        return logger
    output(f"getting loggers", 2)
    query = {'pageSize': 100, 'currentPage': 1, 'total': 0, 'condition': {'communication': 0, 'moduleSN': '', 'moduleType': ''} }
    response = signed_post(path="/c/v0/module/list", data=query)
    if response.status_code != 200:
        output(f"** get_logger() got response code {response.status_code}: {response.reason}")
        return None
    result = response.json().get('result')
    if result is None:
        errno = response.json().get('errno')
        output(f"** get_logger(), no result data, {errno_message(errno)}")
        return None
    total = result.get('total')
    if total is None or total == 0 or total > 100:
        output(f"** invalid list of loggers returned: {total}")
        return None
    logger_list = result.get('data')
    n = None
    if len(logger_list) > 1:
        if sn is not None:
            for i in range(len(logger_list)):
                if site_list[i]['moduleSN'][:len(sn)].upper() == sn.upper():
                    n = i
                    break
        if n is None:
            output(f"\nget_logger(): please provide a serial number from this list:")
            for l in logger_list:
                output(f"SN={l['moduleSN']}, Plant={l['plantName']}, StationID={l['stationID']}")
            return None
    else:
        n = 0
    logger = logger_list[n]
    return logger


##################################################################################################
# get list of devices and select one, using the serial number if there is more than 1
##################################################################################################

device_list = None
device = None
device_id = None
device_sn = None
raw_vars = None

def get_device(sn=None):
    global token, device_list, device, device_id, device_sn, firmware, battery, raw_vars, debug_setting, messages, flag, schedule, templates, remote_settings
    if get_token() is None:
        return None
    if device is not None:
        if sn is None:
            return device
        if device_sn[:len(sn)].upper() == sn.upper():
            return device
    output(f"getting device", 2)
    if sn is None and device_sn is not None and len(device_sn) == 15:
        sn = device_sn
    # get device list
    query = {'pageSize': 100, 'currentPage': 1, 'total': 0, 'condition': {'queryDate': {'begin': 0, 'end':0}}}
    response = signed_post(path="/c/v0/device/list", data=query)
    if response.status_code != 200:
        output(f"** get_device() get device list, got response code {response.status_code}: {response.reason}")
        return None
    result = response.json().get('result')
    if result is None:
        errno = response.json().get('errno')
        output(f"** get_device(), no result data, {errno_message(errno)}")
        return None
    total = result.get('total')
    if total is None or total == 0 or total > 100:
        output(f"** invalid list of devices returned: {total}")
        return None
    device_list = result.get('devices')
    # look for the device we want in the list
    n = None
    if len(device_list) == 1 and sn is None:
        n = 0
    else:
        for i in range(len(device_list)):
            if device_list[i]['deviceSN'][:len(sn)].upper() == sn.upper():
                n = i
                break
        if n is None:
            output(f"\nget_device(): please provide a serial number from this list:")
            for d in device_list:
                output(f"SN={d['deviceSN']}, Type={d['deviceType']}")
            return None
    # load information for the device
    device = device_list[n]
    device_id = device.get('deviceID')
    device_sn = device.get('deviceSN')
    battery = None
    battery_settings = None
    schedule = None
    templates = None
    raw_vars = get_vars()
    firmware = get_firmware()
    remote_settings = get_ui()
    # parse the model code to work out attributes
    model_code = device['deviceType'].upper()
    # first 2 letters / numbers e.g. H1, H3, KH
    if model_code[:2] == 'KH':
        model_code = 'KH-' + model_code[2:]
    elif model_code[:4] == 'AIO-':
        model_code = 'AIO' + model_code[4:]
    device['eps'] = 'E' in model_code
    parts = model_code.split('-')
    model = parts[0]
    if model not in ['KH', 'H1', 'AC1', 'H3', 'AC3', 'AIOH1', 'AIOH3']:
        output(f"** device model not recognised for deviceType: {device['deviceType']}")
        return device
    device['model'] = model
    device['phase'] = 3 if model[-1:] == '3' else 1
    for p in parts[1:]:
        if p.replace('.','').isnumeric():
            power = float(p)
            if power >= 1.0 and power < 20.0:
                device['power'] = float(p)
            break
    if device.get('power') is None:
        output(f"** device power not found for deviceType: {device['deviceType']}")
    # set max charge current
    if model in ['KH']:
        device['max_charge_current'] = 50
    elif model in ['H1', 'AC1']:
        device['max_charge_current'] = 35
    elif model in ['H3', 'AC3', 'AIOH3']:
        device['max_charge_current'] = 26
    else:
        device['max_charge_current'] = 40
    return device

##################################################################################################
# get list of raw_data variables for selected device
##################################################################################################

def get_vars():
    global token, device_id, debug_setting, messages
    if get_device() is None:
        return None
    output(f"getting variables", 2)
    params = {'deviceID': device_id}
    # v1 api required for full list with {name, variable, unit}
    response = signed_get(path="/c/v1/device/variables", params=params)
    if response.status_code != 200:
        output(f"** get_vars() got response code {response.status_code}: {response.reason}")
        return None
    result = response.json().get('result')
    if result is None:
        errno = response.json().get('errno')
        output(f"** get_vars(), no result data, {errno_message(errno)}")
        return None
    vars = result.get('variables')
    if vars is None:
        output(f"** no variables list")
        return None
    return vars

##################################################################################################
# get current firmware and protocol versions for selected device
##################################################################################################

firmware = None

def get_firmware():
    global token, device_id, firmware, debug_setting, messages
    if get_device() is None:
        return None
    output(f"getting firmware", 2)
    params = {'deviceID': device_id}
    response = signed_get(path="/c/v0/device/addressbook", params=params)
    if response.status_code != 200:
        output(f"** get_firmware() got response code {response.status_code}: {response.reason}")
        return None
    result = response.json().get('result')
    if result is None:
        errno = response.json().get('errno')
        output(f"** get_firmware(), no result data, {errno_message(errno)}")
        return None
    firmware = result.get('softVersion')
    if firmware is None:
        output(f"** no firmware data")
        return None
    return firmware

##################################################################################################
# get battery info and save to battery
##################################################################################################

battery = None
battery_settings = None
residual_handling = 1 # set to 2 if Residual returns current capacity

def get_battery(info=0):
    global token, device_id, battery, debug_setting, messages
    if get_device() is None:
        return None
    output(f"getting battery", 2)
    params = {'id': device_id}
    response = signed_get(path="/c/v0/device/battery/info", params=params)
    if response.status_code != 200:
        output(f"** get_battery() got response code {response.status_code}: {response.reason}")
        return None
    result = response.json().get('result')
    if result is None:
        errno = response.json().get('errno')
        output(f"** get_battery(), no result data, {errno_message(errno)}")
        return None
    battery = result
    if battery.get('residual') is not None:
        battery['residual'] /=1000
    if residual_handling == 2:
        capacity = battery.get('residual')
        soc = battery.get('soc')
        battery['residual'] = capacity * soc / 100 if capacity is not None and soc is not None else capacity
    if info == 1:
        response = signed_get(path="/generic/v0/device/battery/list", params=params)
        if response.status_code != 200:
            output(f"** get_battery().info got response code {response.status_code}: {response.reason}")
        else:
            result = response.json().get('result')
            if result is None:
                errno = response.json().get('errno')
                output(f"** get_battery().info, no result data, {errno_message(errno)}")
            else:
                battery['info'] = result['batteries']
    return battery

##################################################################################################
# get charge times and save to battery_settings
##################################################################################################

def get_charge():
    global token, device_sn, battery_settings, debug_setting, messages
    if get_device() is None:
        return None
    if battery_settings is None:
        battery_settings = {}
    output(f"getting charge times", 2)
    params = {'sn': device_sn}
    response = signed_get(path="/c/v0/device/battery/time/get", params=params)
    if response.status_code != 200:
        output(f"** get_charge() got response code {response.status_code}: {response.reason}")
        return None
    result = response.json().get('result')
    if result is None:
        errno = response.json().get('errno')
        output(f"** get_charge(), no result data, {errno_message(errno)}")
        return None
    times = result.get('times')
    if times is None:
        errno = response.json().get('errno')
        output(f"** get_charge(), no times data, {errno_message(errno)}")
        return None
    battery_settings['times'] = times
    return battery_settings


##################################################################################################
# set charge times from battery_settings or parameters
##################################################################################################

# helper to format time period structure
def time_period(t):
    result = f"{t['startTime']['hour']:02d}:{t['startTime']['minute']:02d} - {t['endTime']['hour']:02d}:{t['endTime']['minute']:02d}"
    if t['startTime']['hour'] != t['endTime']['hour'] or t['startTime']['minute'] != t['endTime']['minute']:
        result += f" Charge from grid" if t['enableGrid'] else f" Force Charge"
    return result

def set_charge(ch1 = None, st1 = None, en1 = None, ch2 = None, st2 = None, en2 = None, adjust = 0, force = 0):
    global token, device_sn, battery_settings, debug_setting, messages, schedule
    if get_device() is None:
        return None
    if battery_settings is None:
        battery_settings = {}
    if battery_settings.get('times') is None:
        battery_settings['times'] = []
        battery_settings['times'].append({'tip': '', 'enableCharge': True, 'enableGrid': False, 'startTime': {'hour': 0, 'minute': 0}, 'endTime': {'hour': 0, 'minute': 0}})
        battery_settings['times'].append({'tip': '', 'enableCharge': True, 'enableGrid': False, 'startTime': {'hour': 0, 'minute': 0}, 'endTime': {'hour': 0, 'minute': 0}})
    if get_flag() is None:
        return None
    if schedule.get('enable') == True:
        if force == 0:
            output(f"** set_charge(): cannot set charge when a schedule is enabled")
            return None
        set_schedule(enable=0)
    # configure time period 1
    if st1 is not None:
        if st1 == en1:
            st1 = 0
            en1 = 0
            ch1 = False
        else:
            st1 = round_time(time_hours(st1) + adjust)
            en1 = round_time(time_hours(en1) + adjust)
        battery_settings['times'][0]['enableCharge'] = True
        battery_settings['times'][0]['enableGrid'] = True if ch1 == True or ch1 == 1 else False
        battery_settings['times'][0]['startTime']['hour'] = int(st1)
        battery_settings['times'][0]['startTime']['minute'] = int(60 * (st1 - int(st1)) + 0.5)
        battery_settings['times'][0]['endTime']['hour'] = int(en1)
        battery_settings['times'][0]['endTime']['minute'] = int(60 * (en1 - int(en1)) + 0.5)
    # configure time period 2
    if st2 is not None:
        if st2 == en2:
            st2 = 0
            en2 = 0
            ch2 = False
        else:
            st2 = round_time(time_hours(st2) + adjust)
            en2 = round_time(time_hours(en2) + adjust)
        battery_settings['times'][1]['enableCharge'] = True
        battery_settings['times'][1]['enableGrid'] = True if ch2 == True or ch2 == 1 else False
        battery_settings['times'][1]['startTime']['hour'] = int(st2)
        battery_settings['times'][1]['startTime']['minute'] = int(60 * (st2 - int(st2)) + 0.5)
        battery_settings['times'][1]['endTime']['hour'] = int(en2)
        battery_settings['times'][1]['endTime']['minute'] = int(60 * (en2 - int(en2)) + 0.5)
    output(f"\nSetting time periods:", 1)
    output(f"   Time Period 1 = {time_period(battery_settings['times'][0])}", 1)
    output(f"   Time Period 2 = {time_period(battery_settings['times'][1])}", 1)
    # set charge times
    data = {'sn': device_sn, 'times': battery_settings.get('times')}
    setting_delay()
    response = signed_post(path="/c/v0/device/battery/time/set", data=data)
    if response.status_code != 200:
        output(f"** set_charge() got response code {response.status_code}: {response.reason}")
        return None
    errno = response.json().get('errno')
    if errno != 0:
        if errno == 44096:
            output(f"** set_charge(), cannot update settings when schedule is active")
        else:
            output(f"** set_charge(), {errno_message(errno)}")
        return None
    else:
        output(f"success", 2) 
    return battery_settings

def charge_periods(st1 = None, en1 = None, st2 = None, en2 = None, adjust=0, min_soc=10, target_soc=None):
    output(f"\nConfiguring schedule",1)
    strategy = get_strategy(min_soc=min_soc)
    periods = []
    for s in strategy:
        periods.append(set_period(segment = s, quiet=0))
    if st1 is not None and en1 is not None and st1 != en1:
        st1 = round_time(time_hours(st1) + adjust)
        en1 = round_time(time_hours(en1) + adjust)
        periods.append(set_period(start = st1, end = en1, mode = 'ForceCharge', min_soc = min_soc, max_soc=trget_soc, quiet=0))
    if st2 is not None and en2 is not None and st2 != en2:
        st2 = round_time(time_hours(st2) + adjust)
        en2 = round_time(time_hours(en2) + adjust)
        mode = 'SelfUse'
        periods.append(set_period(start = st2, end = en2, mode = mode, min_soc = target_soc, quiet=0))
    return periods

##################################################################################################
# get min soc settings and save in battery_settings
##################################################################################################

def get_min():
    global token, device_sn, battery_settings, debug_setting, messages
    if get_device() is None:
        return None
    if battery_settings is None:
        battery_settings = {}
    output(f"getting min soc", 2)
    params = {'sn': device_sn}
    response = signed_get(path="/c/v0/device/battery/soc/get", params=params)
    if response.status_code != 200:
        output(f"** get_min() got response code {response.status_code}: {response.reason}")
        return None
    result = response.json().get('result')
    if result is None:
        errno = response.json().get('errno')
        output(f"** get_min(), no result data, {errno_message(errno)}")
        return None
    battery_settings['minSoc'] = result.get('minSoc')
    battery_settings['minGridSoc'] = result.get('minGridSoc')
    return battery_settings

##################################################################################################
# set min soc from battery_settings or parameters
##################################################################################################

def set_min(minGridSoc = None, minSoc = None, force = 0):
    global token, device_sn, battery_settings, debug_setting, messages
    if get_device() is None:
        return None
    if get_schedule().get('enable'):
        if force == 0:
            output(f"** set_min(): cannot set min SoC mode when a schedule is enabled")
            return None
        set_schedule(enable=0)
    data = {'sn': device_sn}
    if battery_settings is None:
        battery_settings = {}
    if minGridSoc is not None:
        data['minGridSoc'] = minGridSoc
        battery_settings['minGridSoc'] = minGridSoc
    if minSoc is not None:
        data['minSoc'] = minSoc
        battery_settings['minSoc'] = minSoc
    output(f"\nSetting minSoc = {battery_settings.get('minSoc')}, minGridSoc = {battery_settings.get('minGridSoc')}", 1)
    setting_delay()
    response = signed_post(path="/c/v0/device/battery/soc/set", data=data)
    if response.status_code != 200:
        output(f"** set_min() got response code {response.status_code}: {response.reason}")
        return None
    errno = response.json().get('errno')
    if errno != 0:
        if errno == 44096:
            output(f"** cannot update settings when schedule is active")
        else:
            output(f"** set_min(), {errno_message(errno)}")
        return None
    return battery_settings

##################################################################################################
# get times and min soc settings and save in bat_settings
##################################################################################################

def get_settings():
    global battery_settings
    get_charge()
    get_min()
    return battery_settings

##################################################################################################
# get remote settings
##################################################################################################

remote_settings = None              # raw UI info
named_settings = None               # processed UI info
merge_settings = {                  # keys to add
    'WorkMode': {'keys': {
        'h115__': 'operation_mode__work_mode',
        'h116__': 'operation_mode__work_mode',
        'h117__': 'operation_mode__work_mode'
        },
        'values': ['SelfUse', 'Feedin', 'Backup']},
    'BatteryVolt': {'keys': {
        'h115__': ['h115__14', 'h115__15', 'h115__16'],
        'h116__': ['h116__15', 'h116__16', 'h116__17'],
        'h117__': ['h117__15', 'h117__16', 'h117__17']
        },
        'type': 'list',
        'valueType': 'float',
        'unit': 'V'},
    'BatteryTemp': {'keys': {
        'h115__': 'h115__17',
        'h116__': 'h116__18',
        'h117__': 'h117__18',
        },
        'type': 'list',
        'valueType': 'int',
        'unit': '℃'},
}

def get_ui():
    global device_id, debug_setting, messages, remote_settings, named_settings, merge_settings
    if get_device() is None:
        return None
    if remote_settings is None:
        output(f"getting ui settings", 2)
        params = {'id': device_id}
        response = signed_get(path="/generic/v0/device/setting/ui", params=params)
        if response.status_code != 200:
            output(f"** get_ui() got response code {response.status_code}: {response.reason}")
            return None
        result = response.json().get('result')
        if result is None:
            errno = response.json().get('errno')
            output(f"** get_ui(), no result data, {errno_message(errno)}")
            return None
        remote_settings = result
        protocol = remote_settings['protocol'].lower().replace('xx','__')
        named_settings = {'_protocol': protocol}
        output(f"  protocol = {protocol}", 2)
        volt_n = 0
        volt_keys = []
        for p in remote_settings['parameters']:
            if p['name'][:11] == 'BatteryVolt':    # merge BatteryVolts
                output(f"  found {p['name']} with key {p['key']}", 2)
                volt_n += 1
                volt_keys.append(p['key'])
                if volt_n == 3:
                    named_settings['BatteryVolt'] = {'keys': volt_keys, 'type': 'list', 'valueType': 'float', 'unit': p['properties'][0]['unit']}
                elif volt_n > 3:
                    print(f"** get_ui(): more than 3 groups found for BatteryVolt, n={volt_n}")
            elif p['name'][:11] == 'BatteryTemp':
                output(f"  found {p['name']} with key {p['key']}", 2)
                named_settings['BatteryTemp'] = {'keys': p['key'], 'type': 'list', 'valueType': 'int', 'unit': p['properties'][0]['unit']}
            else:
                items = []
                block = p['block'] and len(p['properties']) > 1
                for e in p['properties']:
                    valueType = e['elemType']['valueType']
                    item = {'name': e['key'].replace(protocol,'')} if block else {'key': e['key']} #, 'group': p['name']}
                    if e['elemType'].get('uiItems') is not None:
                        item['values'] = e['elemType']['uiItems']
                    elif e.get('range') is not None:
                        item['range'] = e['range']
                        item['valueType'] = 'float' if type(e['range']['hi']) is float else 'int'
                    else:
                        item['type'] = valueType
                    if e.get('unit') is not None and len(e['unit']) > 0:
                        item['unit'] = e['unit']
                    if block:
                        items.append(item)
                    else:
                        named_settings[e['name']] = item
                if block:
                    named_settings[p['name']] = {'key': p['key'], 'type': 'block', 'items': items}
        for name in merge_settings.keys():
            if named_settings.get(name) is None and merge_settings[name]['keys'].get(protocol) is not None:
                named_settings[name] = {'keys': merge_settings[name]['keys'][protocol]}
                for k in merge_settings[name].keys():
                    if k != 'keys':
                        named_settings[name][k] = merge_settings[name][k]
    return remote_settings

def get_remote_settings(key):
    global token, device_id, debug_setting, messages
    if get_device() is None:
        return None
    output(f"getting remote settings", 2)
    if key is None:
        return None
    if type(key) is list:
        values = {}
        for k in key:
            v = get_remote_settings(k)
            if v is None:
                return
            for x in v.keys():
                values[x] = v[x]
        return values
    params = {'id': device_id, 'hasVersionHead': 1, 'key': key}
    response = signed_get(path="/c/v0/device/setting/get", params=params)
    if response.status_code != 200:
        output(f"** get_remote_settings() got response code {response.status_code}: {response.reason}")
        return None
    result = response.json().get('result')
    if result is None:
        errno = response.json().get('errno')
        output(f"** get_remote_settings(), no result data, {errno_message(errno)}")
        return None
    values = result.get('values')
    if values is None:
        output(f"** get_remote_settings(), no values data")
        return None
    return values

def get_named_settings(name):
    global named_settings
    if type(name) is list:
        result = []
        for n in name:
            result.append(get_named_settings(n))
        return result
    if named_settings is None or named_settings.get(name) is None:
        output(f"** get_named_settings(): {name} was not recognised")
        return None
    keys = named_settings[name].get('keys')
    if keys is None:
        output(f"** get_named_settings(): no keys for name: {name}")
        return None
    output(f"getting named_settings for {name} using {keys}", 2)
    result = get_remote_settings(keys)
    if result is None:
        output(f"** get_named_settings(): no result for {name} using key: {keys}")
        return None
    result_type = named_settings[name].get('type')
    value_type = named_settings[name].get('valueType')
    if result_type is None:
        v = result.get([k for k in result.keys()][0])
        return v if value_type is None else c_float(v) if value_type == 'float' else c_int(v)
    if result_type == 'list':
        values = []
        for k in sorted(result.keys()):
            values.append(result[k] if value_type is None else c_float(result[k]) if value_type == 'float' else c_int(result[k]))
        return values
    return result

##################################################################################################
# wrappers for named settings
##################################################################################################

work_mode = None

def get_work_mode():
    global work_mode
    if get_device() is None:
        return None
    work_mode = get_named_settings('WorkMode')
    return work_mode

def get_cell_volts():
    values = get_named_settings('BatteryVolt')
    if values is None:
        return None
    return [v for v in values if v > 0]

temp_slots_per_battery = 8

def get_cell_temps(nbat=8):
    global temp_slots_per_battery
    values = get_named_settings('BatteryTemp')
    if values is None:
        return None
    cell_temps = []
    bat_temps = []
    n = 0
    for v in values:
        if v > -50:
            cell_temps.append(v)
        n += 1
        if n % temp_slots_per_battery == 0:
            bat_temps.append(cell_temps)
            cell_temps = []
        if n > nbat * temp_slots_per_battery:
            break
    return bat_temps


##################################################################################################
# set work mode
##################################################################################################

work_modes = ['SelfUse', 'Feedin', 'Backup', 'ForceCharge', 'ForceDischarge']
settable_modes = work_modes[:3]

def set_work_mode(mode, force = 0):
    global token, device_id, work_modes, work_mode, debug_setting, messages, schedule
    if get_device() is None:
        return None
    if mode not in settable_modes:
        output(f"** work mode: must be one of {settable_modes}")
        return None
    if get_flag() is None:
        return None
    if schedule.get('enable') == True:
        if force == 0:
            output(f"** set_work_mode(): cannot set work mode when a schedule is enabled")
            return None
        set_schedule(enable=0)
    output(f"\nSetting work mode: {mode}", 1)
    data = {'id': device_id, 'key': 'operation_mode__work_mode', 'values': {'operation_mode__work_mode': mode}, 'raw': ''}
    setting_delay()
    response = signed_post(path="/c/v0/device/setting/set", data=data)
    if response.status_code != 200:
        output(f"** set_work_mode() got response code {response.status_code}: {response.reason}")
        return None
    errno = response.json().get('errno')
    if errno != 0:
        if errno == 44096:
            output(f"** cannot update settings when schedule is active")
        else:
            output(f"** set_work_mode(), {errno_message(errno)}")
        return None
    work_mode = mode
    return work_mode


##################################################################################################
# get schedule
##################################################################################################

schedule = None
templates = None

# get the current enable flag
def get_flag():
    global token, device_id, device_sn, schedule, debug_setting, messages
    if get_device() is None:
        return None
    if schedule is not None and schedule.get('support') is not None:
        return schedule
    output(f"getting flag", 2)
    params = {'deviceSN': device_sn}
    response = signed_get(path="/generic/v0/device/scheduler/get/flag", params=params)
    if response.status_code != 200:
        output(f"** get_flag() got response code {response.status_code}: {response.reason}")
        return None
    result = response.json().get('result')
    if result is None:
        errno = response.json().get('errno')
        if errno == 40256:
            output(f"** get_flag(), not suported on this device")
        else:
            output(f"** get_flag()), no result data, {errno_message(errno)}")
        return None
    if schedule is None:
        schedule = {'enable': None, 'support': None, 'pollcy': None}
    schedule['enable'] = result.get('enable')
    schedule['support'] = result.get('support')
    output(f"getting modes", 2)
    params = {'deviceID': device_id}
    response = signed_get(path="/generic/v0/device/scheduler/modes/get", params=params)
    if response.status_code != 200:
        output(f"** get_flag() modes got response code {response.status_code}: {response.reason}")
        return None
    result = response.json().get('result')
    if result is None or result.get('fields') is None:
        errno = response.json().get('errno')
        output(f"** get_flag()), no field result data, {errno_message(errno)}")
        return None
    schedule['maxsoc'] = 'maxsoc' in result['fields']
    return schedule

# get the current schedule
def get_schedule():
    global token, device_id, schedule, debug_setting, messages
    if get_flag() is None:
        return None
    if schedule.get('support') == False:
        output(f"** get_schedule(), not supported on this device")
        return None
    output(f"getting schedule", 2)
    params = {'deviceSN': device_sn}
    response = signed_get(path="/generic/v0/device/scheduler/list", params=params)
    if response.status_code != 200:
        output(f"** get_schedule() got response code {response.status_code}: {response.reason}")
        return None
    result = response.json().get('result')
    if result is None:
        errno = response.json().get('errno')
        output(f"** get_schedule(), no result data, {errno_message(errno)}")
        return None
    maxsoc = schedule.get('maxsoc')
    schedule = result
    schedule['maxsoc'] = maxsoc
    return schedule

# get the details for a specific template
def get_template_detail(template):
    global token, device_id, schedule, debug_setting, messages, templates
    if get_flag() is None:
        return None
    if schedule.get('support') == False:
        output(f"** get_template_detail(), not supported on this device")
        return None
    if debug_setting > 1:
        output(f"getting template detail")
    params = {'templateID': template, 'deviceSN': device_sn}
    response = signed_get(path="/generic/v0/device/scheduler/detail", params=params)
    if response.status_code != 200:
        output(f"** get_schedule() got response code {response.status_code}: {response.reason}")
        return None
    result = response.json().get('result')
    if result is None:
        errno = response.json().get('errno')
        output(f"** get_schedule(), no result data, {errno_message(errno)}")
        return None
    return result

# get the preset templates that contains periods
def get_templates(template_type=[1,2]):
    global token, device_id, flag, schedule, debug_setting, messages, templates
    if get_flag() is None:
        return None
    if schedule.get('support') == False:
        output(f"** get_templates(), not supported on this device")
        return None
    if templates is None:
        templates = {}
    if type(template_type) is list:
        for x in template_type:
            get_templates(x)
        return templates
    if debug_setting > 1:
        output(f"getting templates")
    params = {'templateType': template_type, 'deviceSN': device_sn}
    response = signed_get(path="/generic/v0/device/scheduler/edit/list", params=params)
    if response.status_code != 200:
        output(f"** get_templates() got response code {response.status_code}: {response.reason}")
        return None
    result = response.json().get('result')
    if result is None:
        errno = response.json().get('errno')
        output(f"** get_templates(), no result data, {errno_message(errno)}")
        return None
    for t in result['data']:
        id = t['templateID']
        templates[id] = t
        templates[id]['templateType'] = template_type
        detail = get_template_detail(id)
        if detail is not None:
            for d in detail.keys():
                templates[id][d] = detail[d]
    return templates

# search templates for a specific name and return the ID
def find_template(name):
    global templates, debug_setting
    if templates is None:
        get_templates()
    find = '' if name is None else name.replace(' ','').lower()
    found = [k for k in templates.keys() if templates[k]['templateName'][:len(find)].lower() == find]
    if len(found) == 0:
        output(f"** find_template(): no templates found with {name}")
        return None
    if len(found) == 1:
        return found[0]
    output(f"** find_template(): found multiple templates with {name}")
    for k in found:
        output(f"  {templates[k]['templateName']}")
    return None


##################################################################################################
# set schedule
##################################################################################################

# create a period structure. Note: end time is exclusive.
def set_period(start=None, end=None, mode=None, min_soc=None, max_soc=None, fdsoc=None, fdpwr=None, segment=None, quiet=1):
    global schedule
    if schedule is None and get_flag() is None:
        return None
    if segment is not None and type(segment) is dict:
        start = segment.get('start')
        end = segment.get('end')
        mode = segment.get('mode')
        min_soc = segment.get('min_soc')
        max_soc = segment.get('max_soc')
        fdsoc = segment.get('fdsoc')
        fdpwr = segment.get('fdpwr')
    start = time_hours(start)
    # adjust exclusive time to inclusive
    end = round_time(time_hours(end) - 1/60)
    if start is None or end is None or start >= end:
        output(f"set_period(): ** invalid period times: {hours_time(start)} - {hours_time(end)}")
        return None
    mode = 'SelfUse' if mode is None else mode
    if mode not in work_modes:
        output(f"** mode must be one of {work_modes}")
        return None
    min_soc = 10 if min_soc is None else min_soc
    max_soc = None if schedule.get('maxsoc') is None or schedule['maxsoc'] == False else 100 if max_soc is None else max_soc
    fdsoc = min_soc if fdsoc is None else fdsoc
    fdpwr = 0 if fdpwr is None else fdpwr
    if min_soc < 10 or min_soc > 100:
        output(f"set_period(): ** min_soc must be between 10 and 100")
        return None
    if max_soc is not None and (max_soc < 10 or max_soc > 100):
        output(f"set_period(): ** max_soc must be between 10 and 100")
        return None
    if fdpwr < 0 or fdpwr > 6000:
        output(f"set_period(): ** fdpwr must be between 0 and 6000")
        return None
    if fdsoc < min_soc or fdsoc > 100:
        output(f"set_period(): ** fdsoc must between {min_soc} and 100")
        return None
    if quiet == 0:
        if mode == 'ForceDischarge':
            s = f"   {hours_time(start)} to {hours_time(end)} {mode} with minsoc = {min_soc}%, fdPwr = {fdpwr}W, fdSoC = {fdsoc}%"
        else:
            s = f"   {hours_time(start)} to {hours_time(end)} {mode} with minsoc = {min_soc}%"
        s += f", maxsoc = {max_soc}%" if max_soc is not None else ""
        output(s, 1)
    start_h, start_m = split_hours(start)
    end_h, end_m = split_hours(end)
    period = {'startH': start_h, 'startM': start_m, 'endH': end_h, 'endM': end_m, 'workMode': mode, 'minsocongrid': min_soc, 'fdsoc': fdsoc, 'fdpwr': fdpwr}
    if max_soc is not None:
        period['maxsoc'] = max_soc
    return period

# set a schedule from a period or list of periods
def set_schedule(periods=None, template=None, enable=1):
    global token, device_sn, debug_setting, messages, schedule, templates
    if get_flag() is None:
        return None
    if schedule.get('support') == False:
        output(f"** set_schedule(), not supported on this device")
        return None
    if schedule is None:
        schedule = get_schedule()
    output(f"set_schedule(): enable = {enable}, periods = {periods}, template={template}", 2)
    if debug_setting > 2:
        return None
    params = {'deviceSN': device_sn}
    if enable == 0:
        output(f"\nDisabling schedule", 1)
        setting_delay()
        response = signed_get(path="/generic/v0/device/scheduler/disable", params=params)
        if response.status_code != 200:
            output(f"** set_schedule() got disable response code {response.status_code}: {response.reason}")
            return None
        errno = response.json().get('errno')
        if errno != 0:
            output(f"** set_schedule(), disable, {errno_message(errno)}")
            return None
        schedule['enable'] = False
    else:
        template_id = None
        if periods is not None:
            if type(periods) is not list:
                periods = [periods]
            data = {'pollcy': periods, 'deviceSN': device_sn}
            schedule['pollcy'] = periods
            schedule['template_id'] = None
        elif template is not None:
            if templates is None and get_templates() is None:
                return None
            template_id = template if template in templates.keys() else find_template(template)
            if template_id is None:
                return None
            data = {'templateID': template_id, 'deviceSN': device_sn}
            schedule['pollcy'] = None
            schedule['templateID'] = template_id
        else:
            output(f"** set_schedule() requires periods or template parameter")
            return None
        output(f"\nEnabling schedule", 1)
        setting_delay()
        response = signed_post(path="/generic/v0/device/scheduler/enable", data=data)
        if response.status_code != 200:
            output(f"** set_schedule() got enable response code {response.status_code}: {response.reason}")
            return None
        errno = response.json().get('errno')
        if errno != 0:
            output(f"** set_schedule(), enable, {errno_message(errno)}")
            return None
        schedule['enable'] = True
    return schedule


##################################################################################################
# get raw data values
##################################################################################################
# returns a list of variables and their values / attributes
# time_span = 'hour', 'day', 'week'. For 'week', gets history of 7 days up to and including d
# d = day 'YYYY-MM-DD'. Can also include 'HH:MM' in 'hour' mode
# v = list of variables to get
# summary = 0: raw data, 1: add max, min, sum, 2: summarise and drop raw data, 3: calculate state
# save = "xxxxx": save the raw results to xxxxx_raw_<time_span>_<d>.json
# load = "<file>": load the raw results from <file>
# plot = 0: no plot, 1: plot variables separately, 2: combine variables 
# station = 0: use device_id, 1: use station_id
##################################################################################################

# variables that cover inverter power data: generationPower must be first
power_vars = ['generationPower', 'feedinPower','loadsPower','gridConsumptionPower','batChargePower', 'batDischargePower', 'pvPower', 'meterPower2']
#  names after integration of power to energy. List must be in the same order as above. input_daily must be last
energy_vars = ['output_daily', 'feedin_daily', 'load_daily', 'grid_daily', 'bat_charge_daily', 'bat_discharge_daily', 'pv_energy_daily', 'ct2_daily', 'input_daily']

# sample rate setting and rounding in intervals per minute
sample_time = 5.0       # 5 minutes default
sample_rounding = 2     # round to 30 seconds

def get_raw(time_span='hour', d=None, v=None, summary=1, save=None, load=None, plot=0, station=0):
    global token, device_id, debug_setting, raw_vars, off_peak1, off_peak2, peak, invert_ct2, tariff, max_power_kw, messages, sample_rounding, sample_time
    if station == 0 and get_device() is None:
        return None
    elif station == 1 and get_site() is None:
        return None
    id_name = 'deviceID' if station == 0 else 'stationID'
    id_code = device_id if station == 0 else station_id
    time_span = time_span.lower()
    if d is None:
        d = datetime.strftime(datetime.now() - timedelta(minutes=5), "%Y-%m-%d %H:%M:%S" if time_span == 'hour' else "%Y-%m-%d")
    if time_span == 'week' or type(d) is list:
        days = d if type(d) is list else date_list(e=d, span='week',today=True)
        result_list = []
        for day in days:
            result = get_raw('day', d=day, v=v, summary=summary, save=save, plot=0)
            if result is None:
                return None
            result_list += result
        if plot > 0:
            plot_raw(result_list, plot, station)
        return result_list
    if v is None:
        if raw_vars is None:
            raw_vars = get_vars()
        v = [x['variable'] for x in raw_vars]
    elif type(v) is not list:
        v = [v]
    for var in v:
        if var not in [x['variable'] for x in raw_vars]:
            output(f"** get_raw(): invalid variable '{var}'")
            output(f"{[x['variable'] for x in raw_vars]}")
            return None
    output(f"getting raw data", 2)
    if load is None:
        d_begin = query_date(d)
        if d_begin is None:
            return None
        query = {id_name: id_code, 'variables': v, 'timespan': time_span, 'beginDate': d_begin}
        response = signed_post(path="/c/v0/device/history/raw", data=query)
        if response.status_code != 200:
            output(f"** get_raw() got response code {response.status_code}: {response.reason}")
            return None
        result = response.json().get('result')
        errno = response.json().get('errno')
        if errno > 0 or result is None or len(result) == 0:
            output(f"** get_raw(), no raw data, {errno_message(errno)}")
            return None
    else:
        file = open(load)
        result = json.load(file)
        file.close()
    if save is not None:
        file_name = save + "_raw_" + time_span + "_" + d[0:10].replace('-','') + ".txt"
        file = open(file_name, 'w', encoding='utf-8')
        json.dump(result, file, indent=4, ensure_ascii= False)
        file.close()
    for var in result:
        var['date'] = d[0:10]
        # remove 1 hour over-run when clocks go forward 1 hour
        while len(var['data']) > 0 and var['data'][-1]['time'][0:10] != d[0:10]:
            var['data'].pop()
    if 'meterPower2' in v and invert_ct2 == 1:
        ct2_index = v.index('meterPower2')
        for y in result[ct2_index]['data']:
            y['value'] = - y['value']
    if summary <= 0 or time_span == 'hour':
        if summary == -1:     # return last value only for each variable
            for v in result:
                v['time'] = v['data'][-1]['time'][11:16]
                v['value'] = v['data'][-1]['value']
                del v['data']
#                del v['date']
        elif plot > 0:
            plot_raw(result, plot)
        return result
    # integrate kW to kWh based on 5 minute samples
    output(f"calculating summary data", 3)
    # copy generationPower to produce inputPower data
    input_name = None
    if 'generationPower' in v:
        input_name = energy_vars[-1]
        input_result = deepcopy(result[v.index('generationPower')])
        input_result['name'] = input_name
        for y in input_result['data']:
            y['value'] = -y['value'] if y['value'] < 0.0 else 0.0
        result.append(input_result)
    # process results to generate summary
    for var in result:
        energy = var['unit'] == 'kW'
        hour = 0
        if energy:
            kwh = 0.0       # kwh total
            kwh_off = 0.0   # kwh during off peak time (02:00-05:00)
            kwh_peak = 0.0  # kwh during peak time (16:00-19:00)
            kwh_neg = 0.0
            if len(var['data']) > 1:
                sample_time = round(60 * sample_rounding * (time_hours(var['data'][-1]['time'][11:]) - time_hours(var['data'][0]['time'][11:])) / (len(var['data']) - 1), 0) / sample_rounding
            else:
                sample_time = 5.0
            output(f"{var['variable']}: samples = {len(var['data'])}, sample_time = {sample_time} minutes", 2)
        count = 0
        sum = None
        max = None
        max_time = None
        min = None
        min_time = None
        if summary == 3 and energy:
            var['state'] = [{}]
        for y in var['data']:
            h = time_hours(y['time'][11:19]) # time
            value = y.get('value')
            if value is None:
                output(f"** get_raw(), warning: missing data for {var['variable']} at {y['time']}", 1)
                continue
            count += 1
            if type(value) is str:
                continue
            sum = value + (sum if sum is not None else 0.0)
            max = value if max is None or value > max else max
            min = value if min is None or value < min else min
            if energy:
                e = value * sample_time / 60      # convert kW samples to kWh energy
                if e > 0.0:
                    kwh += e
                    if tariff is not None:
                        if hour_in (h, tariff['off_peak1']):
                            kwh_off += e
                        elif hour_in(h, tariff['off_peak2']):
                            kwh_off += e
                        elif hour_in(h, tariff['peak']):
                            kwh_peak += e
                        elif hour_in(h, tariff['peak2']):
                            kwh_peak += e
                else:
                    kwh_neg -= e
                if summary == 3:
                    if int(h) > hour:    # new hour
                        var['state'].append({})
                        hour += 1
                    var['state'][hour]['time'] = y['time'][11:16]
                    var['state'][hour]['state'] = kwh
                var['kwh'] = kwh
                var['kwh_off'] = kwh_off
                var['kwh_peak'] = kwh_peak
                var['kwh_neg'] = kwh_neg
        var['count'] = count
        var['average'] = sum / count if count > 0 and sum is not None else None
        var['max'] = max if max is not None else None
        var['max_time'] = var['data'][[y['value'] for y in var['data']].index(max)]['time'][11:16] if max is not None else None
        var['min'] = min if min is not None else None
        var['min_time'] = var['data'][[y['value'] for y in var['data']].index(min)]['time'][11:16] if min is not None else None
        if summary >= 2:
            if energy and var['variable'] in power_vars and (input_name is None or var['name'] != input_name):
                var['name'] = energy_vars[power_vars.index(var['variable'])]
            if energy:
                var['unit'] = 'kWh'
            del var['data']
    if plot > 0 and summary < 2:
        plot_raw(result, plot, station)
    return result

# plot raw results data
def plot_raw(result, plot=1, station=0):
    global site, device_sn, legend_location, sample_time
    if result is None:
        return
    # work out what we have
    units = []
    vars = []
    dates = []
    for v in result:
        if v.get('data') is not None:
            if v['unit'] not in units:
                units.append(v['unit'])
            if v['variable'] not in vars:
                vars.append(v['variable'])
            if v['date'] not in dates:
                dates.append(v['date'])
    dates = sorted(dates)
    if len(vars) == 0 or len(dates) == 0:
        return
    # plot variables by date with the same units on the same charts
    for unit in units:
        lines = 0
        for d in dates:
            # get time labels for X axis
            if lines == 0:
                plt.figure(figsize=(figure_width, figure_width/3))
                all_x = []
            for v in [v for v in result if v['unit'] == unit and v['date'] == d]:
                n = len(v['data'])
                x = [time_hours(v['data'][i]['time'][11:]) for i in range(0,n)]
                all_x += x
                y = [v['data'][i]['value'] if v['data'][i]['value'] is not None else 0.0 for i in range(0, n)]
                name = v['name']
                label = f"{name} / {d}" if plot == 2 and len(dates) > 1 else name
                plt.plot(x, y ,label=label)
                lines += 1
            if lines >= 1 and (plot == 1 or d == dates[-1]) :
                bst = 1 if  min(all_x) < 0 else 0
                labels = [f"{h:02d}:00" for h in range(0, 25)]
                plt.xticks(ticks=range(0 - bst, 25 - bst), labels=labels, rotation=90, fontsize=8)
                plt.xlim(-1 - bst, 25)
                if lines > 1:
                    plt.legend(fontsize=6, loc=legend_location)
                title = ""
                if plot == 1 or len(dates) == 1 or lines == 1:
                    title = f"{d} / "
                if len(vars) == 1 or lines == 1:
                    title = f"{name} / {title}"
                title = f"{title}{unit} / {site['name'] if station == 1 else device_sn}"
                title += '' if bst == 0 else ' (BST)'
                plt.title(title, fontsize=12)
                plt.grid()
                plot_show()
                lines = 0
    return

##################################################################################################
# get energy report data in kWh
##################################################################################################
# report_type = 'day', 'week', 'month', 'year'
# d = day 'YYYY-MM-DD'
# v = list of report variables to get
# summary = 0, 1, 2: do a quick total energy report for a day
# save = "xxxxx": save the report results to xxxxx_raw_<time_span>_<d>.json
# load = "<file>": load the report results from <file>
# plot = 0: no plot, 1 = plot variables separately, 2 = combine variables
# station = 0: use device_id, 1 = use station_id
##################################################################################################

report_vars = ['yield', 'input','generation', 'feedin', 'loads', 'gridConsumption', 'chargeEnergyToTal', 'dischargeEnergyToTal']
report_names = ['PV Yield', 'Input', 'Generation', 'Grid Export', 'Consumption', 'Grid Import', 'Battery Charge', 'Battery Discharge']

# fix power values after fox corrupts high word of 32-bit energy total
fix_values = 1
fix_value_threshold = 200000000.0
fix_value_mask = 0x0000FFFF

def get_report(report_type='day', d=None, v=None, summary=1, save=None, load=None, plot=0, station=0):
    global token, device_id, station_id, var_list, debug_setting, report_vars, messages, station_id
    if station == 0 and get_device() is None:
        return None
    elif station == 1 and get_site() is None:
        return None
    id_name = 'deviceID' if station == 0 else 'stationID'
    id_code = device_id if station == 0 else station_id
    query_path = '/c/v0/device/history/report' if station == 0 else '/c/v0/plant/history/report'
    # process list of days
    if d is not None and type(d) is list:
        result_list = []
        for day in d:
            result = get_report(report_type, d=day, v=v, summary=summary, save=save, load=load, plot=0)
            if result is None:
                return None
            result_list += result
        if plot > 0:
            plot_report(result_list, plot, station)
        return result_list
    # validate parameters
    report_type = report_type.lower()
    summary = 1 if summary == True else 0 if summary == False else summary
    if summary == 2 and report_type != 'day':
        summary = 1
    if summary == 0 and report_type == 'week':
        report_type = 'day'
    if d is None:
        d = datetime.strftime(datetime.now(), "%Y-%m-%d")
    if v is None:
        v = report_vars
    elif type(v) is not list:
        v = [v]
    for var in v:
        if var not in report_vars:
            output(f"** get_report(): invalid variable '{var}'")
            output(f"{report_vars}")
            return None
    output(f"getting report data", 2)
    current_date = query_date(None)
    main_date = query_date(d)
    if main_date is None:
        return None
    side_result = None
    if report_type in ('day', 'week') and summary > 0:
        # side report needed
        side_date = query_date(d, -7) if report_type == 'week' else main_date
        if report_type == 'day' or main_date['month'] != side_date['month']:
            query = {id_name: id_code, 'reportType': 'month', 'variables': v, 'queryDate': side_date}
            response = signed_post(path=query_path, data=query)
            if response.status_code != 200:
                output(f"** get_report() side report got response code {response.status_code}: {response.reason}")
                return None
            side_result = response.json().get('result')
            errno = response.json().get('errno')
            if errno > 0 or side_result is None or len(side_result) == 0:
                output(f"** get_report(), no report data available, {errno_message(errno)}")
                return None
            if fix_values == 1:
                for var in side_result:
                    for data in var['data']:
                        if data['value'] is None:
                            continue
                        if data['value'] > fix_value_threshold:
                            data['value'] = (int(data['value'] * 10) & fix_value_mask) / 10
    if summary < 2:
        query = {id_name: id_code, 'reportType': report_type.replace('week', 'month'), 'variables': v, 'queryDate': main_date}
        response = signed_post(path=query_path, data=query)
        if response.status_code != 200:
            output(f"** get_report() main report got response code {response.status_code}: {response.reason}")
            return None
        result = response.json().get('result')
        errno = response.json().get('errno')
        if errno > 0 or result is None or len(result) == 0:
            output(f"** get_report(), no report data available, {errno_message(errno)}")
            return None
        # correct errors in report values:
        if fix_values == 1:
            for var in result:
                for data in var['data']:
                    if data['value'] is None:
                        continue
                    if data['value'] > fix_value_threshold:
                        data['value'] = (int(data['value'] * 10) & fix_value_mask) / 10
        # prune results back to only valid, complete data for day, week, month or year
        if report_type == 'day' and main_date['year'] == current_date['year'] and main_date['month'] == current_date['month'] and main_date['day'] == current_date['day']:
            for var in result:
                # prune current day to hours that are valid
                var['data'] = var['data'][:int(current_date['hour'])]
        if report_type == 'week':
            for i, var in enumerate(result):
                # prune results to days required
                var['data'] = var['data'][:int(main_date['day'])]
                if side_result is not None:
                    # prepend side results (previous month) if required
                    var['data'] = side_result[i]['data'][int(side_date['day']):] + var['data']
                # prune to week required
                var['data'] = var['data'][-7:]
        elif report_type == 'month' and main_date['year'] == current_date['year'] and main_date['month'] == current_date['month']:
            for var in result:
                # prune current month to days that are valid
                var['data'] = var['data'][:int(current_date['day'])]
        elif report_type == 'year' and main_date['year'] == current_date['year']:
            for var in result:
                # prune current year to months that are valid
                var['data'] = var['data'][:int(current_date['month'])]
    else:
        # fake result for summary only report
        result = []
        for x in v:
            result.append({'variable': x, 'data': [], 'date': d})
    if load is not None:
        file = open(load)
        result = json.load(file)
        file.close()
    elif save is not None:
        file_name = save + "_rep_" + report_type + "_" + d.replace('-','') + ".txt"
        file = open(file_name, 'w', encoding='utf-8')
        json.dump(result, file, indent=4, ensure_ascii= False)
        file.close()
    if summary == 0:
        return result
    # calculate and add summary data
    for i, var in enumerate(result):
        count = 0
        sum = None
        max = None
        min = None
        for j, y in enumerate(var['data']):
            value = y.get('value')
            if value is None:
                output(f"** get_report(), warning: missing data for {var['variable']} on {d} at index {j}", 1)
                continue
            count += 1
            if type(value) is str:
                continue
            sum = value + (sum if sum is not None else 0.0)
            max = value if max is None or value > max else max
            min = value if min is None or value < min else min
        # correct day total from side report
        var['total'] = sum if report_type != 'day' else side_result[i]['data'][int(main_date['day'])-1]['value']
        var['name'] = report_names[report_vars.index(var['variable'])]
        var['type'] = report_type
        if summary < 2:
            var['sum'] = sum
            var['average'] = var['total'] / count if count > 0 and var['total'] is not None else None
            var['date'] = d
            var['count'] = count
            var['max'] = max if max is not None else None
            var['max_index'] = [y['value'] for y in var['data']].index(max) if max is not None else None
            var['min'] = min if min is not None else None
            var['min_index'] = [y['value'] for y in var['data']].index(min) if min is not None else None
    if plot > 0 and summary < 2:
        plot_report(result, plot, station)
    return result

# plot get_report result
def plot_report(result, plot=1, station=0):
    global site, device_sn, debug_setting
    if result is None:
        return
    # work out what we have
    vars = []
    types = []
    index = []
    dates = []
    for v in result:
        if v.get('data') is not None:
            if v['variable'] not in vars:
                vars.append(v['variable'])
            if v['type'] not in types:
                types.append(v['type'])
            if v['date'] not in dates:
                dates.append(v['date'])
            for i in [x['index'] for x in v['data']]:
                if i not in index:
                    index.append(i)
    output(f"vars = {vars}, dates = {dates}, types = {types}, index = {index}", 3)
    if len(vars) == 0:
        return
    # plot variables by date with the same units on the same charts
    lines = 0
    width = 0.8 / (len(dates) if plot == 1 else len(vars) if len(dates) == 1 else len(dates))
    align = 0.0
    for var in vars:
        if lines == 0:
            plt.figure(figsize=(figure_width, figure_width/3))
            if types[0] == 'day':
                plt.xticks(ticks=index, labels=[hours_time(h) for h in range(0,len(index))], rotation=90, fontsize=8)
            if types[0] == 'week':
                plt.xticks(ticks=range(1,8), labels=date_list(span='week', e=dates[0], today=2), rotation=45, fontsize=8, ha='right', rotation_mode='anchor')
            elif types[0] == 'month':
                plt.xticks(ticks=index, labels=date_list(s=dates[0][:-2]+'01', limit=len(index), today=2), rotation=45, fontsize=8, ha='right', rotation_mode='anchor')
            elif types[0] == 'year':
                plt.xticks(ticks=index, labels=[m[:3] for m in month_names[:len(index)]], rotation=45, fontsize=10, ha='right', rotation_mode='anchor')
        for v in [v for v in result if v['variable'] == var]:
            name = v['name']
            d = v['date']
            n = len(v['data'])
            x = [i + align  for i in range(1, n+1)]
            y = [v['data'][i]['value'] if v['data'][i]['value'] is not None else 0.0 for i in range(0, n)]
            label = f"{d}" if len(dates) > 1 else f"{name}"
            plt.bar(x, y ,label=label, width=width)
            align += width
            lines += 1
        if lines >= 1 and (plot == 1 or len(dates) > 1 or var == vars[-1]):
            if lines > 1:
                plt.legend(fontsize=6, loc=legend_location)
            title = ""
            if types[0] == 'day' and (lines == 1 or len(dates) == 1):
                title = f"{d} / "
            elif types[0] == 'week':
                title = f"Week to {d} / "
            elif types[0] == 'month':
                title = f"Month of {month_names[int(d[5:7])-1]} {d[:4]} / "
            elif types[0] == 'year':
                title = f"Year {d[:4]} / "
            if len(vars) == 1 or plot == 1 or len(dates) > 1:
                title = f"{name} / {title}kWh / "
            else:
                title = f"{title} kWh / "
            title = f"{title}{site['name'] if station == 1 else device_sn}"
            plt.title(title, fontsize=12)
            plt.grid()
            plot_show()
            lines = 0
            align = 0.0
    return

##################################################################################################
# get earnings data
##################################################################################################

def get_earnings():
    global token, device_id, station_id, var_list, debug_setting, messages
    if get_device() is None:
        return None
    id_name = 'deviceID'
    id_code = device_id
    output(f"getting earnings", 2)
    params = {id_name: id_code}
    response = signed_get(path="/c/v0/device/earnings", params=params)
    if response.status_code != 200:
        output(f"** get_earnings() got response code {response.status_code}: {response.reason}")
        return None
    result = response.json()
    if result is None:
        errno = response.json().get('errno')
        output(f"** get_earnings(), no result data, {errno_message(errno)}")
        return None
    return result


##################################################################################################
##################################################################################################
# Operations section
##################################################################################################
##################################################################################################

##################################################################################################
# Time and charge period functions
##################################################################################################
# times are held either as text HH:MM or HH:MM:SS or as decimal hours e.g. 01.:30 = 1.5
# decimal hours allows maths operations to be performed simply

# time shift from UTC (before any DST adjustment)
time_shift = 0

# roll over decimal times after maths and round to 1 minute
def round_time(h):
    if h is None:
        return None
    while h < 0:
        h += 24
    while h >= 24:
        h -= 24
    return int(h) + int(60 * (h - int(h)) + 0.5) / 60

# split decimal hours into hours and minutes
def split_hours(h):
    if h is None:
        return (None, None)
    hours = int(h % 24)
    minutes = int (h % 1 * 60 + 0.5)
    return (hours, minutes)

# convert time string HH:MM:SS to decimal hours (range 0 to 24)
# If BST time zone is included, convert to GMT (range -1 to 23)
def time_hours(t, d = None):
    if t is None:
        if d is None:
            return None
        t = d
    if type(t) is float:
        return t
    if type(t) is int:
        return float(t)
    offset = 1 if 'BST' in t else 0
    t = t[0:8]
    if type(t) is str and t.replace(':', '').isnumeric() and t.count(':') <= 2:
        t += ':00' if t.count(':') == 1 else ''
        return sum(float(t) / x for x, t in zip([1, 60, 3600], t.split(":"))) - offset
    output(f"** invalid time string {t}")
    return None

# convert decimal hours to time string HH:MM:SS
def hours_time(h, ss = False, day = False, mm = True):
    if h is None:
        return "None"
    if type(h) is str:
        h = time_hours(h)
    n = 8 if ss else 5 if mm else 2
    d = 0
    while h < 0:
        h += 24
        d -= 1
    while h >= 24:
        h -= 24
        d += 1
    suffix = ""
    if day:
        suffix = f"/{d:0}"
    return f"{int(h):02}:{int(h * 60 % 60):02}:{int(h * 3600 % 60):02}"[:n] + suffix

# True if a decimal hour falls within a time period
def hour_in(h, period):
    if period is None:
        return False
    s = period.get('start')
    e = period.get('end')
    if s is None or e is None or s == e:
        return False
    while h < 0:
        h += 24
    while h >= 24:
        h -= 24
    if s > e:
        # e.g. 16:00 - 07:00
        return h >= s or h < e
    else:
        # e.g. 02:00 - 05:00
        return h >= s and h < e

# True if 2 time periods overlap
def hour_overlap(period1, period2):
    if period1 is None or period2 is None:
        return False
    s1 = period1.get('start')
    e1 = period1.get('end')
    if s1 is None or e1 is None or s1 == e1:
        return False
    while s1 > e1:
        s1 -= 24
    s2 = period2.get('start')
    e2 = period2.get('end')
    if s2 is None or e2 is None or s2 == e2:
        return False
    while s2 > e2:
        s2 -= 24
    if s1 >= s2 and s1 < e2:
        return True
    if s2 >= s1 and s2 < e1:
        return True
    return False

# Time in a decimal hour that falls within a time period
def duration_in(h, period):
    if period is None:
        return None
    duration = 1.0
    s = period.get('start')
    e = period.get('end')
    if s is None or e is None:
        return None
    if s == e:
        return 0.0
    if e > s and (h >= e or (h + 1) <= s):    # normal time
            return 0.0
    if e < s and (h >= e and (h + 1) <= s):   # wrap around time
            return 0.0
    if s > h and s < (h + 1):
        duration -= (s - h)
    if e > h and e < (h + 1):
        duration -= (h + 1 - e)
    duration = 1.0 if duration > 1.0 else 0.0 if duration < 0.0 else duration
    return duration

# Return the hours in a time period with optional value check
def period_hours(period, check = None, value = 1):
    if period is None:
        return 0
    if check is not None and period[check] != value:
        return 0
    return round_time(period['end'] - period['start'])

def format_period(period):
    return f"{hours_time(period['start'])} - {hours_time(period['end'])}"

#work out if a date falls in BST or GMT. Returns 1 for BST, 0 for GMT
def british_summer_time(d=None):
    if type(d) is list:
        l = []
        for x in d:
            l.append(british_summer_time(x))
        return l
    elif type(d) is str:
        dat = datetime.strptime(d[:10], '%Y-%m-%d')
        hour = int(d[11:13]) if len(d) >= 16 else 12
    else:
        now = datetime.now(tz=timezone.utc)
        dat =  d.date() if d is not None else now.date()
        hour = d.hour if d is not None else now.hour 
    start_date = dat.replace(month=3, day=31)
    days = (start_date.weekday() + 1) % 7
    start_date = start_date - timedelta(days=days)
    end_date = dat.replace(month=10, day=31)
    days = (end_date.weekday() + 1) % 7
    end_date = end_date - timedelta(days=days)
    if dat == start_date and hour < 1:
        return 0
    elif dat == end_date and hour < 1:
        return 1
    elif dat >= start_date and dat < end_date:
        return 1
    return 0

# hook for alternative daylight saving methods
daylight_saving = british_summer_time

# helper function to return change in daylight saving between 2 datetimes
def daylight_changes(a,b):
    return daylight_saving(a) - daylight_saving(b)


##################################################################################################
# TARIFFS - charge periods and time of user (TOU)
# time values are decimal hours
##################################################################################################

# time periods for Octopus Flux
octopus_flux = {
    'name': 'Octopus Flux',
    'off_peak1': {'start': 2.0, 'end': 5.0, 'force': 1},        # off-peak period 1 / am charging period
    'off_peak2': {'start': 0.0, 'end': 0.0, 'force': 0},        # off-peak period 2 / pm charging period
    'peak': {'start': 16.0, 'end': 19.0 },                      # peak period 1
    'peak2': {'start': 0.0, 'end': 0.0 },                       # peak period 2
    'forecast_times': [22, 23],                                 # hours in a day to get a forecast
    'strategy': [
        {'start': 0.0, 'end': 2.0, 'mode': 'Feedin'},
        {'start': 5.0, 'end': 6.0, 'mode': 'SelfUse'},
        {'start': 16.0, 'end': 24.0, 'mode': 'Feedin'}]
    }

# time periods for Intelligent Octopus
intelligent_octopus = {
    'name': 'Intelligent Octopus',
    'off_peak1': {'start': 23.5, 'end': 5.5, 'force': 1},
    'off_peak2': {'start': 0.0, 'end': 0.0, 'force': 0},
    'peak': {'start': 0.0, 'end': 0.0 },
    'peak2': {'start': 0.0, 'end': 0.0 },
    'forecast_times': [22, 23]
    }

# time periods for Octopus Cosy
octopus_cosy = {
    'name': 'Octopus Cosy',
    'off_peak1': {'start': 4.0, 'end': 7.0, 'force': 1},
    'off_peak2': {'start': 13.0, 'end': 16.0, 'force': 0},
    'peak': {'start': 16.0, 'end': 19.0 },
    'peak2': {'start': 0.0, 'end': 0.0 },
    'forecast_times': [2, 3, 12]
    }

# time periods for Octopus Go
octopus_go = {
    'name': 'Octopus Go',
    'off_peak1': {'start': 0.5, 'end': 4.5, 'force': 1},
    'off_peak2': {'start': 0.0, 'end': 0.0, 'force': 0},
    'peak': {'start': 0.0, 'end': 0.0 },
    'peak2': {'start': 0.0, 'end': 0.0 },
    'forecast_times': [22, 23]
    }

# time periods for Agile Octopus
agile_octopus = {
    'name': 'Agile Octopus',
    'off_peak1': {'start': 2.5, 'end': 5.0, 'force': 1},
    'off_peak2': {'start': 0.0, 'end': 0.0, 'force': 0},
    'peak': {'start': 16.0, 'end': 19.0 },
    'peak2': {'start': 0.0, 'end': 0.0 },
    'forecast_times': [22, 23]
    }

# time periods for British Gas Electric Driver
bg_driver = {
    'name': 'British Gas Electric Driver',
    'off_peak1': {'start': 0.0, 'end': 5.0, 'force': 1},
    'off_peak2': {'start': 0.0, 'end': 0.0, 'force': 0},
    'peak': {'start': 0.0, 'end': 0.0 },
    'peak2': {'start': 0.0, 'end': 0.0 },
    'forecast_times': [22, 23]
    }

# time periods for Economy 7
economy_7 = {
    'name': 'Eco 7',
    'off_peak1': {'start': 0.5, 'end': 7.5, 'force': 1, 'gmt': 1},
    'off_peak2': {'start': 0.0, 'end': 0.0, 'force': 0},
    'peak': {'start': 0.0, 'end': 0.0 },
    'peak2': {'start': 0.0, 'end': 0.0 },
    'forecast_times': [22, 23]
    }

# custom time periods / template
custom_periods = {'name': 'Custom',
    'off_peak1': {'start': 2.0, 'end': 5.0, 'force': 1},
    'off_peak2': {'start': 15.0, 'end': 16.0, 'force': 0},
    'peak': {'start': 16.0, 'end': 19.0 },
    'peak2': {'start': 0.0, 'end': 0.0 },
    'forecast_times': [22, 23]
    }

tariff_list = [octopus_flux, intelligent_octopus, octopus_cosy, octopus_go, agile_octopus, bg_driver, economy_7, custom_periods]
tariff = octopus_flux

##################################################################################################
# Strategy - schedule templates
##################################################################################################

test_strategy = [
        {'start': 0, 'end': 2, 'mode': 'Feedin'},
        {'start': 5, 'end': 11, 'mode': 'SelfUse', 'min_soc': 80},
        {'start': 11, 'end': 14, 'mode': 'SelfUse'},
        {'start': 16, 'end': 20, 'mode': 'Feedin'},
        {'start': 21, 'end': 22, 'mode': 'ForceCharge'}]

# return a strategy that has been filtered for charge times:
def get_strategy(use=None, strategy=None, min_soc=10, quiet=1):
    global tariff
    if use is None:
        use = tariff
    if strategy is None and tariff is not None:
        strategy = tariff.get('strategy')
    if strategy is None:
        return []
    if type(strategy) is not list:
        strategy = [strategy]
    updated = []
    for s in strategy: #orted(strategy, key=lambda s: s['start']):
        # skip segments that overlap any charge periods
        start = s['start']
        end = s['end']
        if hour_overlap(s, use['off_peak1'] ) or hour_overlap(s, use['off_peak2']):
            output(f"   {hours_time(start)} to {hours_time(end)} ** dropped ** (overlaps charge period)", 2)
            continue
        # add segment
        min_soc_now = s['min_soc'] if s.get('min_soc') is not None and s['min_soc'] > min_soc else min_soc
        mode = s['mode']
        max_soc = s['max_soc'] if s.get('max_soc') is not None else 100
        fdsoc = s.get('fdsoc')
        fdpwr = s.get('fdpwr')
        segment = {'start': start, 'end': end, 'mode': mode, 'min_soc': min_soc_now, 'max_soc': max_soc, 'fdsoc': fdsoc, 'fdpwr': fdpwr}
        if quiet == 0:
            output(f"   {hours_time(start)} to {hours_time(end)} {mode} with min_soc = {min_soc_now}% and max_soc = {max_soc}%" + (f", fdPwr = {fdpwr}W and fdSoC = {fdsoc}%" if mode == 'ForceDischarge' else ""), 1)
        updated.append(segment)
    return updated

# build strategy using current schedule
def build_strategy_from_schedule():
    schedule = get_schedule()
    if schedule.get('pollcy') is None:
        return None
    strategy = []
    for p in schedule['pollcy']:
        period = {}
        period['start'] = round_time(p['startH'] + p['startM'] / 60)
        period['end'] = round_time(p['endH'] + p['endM'] / 60 + 1/60)
        period['mode'] = p.get('workMode')
        period['min_soc'] = p.get('minsocongrid')
        period['max_soc'] = p.get('maxSoc')
        period['fdsoc'] = p.get('fdsoc')
        period['fdpwr'] = p.get('fdpwr')
        strategy.append(period)
    return strategy


##################################################################################################
# Octopus Energy Agile Price
##################################################################################################

# base settings
octopus_api_url = "https://api.octopus.energy/v1/products/%PRODUCT%/electricity-tariffs/E-1R-%PRODUCT%-%REGION%/standard-unit-rates/"
regions = {'A':'Eastern England', 'B':'East Midlands', 'C':'London', 'D':'Merseyside and Northern Wales', 'E':'West Midlands', 'F':'North Eastern England', 'G':'North Western England', 'H':'Southern England',
    'J':'South Eastern England', 'K':'Southern Wales', 'L':'South Western England', 'M':'Yorkshire', 'N':'Southern Scotland', 'P':'Northern Scotland'}


# preset weightings for average pricing over charging duration:
front_loaded = [1.0, 0.9, 0.8, 0.7, 0.6, 0.5]           # 3 hour average, front loaded
first_hour =   [1.0, 1.0]                               # lowest average price for first hour


tariff_config = {
    'product': "AGILE-FLEX-22-11-25",     # product code to use for Octopus API
    'region': "H",                        # region code to use for Octopus API
    'update_time': 16.5,                  # time in hours when tomrow's data can be fetched
    'weighting': None,                    # weights for weighted average
    'pm_start': 11,                       # time when charge period is considered PM
    'am_start': 23                        # time when charge period is considered AM
}

# get prices and work out lowest weighted average price time period
def get_agile_period(start_at=None, end_by=None, duration=None, d=None):
    global debug_setting, octopus_api_url, time_shift
    # get time, dates and duration
    duration = 3 if duration is None else 6 if duration > 6 else 0.5 if duration < 0.5 else duration
    # round up to 30 minutes so charge periods covers complete end pricing period
    duration = round(duration * 2 + 0.49, 0) / 2
    # number of 30 minute pricing periods
    span = int(duration * 2)
    # work out dates for price forecast
    if d is not None and len(d) < 11:
        d += " 18:00"
    # get dates and times
    system_time = (datetime.now(tz=timezone.utc) + timedelta(hours=time_shift)) if d is None else datetime.strptime(d, '%Y-%m-%d %H:%M')
    time_offset = daylight_saving(system_time) if daylight_saving is not None else 0
    # adjust system to get local time now
    now = system_time + timedelta(hours=time_offset)
    hour_now = now.hour + now.minute / 60
    update_time = tariff_config['update_time']
    update_time = time_hours(update_time) if type(update_time) is str else 17 if update_time is None else update_time
    today = datetime.strftime(now + timedelta(days=0 if hour_now >= update_time else -1), '%Y-%m-%d')
    tomorrow = datetime.strftime(now + timedelta(days=1 if hour_now >= update_time else 0), '%Y-%m-%d')
    output(f"  datetime = {today} {hours_time(hour_now)}", 2)
    # get product and region
    product = tariff_config['product'].upper()
    region = tariff_config['region'].upper()
    if region not in regions:
        output(f"** region {region} not recognised, valid regions are {regions}")
        return None
    # get prices from 11pm today to 11pm tomorrow
    output(f"\nProduct: {product}")
    output(f"Region:  {regions[region]}")
    zulu_hour = "T" + hours_time(23 - time_offset - time_shift, ss=True) + "Z"
    url = octopus_api_url.replace("%PRODUCT%", product).replace("%REGION%", region)
    period_from = today + zulu_hour
    period_to = tomorrow + zulu_hour
    params = {'period_from': period_from, 'period_to': period_to }
    output(f"time_offset = {time_offset}, time_shift = {time_shift}", 2)
    output(f"period_from = {period_from}, period_to = {period_to}", 2)
    response = requests.get(url, params=params)
    if response.status_code != 200:
        output(f"** get_agile_period() response code from Octopus API {response.status_code}: {response.reason}")
        return None
    # results are in reverse chronological order...
    results = response.json().get('results')[::-1]
    # extract times and prices
    times = []          # ordered list of times
    prices = []         # ordered list of prices inc VAT
    for r in results:
        time_offset = daylight_saving(r['valid_from'][:16]) if daylight_saving is not None else 0
        times.append(hours_time(time_hours(r['valid_from'][11:16]) + time_offset + time_shift))
        prices.append(r['value_inc_vat'])
    # show the results
    s = f"\nPrices for {tomorrow} (p/kWh inc VAT):\n" + " " * 4 * 15
    for i in range(0, len(times)):
        s += "\n" if i % 6 == 2 else ""
        s += f"  {times[i]} = {prices[i]:5.2f}"
    output(s)
    # work out start and end times for charging
    start_at = time_hours(start_at) if type(start_at) is str else 23.0 if start_at is None else start_at
    end_by = time_hours(end_by) if type(end_by) is str else 8.0 if end_by is None else end_by
    start_i = int(round_time(start_at - 23) * 2)
    end_i = int(round_time(end_by - 23) * 2)
    end_i = 48 if end_i == 0 or end_i > 48 else end_i
    output(f"start_at = {start_at}, end_by = {end_by}, start_i = {start_i}, end_i = {end_i}, duration = {duration}, span = {span}", 2)
    if (start_i + span) > 48 or start_i > end_i:
        output(f"** get_agile_period(): invalid times {hours_time(start_at)} - {hours_time(end_by)}. Must start from 23:00 today and end by 23:00 tomorrow")
        return None
    if len(results) < (start_i + span):
        output(f"** get_agile_period(): prices not available for {tomorrow}")
        return None
    # work out weighted average for each period and track lowest price
    period = {}
    min_i = None
    min_v = None
    weighting = tariff_config['weighting']
    weights = [1.0] * span if weighting is None else (weighting + [0.0] * span)[:span]
    for i in range(start_i, end_i):
        start = times[i]
        p_span = prices[i: i + span]
        if (i + span) > 48:
            break
        wavg = round(sum(p * w for p,w in zip(p_span, weights)) / sum(weights), 2)
        if min_v is None or wavg < min_v:
            min_v = wavg
            min_i = i
    # save results
    start = times[min_i]
    end = times[min_i + span] if (min_i + span) < 48 else "23:00"
    price = min_v
    period['date'] = tomorrow
    period['times'] = times
    period['prices'] = prices
    period['span'] = span
    period['start'] = start
    period['end'] = end
    period['price'] = price
    return period

# pushover app key for set_tariff()
set_tariff_app_key = "apx24dswzinhrbeb62sdensvt42aqe"

# set AM/PM charge time period based on pricing for Agile Octopus
def set_agile_period(period=None, tariff=agile_octopus, d=None):
    global debug_setting, agile_octopus, set_tariff_app_key
    output_spool(set_tariff_app_key)
    start_at = 23 if period.get('start') is None else time_hours(period['start'])
    end_by = 8 if period.get('end') is None else time_hours(period['end'])
    duration = 3 if period.get('duration') is None else period['duration']
    if duration > 0:
        agile_period = get_agile_period(start_at=start_at, end_by=end_by, duration=duration, d=d)
        if agile_period is None:
            output_close()
            return None
        weighting = tariff_config['weighting']
        if weighting is not None:
            output(f"\nWeighting: {weighting}")
        start = time_hours(agile_period['start'])
        end = time_hours(agile_period['end'])
        price = agile_period['price']
        charge_pm = start >= tariff_config['pm_start'] and end < tariff_config['am_start']
        am_pm = 'PM' if charge_pm else 'AM'
        output(f"\nBest {duration} hour {am_pm} charging period for {tariff['name']} between {hours_time(start_at)} and {hours_time((end_by))}:")
        output(f"  Price: {price:.2f} p/kWh inc VAT")
    else:
        charge_pm = start_at >= tariff_config['pm_start'] and start_at < tariff_config['am_start']
        am_pm = 'PM' if charge_pm else 'AM'
        start = 0.0
        end = 0.0
        output(f"\nDisabled {am_pm} charging period")
    if charge_pm:
        tariff['off_peak2']['start'] = start
        tariff['off_peak2']['end'] = end
    else:
        tariff['off_peak1']['start'] = start
        tariff['off_peak1']['end'] = end
    output(f"  Charging period: {hours_time(start)} to {hours_time(end)}")
    output_close()
    return 1

# set agile strategy
def get_agile_strategy(max_price=None, duration=None, allow=None):
    period = get_agile_period()
    allow = {'start': 23, 'end': 8} if allow is None else allow
    max_price = 13 if max_price is None else max_price
    n = 6 if duration is None else int(duration * 2 + 0.99)
    # find periods that meet the criteria
    periods = []
    for i in range(0, len(period['times'])):
        h = time_hours(period['times'][i])
        if period['prices'][i] <= max_price and hour_in(h, allow):
            periods.append({'h': h, 'price': period['prices'][i]})
    # sort by price to get cheapest n periods, then sort back into time order
    periods = sorted(sorted(periods, key=lambda d: d['price'])[:n], key=lambda d: d['h'])
    # consolidate 30 minute periods into time segments
    segments = []
    segment = None
    h = -1
    for s in periods:
        if s['h'] != h:
            if segment is not None:
                segment['end'] = h
                segments.append(segment)
            h = s['h']
            segment = {'start': h, 'end': None, 'mode': 'ForceCharge'}
        h = round_time(h + 0.5)
    if segment is not None:
        segment['end'] = h
        segments.append(segment)
    return segments

# set AM/PM charge time for any tariff
def set_tariff_period(period=None, tariff=octopus_flux, d=None):
    global debug_setting
    start_at = time_hours(period.get('start'), tariff['off_peak1']['start'])
    end_by = time_hours(period.get('end'), tariff['off_peak1']['end'])
    duration = 3 if period.get('duration') is None else period['duration']
    charge_pm = start_at >= tariff_config['pm_start'] and end_by < tariff_config['am_start']
    am_pm = 'PM' if charge_pm else 'AM'
    start = start_at if duration > 0 else 0.0
    end = end_by if duration > 0 else 0.0
    gmt = ''
    if charge_pm:
        tariff['off_peak2']['start'] = start
        tariff['off_peak2']['end'] = end
    else:
        tariff['off_peak1']['start'] = start
        tariff['off_peak1']['end'] = end
        gmt = ' GMT' if tariff['off_peak1'].get('gmt') is not None else ''
    print(f"\n{tariff['name']} {am_pm} charging period: {hours_time(start)} to {hours_time(end)}{gmt}")
    return 1

# set tariff and AM/PM charge time period
def set_tariff(find, update=1, start_at=None, end_by=None, duration=None, times=None, forecast_times=None, strategy=None, d=None, **settings):
    global debug_setting, agile_octopus, tariff, tariff_list
    output(f"\n---------------- set_tariff -----------------", 1)
    # validate parameters
    args = locals()
    s = ""
    for k in [k for k in args.keys() if args[k] is not None and k != 'settings']:
        s += f"\n  {k} = {args[k]}"
    # store settings:
    for key, value in settings.items():
        if key not in tariff_config:
            output(f"** unknown configuration parameter: {key}")
        else:
            tariff_config[key] = value
            s += f"\n  {key} = {value}"
    if len(s) > 0:
        output(f"Parameters: {s}", 2)
    found = []
    if find in tariff_list:
        found = [find]
    elif type(find) is str:
        for dict in tariff_list:
            if find.lower() in dict['name'].lower():
                found.append(dict)
    if len(found) != 1:
        output(f"** set_tariff(): {find} must identify one of the available tariffs:")
        for x in tariff_list:
            print(f"  {x['name']}")
        return None
    use = found[0]
    if times is None:
        times = [(start_at, end_by, duration)] if start_at is not None or end_by is not None or duration is not None else [(None, None, 3)]
    elif type(times) is not list:
        times = [times]
    if len(times) > 2:
        output(f"** set_tariff(): one AM (11pm - 11am) and one PM (11am - 11pm) charge time can be set. times = {times}")
        return None
    set_proc = set_agile_period if use == agile_octopus else set_tariff_period
    for t in times:
        result = set_proc(period={'start': t[0], 'end': t[1], 'duration': t[2]}, tariff=use, d=d)
        if result is None:
            return None
    if forecast_times is not None:
        if type(forecast_times) is not list:
            forecast_times = [forecast_times]
        forecast_hours = []
        for i, t in enumerate(forecast_times):
            forecast_times[i] = hours_time(t)
            forecast_hours.append(time_hours(t))
        use['forecast_times'] = forecast_hours
        output(f"Forecast times set to {forecast_times}")
    if strategy is not None:
        if strategy == 'load':
            strategy = build_strategy_from_schedule()
        elif type(strategy) is not list:
            strategy = [strategy]
        output(f"Strategy updated")
        use['strategy'] = get_strategy(use=use, strategy=strategy, quiet=0)
    if update == 1:
        tariff = use
        output(f"\nTariff set to {tariff['name']}")
    else:
        output(f"\nNo changes made to current tariff", 1)
    return None


##################################################################################################
# CHARGE_NEEDED - calculate charge from current battery charge, forecast yield and expected load
##################################################################################################

# how consumption varies by month across a year. 12 values.
# month                J   F   M   A   M   J   J   A   S   O   N   D
high_seasonality =   [13, 12, 11, 10,  9,  8,  9,  9, 10, 11, 12, 13]
medium_seasonality = [11, 11, 10, 10,  9,  9,  9,  9, 10, 10, 11, 12]
no_seasonality =     [10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10]
seasonality_list = [high_seasonality, medium_seasonality, no_seasonality]
seasonality = medium_seasonality

# how consumption varies by hour across a day. 24 values.
# from hour       00  01  02  03  04  05  06  07  08  09  10  11  12  13  14  15  16  17  18  19  20  21  22  23
high_profile =   [20, 20, 20, 20, 20, 20, 40, 50, 70, 70, 70, 50, 50, 50, 50, 70, 99, 99, 99, 70, 40, 35, 30, 30]
medium_profile = [28, 28, 28, 28, 28, 28, 36, 49, 65, 70, 65, 49, 44, 44, 49, 63, 92, 99, 92, 63, 47, 39, 33, 31]
no_profile =     [50, 50, 50, 50, 50, 50, 50, 50, 50, 50, 50, 50, 50, 50, 50, 50, 50, 50, 50, 50, 50, 50, 50, 50]
daily_consumption = medium_profile

# how generation varies by hour across a day and by season. 24 values
winter_sun =     [ 0,  0,  0,  0,  0,  0,  0,  0,  5, 20, 55, 85, 99, 85, 55, 20,  5,  0,  0,  0,  0,  0,  0,  0]
spring_sun =     [ 0,  0,  0,  0,  0,  0,  0,  5, 19, 40, 70, 90, 99, 90, 70, 40, 19,  5,  0,  0,  0,  0,  0,  0]
summer_sun =     [ 0,  0,  0,  0,  0,  0,  5, 15, 30, 50, 80, 95, 99, 95, 80, 50, 30, 15,  5,  0,  0,  0,  0,  0]
autumn_sun =     [ 0,  0,  0,  0,  0,  0,  0,  5, 19, 40, 70, 90, 99, 90, 70, 40, 19,  5,  0,  0,  0,  0,  0,  0]

# map month via quarters to seasons
seasonal_sun =   [
    {'name': 'Winter', 'sun': winter_sun},
    {'name': 'Spring', 'sun': spring_sun},
    {'name': 'Summer', 'sun': summer_sun},
    {'name': 'Autumn', 'sun': autumn_sun},
]
# --------- helper functions for charge_needed() ---------

# rotate 24 hour list so it aligns with hour_now and cover run_time:
def timed_list(data, hour_now, run_time=None):
    h = int(hour_now)
    data1 = data[h:] + data[:h]
    if run_time is not None:
        data1 = (data1 + data1)[:run_time]
    return data1

# take a report and return (average value and 24 hour profile)
def report_value_profile(result):
    if type(result) is not list or result[0]['type'] != 'day':
        return (None, None)
    data = []
    for h in range(0,24):
        data.append((0.0, 0)) # value sum, count of values
    totals = 0
    n = 0
    for day in result:
        hours = 0
        value = 0.0
        # sum and count available values by hour
        for i in range(0, len(day['data'])):
            value = day['data'][i]['value'] if day['data'][i]['value'] is not None else value
            data[i] = (data[i][0] + value, data[i][1]+1)
            hours += 1
        totals += day['total'] * (24 / hours if hours >= 1 else 1)
        n += 1
    daily_average = totals / n if n !=0 else None
    # average for each hour
    by_hour = []
    for h in data:
        by_hour.append(h[0] / h[1] if h[1] != 0 else 0.0)   # sum / count
    if daily_average is None or daily_average == 0.0:
        return (None, None)
    # rescale to match daily_average
    current_total = sum(by_hour)
    return (daily_average, [h * daily_average / current_total for h in by_hour])

def forecast_value_timed(forecast, today, tomorrow, hour_now, run_time, time_offset=0):
    profile = []
    h = int(hour_now - time_offset)
    while h < 0:
        profile.append(0.0)
        h += 1
    while h < 24:
        profile.append(c_float(forecast.daily[today]['hourly'].get(h)))
        h += 1
    while h < 48:
        profile.append(c_float(forecast.daily[tomorrow]['hourly'].get(h-24)))
        h += 1
    while len(profile) < run_time:
        profile.append(0.0)
    return profile[:run_time]

# build the timed work mode profile from the tariff strategy:
def strategy_timed(timed_mode, hour_now, run_time, min_soc=10, max_soc=100):
    global tariff
    profile = []
    min_soc_now = min_soc
    max_soc_now = max_soc
    for h in range(0, 24):
        period = {'mode': 'SelfUse', 'min_soc': min_soc_now, 'max_soc': max_soc_now, 'fdpwr': 0, 'fdsoc': min_soc_now, 'duration': 1.0, 'charge': 0.0}
        if timed_mode > 0 and tariff is not None and tariff.get('strategy') is not None:
            for d in tariff['strategy']:
                if hour_in(h, d):
                    mode = d['mode']
                    period['mode'] = mode
                    min_soc_now = d['min_soc'] if d.get('min_soc') is not None and d['min_soc'] > min_soc else min_soc
                    period['min_soc'] = min_soc_now
                    max_soc_now = d['max_soc'] if d.get('max_soc') is not None and d['max_soc'] < max_soc else max_soc
                    period['max_soc'] = max_soc_now
                    if mode == 'ForceDischarge':
                        if d.get('fdsoc') is not None:
                            period['fdsoc'] = d['fdsoc'] if d['fdsoc'] > min_soc_now else min_soc_now
                        if d.get('fdpwr') is not None:
                            period['fdpwr'] = d['fdpwr']
                    period['duration'] = duration_in(h, d)
        profile.append(period)
    output(f"work mode profile = {profile}", 2)
    return (profile[int(hour_now):] + profile + profile)[:run_time]

# build the timed battery residual from the charge / discharge, work mode and min_soc
def battery_timed(kwh_timed, work_mode_timed, kwh_current, capacity, time_to_next, float_charge, kwh_min=None, reserve_drain=None):
    global charge_config
    bat_timed = []
    allowed_drain = charge_config['allowed_drain'] if charge_config.get('allowed_drain') is not None else 4
    bms_loss = charge_config['bms_power'] / 1000 if charge_config.get('bms_power') is not None else 0.05
    for i in range(0, len(kwh_timed)):
        bat_timed.append(kwh_current)
        max_now = work_mode_timed[i]['max_soc'] * capacity / 100
        if kwh_current < max_now and work_mode_timed[i]['charge'] > 0.0:
            kwh_current += work_mode_timed[i]['charge']
            kwh_current = max_now if kwh_current > max_now else kwh_current
        kwh_current += kwh_timed[i]
        if kwh_current > capacity:
            # battery is full
            kwh_current = capacity
        min_soc_now = work_mode_timed[i]['fdsoc'] if work_mode_timed[i]['mode'] =='ForceDischarge' else work_mode_timed[i]['min_soc']
        reserve_now = capacity * min_soc_now / 100
        if kwh_current < reserve_now and (i <= time_to_next or kwh_min is None):
            # battery is empty, check if charge is needed
            reserve_limit = capacity * (min_soc_now - allowed_drain) / 100
            reserve_drain = kwh_current if reserve_drain is None or kwh_current > reserve_drain else reserve_drain
            kwh_current = reserve_drain
            if reserve_drain <= reserve_limit:
                reserve_drain = min([reserve_now, reserve_drain + float_charge])
            else:
                # BMS power drain
                reserve_drain -= bms_loss
        else:
            # reset drain level
            reserve_drain = reserve_now
        if kwh_min is not None and kwh_current < kwh_min and i >= time_to_next:       # track minimum without charge
            kwh_min = kwh_current
    return (bat_timed, kwh_min)

# Battery open circuit voltage (OCV) from 0% to 100% SoC
#                 0%     10%    20%    30%    40%    50%    60%    70%    80%    90%   100%
lifepo4_curve = [51.00, 51.50, 52.00, 52.30, 52.60, 52.80, 52.90, 53.00, 53.10, 53.30, 54.00]

# charge_needed settings
charge_config = {
    'contingency': [20,10,5,15],      # % of consumption. Single value or [winter, spring, summer, autumn]
    'capacity': None,                 # Battery capacity (over-ride)
    'min_soc': None,                  # Minimum Soc (over-ride)
    'charge_current': None,           # max battery charge current setting in A
    'discharge_current': None,        # max battery discharge current setting in A
    'export_limit': None,             # maximum export power in kW
    'discharge_loss': 0.98,           # loss converting battery discharge power to grid power
    'pv_loss': 0.95,                  # loss converting PV power to battery charge power
    'grid_loss': 0.95,                # loss converting grid power to battery charge power
    'charge_loss': None,              # loss converting charge power to residual
    'inverter_power': None,           # Inverter power consumption in W
    'bms_power': 50,                  # BMS power consumption in W
    'allowed_drain': 4,               # % tolerance below min_soc before float charge starts
    'float_current': 4,               # BMS float charge in A
    'bat_resistance': 0.072,          # internal resistance of a battery
    'volt_curve': lifepo4_curve,      # battery OCV range from 0% to 100% SoC
    'nominal_soc': 60,                # SoC for nominal open circuit battery voltage
    'generation_days': 3,             # number of days to use for average generation (1-7)
    'consumption_days': 3,            # number of days to use for average consumption (1-7)
    'consumption_span': 'week',       # 'week' = last n days or 'weekday' = last n weekdays
    'use_today': 21.0,                # hour when todays consumption and generation can be used
    'min_hours': 0.25,                # minimum charge time in decimal hours
    'min_kwh': 0.5,                   # minimum to add in kwh
    'solcast_adjust': 100,            # % adjustment to make to Solcast forecast
    'solar_adjust':  100,             # % adjustment to make to Solar forecast
    'forecast_selection': 1,          # 0 = use available forecast / generation, 1 only update settings with forecast
    'annual_consumption': None,       # optional annual consumption in kWh
    'timed_mode': 0,                  # = = None, 1 = timed mode, 2 = strategy mode
    'special_contingency': 33,        # contingency for special days when consumption might be higher
    'special_days': ['12-25', '12-26', '01-01'],
    'full_charge': None,              # day of month (1-28) to do full charge, or 'daily' or 'Mon', 'Tue' etc
    'derate_temp': 22,                # battery temperature where cold derating starts to be applied
    'derate_step': 5,                 # scale for derating factors in C
    'derating': [24, 15, 10, 2],      # max charge current e.g. 5C step = 22C, 17C, 12C, 7C
    'force': 1,                       # 0 = don't over-ride schedule, 1 = disable schedule
    'data_wrap': 6,                   # data items to show per line
    'target_soc': None                # set the target SoC for charging
}

# app key for charge_needed (used to send output via pushover)
charge_needed_app_key = "awcr5gro2v13oher3v1qu6hwnovp28"

# work out the charge times to set using the parameters:
#  forecast: the kWh expected tomorrow. If none, forecast data is loaded from solcast etc
#  update_settings: 0 no updates, 1 update charge settings. The default is 0
#  show_data: 1 shows battery SoC, 2 shows battery residual. Default = 0
#  show_plot: 1 plots battery SoC, 2 plots battery residual. Default = 1
#  run_after: 0 over-rides 'forecast_times'. The default is 1.
#  forecast_times: list of hours when forecast can be fetched
#  force_charge: 1 = set force charge, 2 = charge for whole period

def charge_needed(forecast=None, update_settings=0, timed_mode=None, show_data=None, show_plot=None, run_after=None,
        forecast_times=None, force_charge=None, test_time=None, test_soc=None, test_charge=None, **settings):
    global device, seasonality, solcast_api_key, debug_setting, tariff, solar_arrays, legend_location, time_shift, timed_strategy
    print(f"\n---------------- charge_needed ----------------")
    # validate parameters
    args = locals()
    s = ""
    for k in [k for k in args.keys() if args[k] is not None and k != 'settings']:
        s += f"\n  {k} = {args[k]}"
    # store settings:
    for key, value in settings.items():
        if key not in charge_config:
            print(f"** unknown configuration parameter: {key}")
        else:
            charge_config[key] = value
            s += f"\n  {key} = {value}"
    if len(s) > 0:
        output(f"Parameters: {s}", 2)
    if tariff is not None:
        output(f"  tariff = {tariff['name']}", 2)
    # set default parameters
    show_data = 1 if show_data is None or show_data == True else 0 if show_data == False else show_data
    show_plot = 3 if show_plot is None or show_plot == True else 0 if show_plot == False else show_plot
    run_after = 1 if run_after is None else run_after 
    timed_mode = 1 if timed_mode is None and tariff is not None and tariff.get('strategy') is not None else 0 if timed_mode is None else timed_mode
    if forecast_times is None:
        forecast_times = tariff['forecast_times'] if tariff is not None and tariff.get('forecast_times') is not None else [22,23]
    if type(forecast_times) is not list:
        forecast_times = [forecast_times]
    # get dates and times
    system_time = (datetime.now(tz=timezone.utc) + timedelta(hours=time_shift)) if test_time is None else datetime.strptime(test_time, '%Y-%m-%d %H:%M')
    time_offset = daylight_saving(system_time) if daylight_saving is not None else 0
    now = system_time + timedelta(hours=time_offset)
    today = datetime.strftime(now, '%Y-%m-%d')
    base_hour = now.hour
    hour_now = now.hour + now.minute / 60
    output(f"  datetime = {today} {hours_time(hour_now)}", 2)
    yesterday = datetime.strftime(now - timedelta(days=1), '%Y-%m-%d')
    tomorrow = datetime.strftime(now + timedelta(days=1), '%Y-%m-%d')
    day_tomorrow = day_names[(now.weekday() + 1) % 7]
    day_after_tomorrow = datetime.strftime(now + timedelta(days=2), '%Y-%m-%d')
    # work out if we lose 1 hour if clocks go forward or gain 1 hour if clocks go back
    change_hour = 0
    hour_adjustment = 0 if daylight_saving is None else daylight_changes(system_time, system_time + timedelta(days=2))
    if hour_adjustment != 0:    # change happens in the next 2 days - work out if today, tomorrow or day after tomorrow
        change_hour = 1 if daylight_changes(system_time, f"{tomorrow} 00:00") != 0 else 25 if daylight_changes(f"{tomorrow} 00:00", f"{day_after_tomorrow} 00:00") != 0 else 49
        change_hour += 1 if hour_adjustment > 0 else 0
    # get next charge times from am/pm charge times
    force_charge = 0 if force_charge is None else force_charge
    start_am = time_hours(tariff['off_peak1']['start'] if tariff is not None else 2.0)
    end_am = time_hours(tariff['off_peak1']['end'] if tariff is not None else 5.0)
    # adjust charge times for Economy 7 in BST
    if time_offset > 0 and tariff is not None and tariff['off_peak1'].get('gmt') is not None:
        start_am += 1
        end_am += 1
    force_charge_am = 0 if (tariff is not None and tariff['off_peak1']['force'] == 0) or force_charge == 0 else 1
    time_to_am = round_time(start_am - base_hour)
    start_pm = time_hours(tariff['off_peak2']['start'] if tariff is not None else 0.0)
    end_pm = time_hours(tariff['off_peak2']['end'] if tariff is not None else 0.0)
    force_charge_pm = 0 if (tariff is not None and tariff['off_peak2']['force'] == 0) or force_charge == 0 else 1
    time_to_pm = round_time(start_pm - base_hour) if start_pm > 0 else None
    no_go1 = time_to_am is not None and hour_in(hour_now, {'start': round_time(start_am - 0.25), 'end': round_time(end_am + 0.25)})
    no_go2 = time_to_pm is not None and hour_in(hour_now, {'start': round_time(start_pm - 0.25), 'end': round_time(end_pm + 0.25)})
    if (no_go1 or no_go2) and update_settings > 0:
        output(f"\nInverter settings will not be changed less than 15 minutes before or after a charging period")
        update_settings = 0
    # choose and configure parameters for next charge time period
    charge_pm = time_to_pm is not None and time_to_pm < time_to_am
    force_charge = force_charge_pm if charge_pm else force_charge if force_charge_am == 1 else 0
    start_at = start_pm if charge_pm else start_am
    end_by = end_pm if charge_pm else end_am
    charge_time = round_time(end_by - start_at)
    time_to_start = time_to_pm if charge_pm else time_to_am
    start_hour = base_hour + time_to_start
    time_to_next = int(time_to_start)
    start_part_hour = time_to_start % 1
    forecast_day = today if charge_pm else tomorrow
    if hour_adjustment < 0 and start_hour > change_hour:
        time_to_next -= 1       # 1 hour less if charging after clocks go forward
    run_time = int((time_to_am if charge_pm else time_to_am + 24 if time_to_pm is None else time_to_pm) + 0.99) + 1 + hour_adjustment
    # if we need to do a full charge, full_charge is the date, otherwise None
    full_charge = charge_config['full_charge'] if not charge_pm else None
    if type(full_charge) is int:            # value = day of month
        full_charge = tomorrow if full_charge is not None and int(tomorrow[-2:]) == full_charge else None
    elif type(full_charge) is str:          # value = daily or day of week
        full_charge = tomorrow if full_charge.lower() == 'daily' or full_charge.title() == day_tomorrow[:3] else None
    output(f"\ntoday = {today}, tomorrow = {tomorrow}, time_shift = {time_shift}", 3)
    output(f"start_am = {start_am}, end_am = {end_am}, force_am = {force_charge_am}, time_to_am = {time_to_am}", 3)
    output(f"start_pm = {start_pm}, end_pm = {end_pm}, force_pm = {force_charge_pm}, time_to_pm = {time_to_pm}", 3)
    output(f"start_at = {start_at}, end_by = {end_by}, force_charge = {force_charge}", 3)
    output(f"base_hour = {base_hour}, hour_adjustment = {hour_adjustment}, change_hour = {change_hour}", 3)
    output(f"time_to_start = {time_to_start}, run_time = {run_time}, charge_pm = {charge_pm}", 3)
    output(f"start_hour = {start_hour}, time_to_next = {time_to_next}, full_charge = {full_charge}", 3)
    # get device and battery info from inverter
    if test_soc is None:
        min_soc = charge_config['min_soc'] if charge_config['min_soc'] is not None else 10
        get_battery()
        if battery is None or battery['status'] != 1:
            output(f"\nBattery status is not available")
            return None
        current_soc = battery['soc']
        bat_volt = battery['volt']
        bat_power = battery['power']
        bat_current = battery['current']
        temperature = battery['temperature']
        residual = battery['residual']
        if charge_config.get('capacity') is not None:
            capacity = charge_config['capacity']
        elif residual is not None and residual > 0.2 and current_soc is not None and current_soc > 1:
            capacity = residual * 100 / current_soc
        else:
            output(f"Battery capacity could not be estimated. Please add the parameter 'capacity=xx' in kWh")
            return None
    else:
        current_soc = test_soc
        capacity = 8.2
        residual = test_soc * capacity / 100
        min_soc = 10
        bat_volt = 122 / (1 + 0.03 * (100 - test_soc) / 90)
        bat_power = 0.0
        temperature = 19.5
        bat_current = 0.0
    volt_curve = charge_config['volt_curve']
    nominal_soc = charge_config['nominal_soc']
    volt_nominal = interpolate(nominal_soc / 10, volt_curve)
    bat_resistance = charge_config['bat_resistance'] * bat_volt / volt_nominal
    bat_ocv = (bat_volt + bat_current * bat_resistance) * volt_nominal / interpolate(current_soc / 10, volt_curve)
    reserve = capacity * min_soc / 100
    output(f"\nBattery Info:")
    output(f"  Capacity:    {capacity:.2f}kWh")
    output(f"  Residual:    {residual:.2f}kWh")
    output(f"  Voltage:     {bat_volt:.1f}V")
    output(f"  Current:     {bat_current:.1f}A")
    output(f"  State:       {'Charging' if bat_power < 0 else 'Discharging'} ({abs(bat_power):.3f}kW)")
    output(f"  Current SoC: {current_soc}%")
    output(f"  Min SoC:     {min_soc}% ({reserve:.2f}kWh)")
    output(f"  Temperature: {temperature:.1f}°C")
    output(f"  Resistance:  {bat_resistance:.2f} ohms")
    output(f"  Nominal OCV: {bat_ocv:.1f}V at {nominal_soc}% SoC")
    # get power and charge current for device
    device_power = device.get('power')
    device_current = device.get('max_charge_current')
    model = device.get('deviceType') if device.get('deviceType') is not None else 'unknown'
    if device_power is None or device_current is None:
        output(f"** could not get parameters for {model} inverter, using default rating of 3.68kW")
        device_power = 3.68
        device_current = 26
    # charge times are derated based on temperature
    charge_current = device_current if charge_config['charge_current'] is None else charge_config['charge_current']
    derate_temp = charge_config['derate_temp']
    if temperature > 36:
        output(f"\nHigh battery temperature may affect the charge rate")
    elif round(temperature, 0) <= derate_temp:
        output(f"\nLow battery temperature may affect the charge rate")
        derating = charge_config['derating']
        derate_step = charge_config['derate_step']
        i = int((derate_temp - temperature) / (derate_step if derate_step is not None and derate_step > 0 else 1))
        if derating is not None and type(derating) is list and i < len(derating):
            derated_current = derating[i]
            if derated_current < charge_current:
                output(f"  Charge current reduced from {charge_current:.0f}A to {derated_current:.0f}A" )
                charge_current = derated_current
        else:
            force_charge = 2
            output(f"  Full charge set")
    # work out charge limit = max power going into the battery after ac conversion losses
    charge_limit = device_power * charge_config['grid_loss']
    charge_power = charge_current * (bat_ocv + charge_current * bat_resistance) / 1000
    if charge_power < 0.1:
        output(f"** charge_current is too low ({charge_current:.1f}A)")
    elif charge_power < charge_limit:
        charge_limit = charge_power
    # work out losses when charging / force discharging
    inverter_power = charge_config['inverter_power'] if charge_config['inverter_power'] is not None else round(device_power, 0) * 12
    operating_loss = inverter_power / 1000
    bms_power = charge_config['bms_power']
    bms_loss = bms_power / 1000
    charge_loss = charge_config.get('charge_loss')
    if charge_loss is None:
        charge_loss = 1.0 - charge_limit * 1000 * bat_resistance / bat_ocv ** 2 - bms_loss / charge_limit
    float_charge = (charge_config['float_current'] if charge_config.get('float_current') is not None else 4) * bat_ocv / 1000 * charge_loss
    # work out discharge limit = max power coming from the battery before ac conversion losses
    discharge_loss = charge_config['discharge_loss']
    discharge_limit = device_power
    discharge_current = device_current if charge_config['discharge_current'] is None else charge_config['discharge_current']
    discharge_power = discharge_current * bat_ocv / 1000
    discharge_limit = discharge_power if discharge_power < discharge_limit else discharge_limit
    # charging happens if generation exceeds export limit in feedin work mode
    export_power = device_power if charge_config['export_limit'] is None else charge_config['export_limit']
    export_limit = export_power / discharge_loss
    current_mode = get_work_mode()
    output(f"\ncharge_config = {json.dumps(charge_config, indent=2)}", 3)
    output(f"\nDevice Info:")
    output(f"  Model:     {model}")
    output(f"  Rating:    {device_power:.2f}kW")
    output(f"  Export:    {export_power:.2f}kW")
    output(f"  Charge:    {charge_current:.1f}A, {charge_limit:.2f}kW, {charge_loss * 100:.1f}% efficient")
    output(f"  Discharge: {discharge_current:.1f}A, {discharge_limit:.2f}kW, {discharge_loss * 100:.1f}% efficient")
    output(f"  Inverter:  {inverter_power:.0f}W power consumption")
    output(f"  BMS:       {bms_power:.0f}W power consumption")
    if current_mode is not None:
        output(f"  Work Mode: {current_mode}")
    # get consumption data
    annual_consumption = charge_config['annual_consumption']
    if annual_consumption is not None:
        consumption = annual_consumption / 365 * seasonality[now.month - 1] / sum(seasonality) * 12
        consumption_by_hour = daily_consumption
        output(f"\nEstimated consumption: {consumption:.1f}kWh")
    else:
        consumption_days = charge_config['consumption_days']
        consumption_days = 3 if consumption_days > 7 or consumption_days < 1 else consumption_days
        consumption_span = charge_config['consumption_span']
        if consumption_span == 'weekday':
            history = get_report('day', d=date_list(span='weekday', e=tomorrow, today=2)[-consumption_days-1:-1], v='loads')
        else:
            last_date = today if hour_now >= charge_config['use_today'] else yesterday
            history = get_report('day', d=date_list(span='week', e=last_date, today=1)[-consumption_days:], v='loads')
        (consumption, consumption_by_hour) = report_value_profile(history)
        if consumption is None:
            print(f"No consumption data available")
            return None
        output(f"\nConsumption (kWh):")
        s = ""
        for h in history:
            s += f"  {h['date']}: {h['total']:4.1f},"
        output(s[:-1])
        output(f"  Average of last {consumption_days} {day_tomorrow if consumption_span=='weekday' else 'day'}s: {consumption:.1f}kWh")
    # time line has 1 hour buckets of consumption
    daily_sum = sum(consumption_by_hour)
    consumption_timed = timed_list([consumption * x / daily_sum for x in consumption_by_hour], hour_now, run_time)
    # get Solcast data and produce time line
    solcast_value = None
    solcast_profile = None
    if forecast is None and solcast_api_key is not None and solcast_api_key != 'my.solcast_api_key' and (base_hour in forecast_times or run_after == 0):
        fsolcast = Solcast(quiet=True, estimated=1 if charge_pm else 0)
        if fsolcast is not None and hasattr(fsolcast, 'daily') and fsolcast.daily.get(forecast_day) is not None:
            solcast_value = fsolcast.daily[forecast_day]['kwh']
            solcast_timed = forecast_value_timed(fsolcast, today, tomorrow, hour_now, run_time, time_offset)
            if charge_pm:
                output(f"\nSolcast forecast for {today} = {fsolcast.daily[today]['kwh']:.1f}, {tomorrow} = {fsolcast.daily[tomorrow]['kwh']:.1f}")
            else:
                output(f"\nSolcast forecast for {forecast_day} = {solcast_value:.1f}kWh")
            adjust = charge_config['solcast_adjust']
            if adjust != 100:
                solcast_value = solcast_value * adjust / 100
                solcast_timed = [v * adjust / 100 for v in solcast_timed]
                output(f"  Adjusted forecast: {solcast_value:.1f}kWh ({adjust}%)")
    # get forecast.solar data and produce time line
    solar_value = None
    solar_profile = None
    if forecast is None and solar_arrays is not None and (base_hour in forecast_times or run_after == 0):
        fsolar = Solar(quiet=True)
        if fsolar is not None and hasattr(fsolar, 'daily') and fsolar.daily.get(forecast_day) is not None:
            solar_value = fsolar.daily[forecast_day]['kwh']
            solar_timed = forecast_value_timed(fsolar, today, tomorrow, hour_now, run_time, 0)
            if charge_pm:
                output(f"\nSolar forecast for {today} = {fsolar.daily[today]['kwh']:.1f}, {tomorrow} = {fsolar.daily[tomorrow]['kwh']:.1f}")
            else:
                output(f"\nSolar forecast for {forecast_day} = {solar_value:.1f}kWh")
            adjust = charge_config['solar_adjust']
            if adjust != 100:
                solar_value = solar_value * adjust / 100
                solar_timed = [v * adjust / 100 for v in solar_timed]
                output(f"  Adjusted forecast: {solar_value:.1f}kWh ({adjust}%)")
    if solcast_value is None and solar_value is None and debug_setting > 1:
        output(f"\nNo forecasts available at this time")
    # get generation data
    generation = None
    last_date = today if hour_now >= charge_config['use_today'] else yesterday
    gen_days = charge_config['generation_days']
    history = get_raw('week', d=last_date, v=['pvPower','meterPower2'], summary=2)
    pv_history = {}
    if history is not None and len(history) > 0:
        for day in history:
            date = day['date']
            if pv_history.get(date) is None:
                pv_history[date] = 0.0
            if day.get('kwh') is not None and day.get('kwh_neg') is not None:
                pv_history[date] += day['kwh_neg'] / 0.92 if day['variable'] == 'meterPower2' else day['kwh']
        pv_sum = sum([pv_history[d] for d in sorted(pv_history.keys())[-gen_days:]])
        output(f"\nGeneration (kWh):")
        s = ""
        for d in sorted(pv_history.keys())[-gen_days:]:
            s += f"  {d}: {pv_history[d]:4.1f},"
        output(s[:-1])
        generation = pv_sum / gen_days
        output(f"  Average of last {gen_days} days: {generation:.1f}kWh")
    # choose expected value and produce generation time line
    output_spool(charge_needed_app_key)
    quarter = now.month // 3 % 4
    sun_name = seasonal_sun[quarter]['name']
    sun_profile = seasonal_sun[quarter]['sun']
    sun_sum = sum(sun_profile)
    sun_timed = timed_list(sun_profile, hour_now, run_time)
    if forecast is not None:
        expected = forecast
        generation_timed = [expected * x / sun_sum for x in sun_timed]
    elif solcast_value is not None:
        expected = solcast_value
        generation_timed = solcast_timed
    elif solar_value is not None:
        expected = solar_value
        generation_timed = solar_timed
    elif generation is None or generation == 0.0:
        output(f"\nNo generation data available")
        output_close()
        return None
    else:
        expected = generation
        generation_timed = [expected * x / sun_sum for x in sun_timed]
        if charge_config['forecast_selection'] == 1 and update_settings > 0:
            output(f"\nSettings will not be updated when forecast is not available")
            update_settings = 0
    # produce time lines for main charge and discharge (after losses)
    charge_timed = [x * charge_config['pv_loss'] * charge_loss for x in generation_timed]
    discharge_timed = [(x / discharge_loss + operating_loss) / charge_loss for x in consumption_timed]
    # adjust charge and discharge time lines for work mode, force charge and power limits
    work_mode_timed = strategy_timed(timed_mode, hour_now, run_time, min_soc)
    work_mode = work_mode_timed[0]['mode'] if current_mode is None else current_mode
    for i in range(0, run_time):
        h = base_hour + i
        # get work mode and check for changes
        new_work_mode = work_mode_timed[i]['mode']
        if new_work_mode != work_mode:
            output(f"  {hours_time(h)}: {new_work_mode} work mode", 2)
            work_mode = new_work_mode
        # cap charge / discharge power
        charge_timed[i] = charge_limit if charge_timed[i] > charge_limit else charge_timed[i]
        discharge_timed[i] = discharge_limit if discharge_timed[i] > discharge_limit else discharge_timed[i]
        # apply changes due to work mode
        duration = work_mode_timed[i]['duration']
        if timed_mode > 0 and work_mode == 'ForceCharge':
            discharge_timed[i] = discharge_timed[i] * (1.0 - duration)
            work_mode_timed[i]['charge'] = charge_limit * duration * charge_loss
        elif timed_mode > 0 and work_mode == 'ForceDischarge':
            fdpwr = work_mode_timed[i]['fdpwr'] / charge_config['discharge_loss']
            fdpwr = min([discharge_limit, export_limit * 1000 + discharge_timed[i], fdpwr])
            discharge_timed[i] = fdpwr * duration + discharge_timed[i] * (1.0 - duration) - charge_timed[i] * duration
        elif force_charge_am > 0 and hour_in(h, {'start': start_am, 'end': end_am}):
            discharge_timed[i] = bms_loss
        elif force_charge_pm > 0 and hour_in(h, {'start': start_pm, 'end': end_pm}):
            discharge_timed[i] = bms_loss
        elif timed_mode > 0 and work_mode == 'Backup':
            discharge_timed[i] = bms_loss if charge_timed[i] == 0.0 else 0.0
        elif timed_mode > 0 and work_mode == 'Feedin':
            (discharge_timed[i], charge_timed[i]) = (bms_loss if (charge_timed[i] >= discharge_timed[i]) else (discharge_timed[i] - charge_timed[i]),
                0.0 if (charge_timed[i] <= export_limit * 1000 + discharge_timed[i]) else (charge_timed[i] - export_limit * 1000 - discharge_timed[i]))
        else: # work_mode == 'SelfUse'
            (discharge_timed[i], charge_timed[i]) = (bms_loss if (charge_timed[i] >= discharge_timed[i]) else (discharge_timed[i] - charge_timed[i]),
                0.0 if (charge_timed[i] <= discharge_timed[i]) else (charge_timed[i] - discharge_timed[i]))
    # build the battery residual if we don't add any charge and don't limit discharge at min_soc
    kwh_timed = [charge - discharge for charge, discharge in zip(charge_timed, discharge_timed)]
    kwh_current = residual - kwh_timed[0] * (hour_now % 1)
    (bat_timed, kwh_min) = battery_timed(kwh_timed, work_mode_timed, kwh_current, capacity, time_to_next, float_charge, kwh_min=capacity)
    # work out what we need to add to stay above reserve and provide contingency or to hit target_soc
    contingency = charge_config['special_contingency'] if tomorrow[-5:] in charge_config['special_days'] else charge_config['contingency']
    contingency = contingency[quarter] if type(contingency) is list else contingency
    kwh_contingency = consumption * contingency / 100
    kwh_needed = reserve + kwh_contingency - kwh_min
    start_residual = interpolate(time_to_start, bat_timed)      # residual when charging starts
    target_soc = charge_config['target_soc'] if charge_config.get('target_soc') is not None else 10
    target_soc = 100 if target_soc > 100 else 10 if target_soc < 10 else target_soc
    target_kwh = target_soc / 100 * capacity
    if target_kwh > (start_residual + kwh_needed):
        kwh_needed = target_kwh - start_residual
    if kwh_min > reserve and kwh_needed < charge_config['min_kwh'] and full_charge is None and test_charge is None:
        output(f"\nNo charging is needed (forecast = {expected:.1f}kWh, consumption = {consumption:.1f}kWh, contingency = {kwh_contingency:.1f}kWh)")
        charge_message = "no charge needed"
        kwh_needed = 0.0
        hours = 0.0
        end1 = start_at
        end_soc = int(start_residual / capacity * 100 + 0.5)
        output(f"   Expected SoC at {hours_time(start_at)} is {end_soc}%")
        # rebuild the battery residual with min_soc
        if force_charge > 0 and timed_mode > 1:
            for i in range(0, int(charge_time + 0.5)):
                work_mode_timed[time_to_next + i]['min_soc'] = end_soc
        kwh_current = residual - kwh_timed[0] * (hour_now % 1)
        (bat_timed, x) = battery_timed(kwh_timed, work_mode_timed, kwh_current, capacity, time_to_next, float_charge)
    else:
        charge_message = "with charge added"
        if test_charge is None:
            output(f"\nCharge of {kwh_needed:.2f}kWh is needed (forecast = {expected:.1f}kWh, consumption = {consumption:.1f}kWh, contingency = {kwh_contingency:.1f}kWh)")
        else:
            output(f"\nTest charge of {test_charge}kWh")
            charge_message = "** test charge **"
            kwh_needed = test_charge
        # work out time to add kwh_needed to battery
        taper_time = 10/60 if (start_residual + kwh_needed) >= (capacity * 0.95) else 0
        hours = round_time(kwh_needed / (charge_limit * charge_loss + discharge_timed[time_to_next]) + taper_time)
        # full charge if requested or charge time exceeded or charge needed exceeds capacity
        if full_charge is not None or force_charge == 2 or hours > charge_time or (start_residual + kwh_needed) > (capacity * 1.01):
            kwh_needed = capacity - start_residual
            hours = charge_time
            output(f"  Full charge time used")
        elif hours < charge_config['min_hours']:
            hours = charge_config['min_hours']
        end1 = round_time(start_at + hours)
        end_soc = (start_residual + kwh_needed) / capacity * 100
        if force_charge > 0 and timed_mode > 1:
            for i in range(0, int(charge_time + 0.5)):
                work_mode_timed[time_to_next + i]['min_soc'] = end_soc
        # rework charge and discharge
        start_timed = time_to_start      # relative start and end time 
        end_timed = start_timed + hours
        discharge_timed_old = [x for x in discharge_timed]
        for i in range(time_to_next, int(time_to_next + hours + 2)):
            j = i + 1
            # work out time (fraction of hour) when charging in hour from i to j
            if start_timed >= i and end_timed < j:
                t = end_timed - start_timed         # start and end in same hour
            elif start_timed >= i and start_timed < j and end_timed >= j:
                t = j - start_timed                 # start this hour but not end
            elif end_timed > i and end_timed <= j and start_timed <= i:
                t = end_timed - i                   # end this hour but not start
            elif start_timed <= i and end_timed > j:
                t = 1.0                             # complete hour inside start and end
            else:
                t = 0.0                             # complete hour before start or after end
            if debug_setting > 2:
                print(f"i = {i}, j = {j}, t = {t}")
            charge_added = charge_limit * t
            work_mode_timed[i]['charge'] = (charge_added if charge_timed[i] + charge_added < charge_limit else charge_limit - charge_timed[i]) * charge_loss
            discharge_timed[i] *= (1-t)
        # rebuild the battery residual with the charge added and min_soc
        kwh_timed = [charge * charge_loss - discharge for charge, discharge in zip(charge_timed, discharge_timed)]
        kwh_current = residual - kwh_timed[0] * (hour_now % 1)
        bat_timed_old = [x for x in bat_timed]     # save for before / after comparison
        bat_timed = []
        (bat_timed, x) = battery_timed(kwh_timed, work_mode_timed, kwh_current, capacity, time_to_next, float_charge)
        # work out the new state
        time_to_end = int(start_timed + hours) + 1
        kwh_added = bat_timed[time_to_end] - bat_timed_old[time_to_end]
        end_part_hour = end_timed - int(end_timed)
        old_residual = interpolate(end_timed, bat_timed_old)
        new_residual = capacity if old_residual + kwh_added > capacity else old_residual + kwh_added
        net_added = new_residual - start_residual
        end_soc = int(new_residual / capacity * 100 + 0.5)
        output(f"  Start SoC: {start_residual / capacity * 100:3.0f}% at {hours_time(start_at)} ({start_residual:.2f}kWh)")
        output(f"  End SoC:   {end_soc:3.0f}% at {hours_time(end1)} ({new_residual:.2f}kWh)")
    # work out charge periods settings
    start2 = round_time(start_at if hours == 0 else end1)
    if force_charge > 0 and hour_in(start2, {'start':start_at, 'end': end_by}):
        end2 = end_by
    else:
        end2 = start2
    if show_data > 2:
        output(f"\nTime, Generation, Charge, Consumption, Discharge, Residual, kWh")
        for i in range(0, run_time):
            h = base_hour + i
            output(f"  {hours_time(h)}, {generation_timed[i]:6.3f}, {charge_timed[i]:6.3f}, {consumption_timed[i]:6.3f}, {discharge_timed[i]:6.3f}, {bat_timed[i]:6.3f}")
        if kwh_needed > 0 and show_data > 3:
            output(f"\nTime, Generation, Charge, Consumption, Discharge, Residual, kWh (before charging)")
            for i in range(0, run_time):
                h = base_hour + i
                output(f"  {hours_time(h)}, {generation_timed[i]:6.3f}, {charge_timed[i]:6.3f}, {consumption_timed[i]:6.3f}, {discharge_timed_old[i]:6.3f}, {bat_timed_old[i]:6.3f}")
    if show_data > 0:
        data_wrap = charge_config['data_wrap'] if charge_config.get('data_wrap') is not None else 6
        s = f"\nBattery Energy kWh:\n" if show_data == 2 else f"\nBattery SoC %:\n"
        h = base_hour + 1
        s += " " * (18 if show_data == 2 else 17) * (h % data_wrap)
        for i in range(1, run_time):
            s += "\n" if h > hour_now and h % data_wrap == 0 else ""
            s += f"  {hours_time(h - (hour_adjustment if h >= change_hour else 0), day=True)}"
            s += f" = {bat_timed[i]:5.2f}," if show_data == 2 else f" = {bat_timed[i] / capacity * 100:3.0f}%,"
            h += 1
        output(s[:-1])
    if show_plot > 0:
        print()
        plt.figure(figsize=(figure_width, figure_width/2))
        x_timed = [i for i in range(1, run_time)]
        plt.xticks(ticks=x_timed, labels=[hours_time(base_hour + x - (hour_adjustment if (base_hour + x) >= change_hour else 0), day=False) for x in x_timed], rotation=90, fontsize=8, ha='center')
        if show_plot == 1:
            title = f"Battery SoC % ({charge_message})"
            plt.plot(x_timed, [round(bat_timed[x] * 100 / capacity, 1) for x in x_timed], label='Battery', color='blue')
            plt.plot(x_timed, [work_mode_timed[x]['min_soc'] for x in x_timed], label='Min SoC', color='grey', linestyle='dotted')
            plt.plot(x_timed, [work_mode_timed[x]['max_soc'] for x in x_timed], label='Max SoC', color='coral', linestyle='dotted')
        else:
            title = f"Energy Flow kWh ({charge_message})"
            plt.plot(x_timed, bat_timed[1:], label='Battery', color='blue')
            plt.plot(x_timed, generation_timed[1:], label='Generation', color='green')
            plt.plot(x_timed, consumption_timed[1:], label='Consumption', color='red')
            plt.plot(x_timed, [round(capacity * work_mode_timed[x]['min_soc'] / 100, 1) for x in x_timed], label='Min SoC', color='grey', linestyle='dotted')
            plt.plot(x_timed, [round(capacity * work_mode_timed[x]['max_soc'] / 100, 1) for x in x_timed], label='Max SoC', color='coral', linestyle='dotted')
            if show_plot == 3:
                plt.plot(x_timed, charge_timed[1:], label='PV Charge', color='orange', linestyle='dotted')
                plt.plot(x_timed, discharge_timed[1:], label='Discharge', color='brown', linestyle='dotted')
                plt.plot(x_timed, [work_mode_timed[x]['charge'] for x in x_timed], label='Grid Charge', color='pink', linestyle='dotted')
        plt.title(title, fontsize=10)
        plt.grid()
        if show_plot > 1:
            plt.legend(fontsize=8, loc="upper right")
        plot_show()
    if test_charge is not None:
        return None
    # setup charging
    if update_settings == 1:
        # adjust times for clock changes
        adjust = hour_adjustment if hour_adjustment != 0 and start_hour > change_hour else 0
        if timed_mode > 1:
            periods = charge_periods(st1 = start_at, en1 = end1, st2 = start2, en2 = end2, adjust = adjust, min_soc = min_soc, target_soc = end_soc if target_soc < end_soc else target_soc)
            set_schedule(periods = periods)
        else:
            set_charge(ch1 = True, st1 = start_at, en1 = end1, ch2 = False, st2 = start2, en2 = end2, adjust = adjust, force = charge_config['force'])
    else:
        print(f"\nNo changes made to charge settings")
    output_close(plot=show_plot)
    return None


##################################################################################################
# Battery Info / Battery Monitor
##################################################################################################

# calculate the average of a list of values
def avg(x):
    if len(x) == 0:
        return None
    count = 0
    total = 0.0
    for y in x:
        if y is not None:
            total += y
            count += 1
    return total / count if count > 0 else None

# calculate the % imbalance in a list of values
def imbalance(v):
    if len(v) == 0:
        return None
    max_v = max(v)
    min_v = min(v)
    return (max_v - min_v) / (max_v + min_v) * 200

cells_per_battery = [16,18,15]      # allowed number of cells per battery

# deduce the number of batteries from the number of cells
def bat_count(cell_count):
    global cells_per_battery
    n = None
    for i in cells_per_battery:
        if cell_count % i == 0:
            n = i
            break
    if n is None:
        return None
    return int(cell_count / n + 0.5)

# battery monitor app key
battery_info_app_key = "aug938dqt5cbqhvq69ixc4v39q6wtw"

# show information about the current state of the batteries
def battery_info(log=0, plot=1, count=None, info=1):
    global debug_setting, battery_info_app_key
    output_spool(battery_info_app_key)
    bat = get_battery(info=info)
    if bat is None:
        output_close()
        return None
    nbat = None
    if bat.get('info') is not None:
        for b in bat['info']:
            output(f"\nSN {b['masterSN']}, {b['masterBatType']}, Version {b['masterVersion']} (BMS)")
            nbat = 0
            for s in b['slaveBatteries']:
                nbat += 1
                output(f"SN {s['sn']}, {s['batType']}, Version {s['version']} (Battery {nbat})")
    bat_volt = bat['volt']
    current_soc = bat['soc']
    residual = bat['residual']
    bat_current = bat['current']
    bat_power = bat['power']
    bms_temperature = bat['temperature']
    capacity = residual / current_soc * 100
    cell_volts = get_cell_volts()
    if cell_volts is None:
        output_close()
        return None
    nv = len(cell_volts)
    if nbat is None:
        nbat = bat_count(nv) if count is None else count
    if nbat is None:
        output(f"** battery_info(): unable to match cells_per_battery for {nv}")
        output_close()
        return None
    nv_cell = int(nv / nbat + 0.5)
    bat_cell_temps = get_cell_temps(nbat)
    if bat_cell_temps is None:
        output_close()
        return None
    bat_cell_volts = []
    bat_volts = []
    bat_temps = []
    cell_temps = []
    for i in range(0, nbat):
        bat_cell_volts.append(cell_volts[i * nv_cell : (i + 1) * nv_cell])
        bat_volts.append(sum(bat_cell_volts[i]))
        bat_temps.append(avg(bat_cell_temps[i]))
        for t in bat_cell_temps[i]:
            cell_temps.append(t)
    if log > 0:
        now = datetime.now()
        s = datetime.strftime(datetime.now(), '%Y-%m-%d %H:%M:%S')
        s += f",{current_soc},{residual},{bat_volt},{bat_current},{bms_temperature},{nbat},{nv_cell}"
        for i in range(0, nbat):
            s +=f",{bat_volts[i]:.2f}"
        for i in range(0, nbat):
            s +=f",{imbalance(bat_cell_volts[i]):.2f}"
        for i in range(0, nbat):
            s +=f",{bat_temps[i]:.1f}"
        if log >= 2:
            for v in cell_volts:
                s +=f",{v:.3f}"
            if log >= 3:
                for v in cell_temps:
                    s +=f",{v:.0f}"
        return s
    output(f"\nCurrent SoC:         {current_soc}%")
    output(f"Capacity:            {capacity:.2f}kWh")
    output(f"Residual:            {residual:.2f}kWh")
    output(f"InvBatVolt:          {bat_volt:.1f}V")
    output(f"InvBatCurrent:       {bat_current:.1f}A")
    output(f"State:               {'Charging' if bat_power < 0 else 'Discharging'} ({abs(bat_power):.3f}kW)")
    output(f"Battery Count:       {nbat} batteries with {nv_cell} cells each")
    output(f"Battery Volts:       {sum(bat_volts):.1f}V total, {avg(bat_volts):.2f}V average, {max(bat_volts):.2f}V maximum, {min(bat_volts):.2f}V minimum")
    output(f"Cell Volts:          {avg(cell_volts):.3f}V average, {max(cell_volts):.3f}V maximum, {min(cell_volts):.3f}V minimum")
    output(f"Cell Imbalance:      {imbalance(cell_volts):.2f}%:")
    output(f"BMS Temperature:     {bms_temperature:.1f}°C")
    output(f"Battery Temperature: {avg(cell_temps):.1f}°C average, {max(cell_temps):.1f}°C maximum, {min(cell_temps):.1f}°C minimum")
    output(f"\nInfo by battery:")
    for i in range(0, nbat):
        output(f"  Battery {i+1}: {bat_volts[i]:.2f}V, Cell Imbalance = {imbalance(bat_cell_volts[i]):.2f}%, Average Cell Temperature = {bat_temps[i]:.1f}°C")
    if plot >= 1:
        print()
        plt.figure(figsize=(figure_width, figure_width/3))
        x_scale = 0
        for i in range(0, len(bat_cell_volts)):
            n = len(bat_cell_volts[i])
            x_scale = max([x_scale, n])
            plt.plot(range(1, n + 1), bat_cell_volts[i], label = f"Battery {i+1}")
        x = range(1, x_scale + 1)
        plt.xticks(ticks=x, labels=x, fontsize=8)
        plt.title(f"Cell Volts by battery", fontsize=12)
        plt.legend(fontsize=8, loc='lower right')
        plt.grid()
        plot_show()
    output_close(plot=plot)
    if plot >= 2:
        print()
        plt.figure(figsize=(figure_width, figure_width/3))
        x_scale = 0
        for i in range(0, len(bat_cell_temps)):
            n = len(bat_cell_temps[i])
            x_scale = max([x_scale, n])
            plt.plot(range(1, n + 1), bat_cell_temps[i], label = f"Battery {i+1}")
        x = range(1, x_scale + 1)
        plt.xticks(ticks=x, labels=x, fontsize=8)
        plt.title(f"Cell Temperatures in °C by battery", fontsize=12)
        plt.legend(fontsize=8, loc='lower right')
        plt.grid()
        plot_show()
    return None

# helper to write file / echo to screen
def write(f, s, m='a'):
    print(s)
    if f is None or s is None:
        return
    file = open(f, m)
    print(s, file=file)
    file.close()
    return

# log battery information in CSV format at 'interval' minutes apart for 'run' times
# log 1: battery info, 2: add cell volts, 3: add cell temps
def battery_monitor(interval=30, run=48, log=1, count=None, save=None, overwrite=0):
    run_time = interval * run / 60
    print(f"\n---------------- battery_monitor ------------------")
    print(f"Expected runtime = {hours_time(run_time, day=True)} (hh:mm/days)")
    if save is not None:
        print(f"Saving data to {save} ")
    print()
    s = f"time,soc,residual,bat_volt,bat_current,bat_temp,nbat,ncell,ntemp,volts*,imbalance*,temps*"
    s += ",cell_volts*" if log == 2 else ",cell_volts*,cell_temps*" if log ==3 else ""
    write(save, s, 'w' if overwrite == 1 else 'a')
    i = run
    while i > 0:
        t1 = time.time()
        write(save, battery_info(log=log, count=count), 'a')
        if i == 1:
            break
        i -= 1
        t2 = time.time()
        time.sleep(interval * 60 - t2 + t1)
    return


##################################################################################################
# Date Ranges
##################################################################################################

# generate a list of dates, where the last date is not later than yesterday or today
# s and e: start and end dates using the format 'YYYY-MM-DD'
# limit: limits the total number of days (default is 200)
# today: 1 defaults the date to today as the last date, otherwise, yesterday
# span: 'week', 'month' or 'year' generated dates that span a week, month or year
# quiet: do not print results if True

def date_list(s = None, e = None, limit = None, span = None, today = 0, quiet = True):
    global debug_setting
    latest_date = datetime.date(datetime.now())
    today = 0 if today == False else 1 if today == True else today
    if today == 0:
        latest_date -= timedelta(days=1)
    first = datetime.date(datetime.strptime(s, '%Y-%m-%d')) if type(s) is str else s.date() if s is not None else None
    last = datetime.date(datetime.strptime(e, '%Y-%m-%d')) if type(e) is str else e.date() if e is not None else None
    last = latest_date if last is not None and last > latest_date and today != 2 else last
    step = 1
    if first is None and last is None:
        last = latest_date
    if span is not None:
        span = span.lower()
        limit = 366 if limit is None else limit
        if span == 'day':
            limit = 1
        elif span == '2days':
            # e.g. yesterday and today
            last = first + timedelta(days=1) if first is not None else last
            first = last - timedelta(days=1) if first is None else first
        elif span == 'weekday':
            # e.g. last 8 days with same day of the week
            last = first + timedelta(days=49) if first is not None else last
            first = last - timedelta(days=49) if first is None else first
            step = 7
        elif span == 'week':
            # number of days in a week less 1 day
            last = first + timedelta(days=6) if first is not None else last
            first = last - timedelta(days=6) if first is None else first
        elif span == 'month':
            if first is not None:
                # number of days in this month less 1 day
                days = ((first.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)).day - 1
            else:
                # number of days in previous month less 1 day
                days = (last.replace(day=1) - timedelta(days=1)).day - 1
            last = first + timedelta(days=days) if first is not None else last
            first = last - timedelta(days=days) if first is None else first
        elif span == 'year':
            if first is not None:
                # number of days in coming year
                days = (first.replace(year=first.year+1,day=28 if first.month==2 and first.day==29 else first.day) - first).days - 1
            else:
                # number of days in previous year
                days = (last - last.replace(year=last.year-1,day=28 if last.month==2 and last.day==29 else last.day)).days - 1
            last = first + timedelta(days=days) if first is not None else last
            first = last - timedelta(days=days) if first is None else first
        else:
            print(f"** span '{span}' was not recognised")
            return None
    else:
        limit = 200 if limit is None or limit < 1 else limit
    last = latest_date if last is None or (last > latest_date and today != 2) else last
    d = latest_date if first is None or (first > latest_date and today != 2) else first
    if d > last:
        d, last = last, d
    l = [datetime.strftime(d, '%Y-%m-%d')]
    while d < last  and len(l) < limit:
        d += timedelta(days=step)
        l.append(datetime.strftime(d, '%Y-%m-%d'))
    return l


##################################################################################################
##################################################################################################
# PV Output Section
##################################################################################################
##################################################################################################

# validate pv power data by checking it does not exceed a limit. Used to cover the situation where
# Fox returns PV Voltage instead of PV Power. For example, over 100v instead of under 100kW.
max_pv_power = 100
# data calibration settings compared with HA inverter data 
pv_calibration = 0.98
ct2_calibration = 0.92
invert_ct2 = 1
integrate_load_power = 0

##################################################################################################
# get PV Output upload data from the Fox Cloud as energy values for a list of dates
##################################################################################################

# get pvoutput data for upload to pvoutput api or via Bulk Loader
# tou: 0 = no time of use, 1 = use time of use periods if available

def get_pvoutput(d = None, tou = 0):
    global tariff, pv_calibration, ct2_calibration, integrate_load_power
    if d is None:
        d = date_list()[0]
    tou = 0 if tariff is None else 1 if tou == 1 or tou == True else 0
    if type(d) is list:
        print(f"---------------- get_pvoutput ------------------")
        print(f"Date range {d[0]} to {d[-1]} has {len(d)} days")
        if tou == 1:
            print(f"Time of use: {tariff['name']}")
        if integrate_load_power == 1:
            print(f"Consumption integrated from Load Power")
        print(f"------------------------------------------------")
        for x in d:
            csv = get_pvoutput(x, tou)
            if csv is None:
                return None
            print(csv)
        return
    # get quick report of totals for the day
    v = ['feedin', 'gridConsumption']
    if integrate_load_power == 0:
        v.append('loads')
    report_data = get_report('day', d=d, v=v, summary=2)
    if report_data is None:
        return None
    # get raw power data for the day
    v = ['pvPower', 'meterPower2', 'feedinPower', 'gridConsumptionPower'] if tou == 1 else ['pvPower', 'meterPower2']
    if integrate_load_power == 1:
        v.append('loadsPower')
    raw_data = get_raw('day', d=d + ' 00:00:00', v=v , summary=1)
    if raw_data is None or len(raw_data) == 0 or raw_data[0].get('kwh') is None or raw_data[0].get('max') is None:
        return(f"# error: {d.replace('-','')} No generation data available")
    # apply calibration and merge raw_data for meterPower2 into pvPower:
    pv_index = v.index('pvPower')
    ct2_index = v.index('meterPower2')
    for i, data in enumerate(raw_data[ct2_index]['data']):
        raw_data[pv_index]['data'][i]['value'] += data['value'] / ct2_calibration if data['value'] > 0.0 else 0
    # kwh is positive for generation
    raw_data[pv_index]['kwh'] = raw_data[pv_index]['kwh'] / pv_calibration + raw_data[ct2_index]['kwh'] / ct2_calibration
    pv_max = max(data['value'] for data in raw_data[pv_index]['data'])
    max_index = [data['value'] for data in raw_data[pv_index]['data']].index(pv_max)
    raw_data[pv_index]['max'] = pv_max
    raw_data[pv_index]['max_time'] = raw_data[pv_index]['data'][max_index]['time'][11:16]
    # validation check: max_pv_power against max pvPower (including meterPower2)
    if pv_max > max_pv_power:
        return(f"# error: {d.replace('-','')} PV power ({pv_max}kWh) exceeds max_pv_power ({max_pv_power}kWh)")
    # generate output
    date = None
    generate = None
    export = None
    power = None
    comment = ','
    grid = None
    consume = None
    export_tou = ',,,'
    # process list of report_data values (no TOU)
    for var in report_data:
        wh = int(var['total'] * 1000)
        if var['variable'] == 'feedin':
            export_wh = wh 
            export = f"{wh},"
        elif var['variable'] == 'gridConsumption':
            grid_wh = wh
            grid = f"0,0,{wh},0,"
        elif var['variable'] == 'loads':
            consume = f"{wh},"
    # process list of raw_data values (with TOU)
    for var in raw_data:
        wh = int(var['kwh'] * 1000)
        peak = int(var['kwh_peak'] * 1000)
        off_peak = int(var['kwh_off'] * 1000)
        if var['variable'] == 'pvPower':
            generate_wh = wh
            date = var['date'].replace('-','') + ','
            generate = f"{wh},"
            power = f"{int(var['max'] * 1000)},{var['max_time']},"
        elif var['variable'] == 'feedinPower':
            calibrate = export_wh / wh if wh > 0.0 else 1.0
            export = f","
            export_tou = f"{int(peak * calibrate)},{int(off_peak * calibrate)},{int((wh - peak - off_peak) * calibrate)},0"
        elif var['variable'] == 'gridConsumptionPower':
            calibrate = grid_wh / wh if wh > 0.0 else 1.0
            grid = f"{int(peak * calibrate)},{int(off_peak * calibrate)},{int((wh - peak - off_peak) * calibrate)},0,"
        elif var['variable'] == 'loadsPower':
            consume = f"{wh},"
    if date is None or generate is None or export is None or power is None or grid is None or consume is None:
        return None
    # check exported is less than generated
    if export_wh > generate_wh:
        comment = f"Export {export_wh/1000:.1f}kWh was more than Generated,"
        if tou == 0:
            export = f"{generate_wh},"
    csv = date + generate + export + power + ',,,' + comment + grid + consume + export_tou
    return csv

# helper to format CSV output data for display
def pvoutput_str(system_id, csv, tou=0):
    field = csv.split(',')
    s =  f"Upload data for {system_id} on {field[0][0:4]}-{field[0][4:6]}-{field[0][6:8]}:\n"
    imported = int(field[9]) + int(field[10]) + int(field[11]) + int(field[12])
    s += f"  Peak Solar: {int(field[3])/1000:.1f}kW at {field[4]}\n"
    s += f"  From Solar: {int(field[1])/1000:.1f}kWh\n"
    exported = int(field[2]) if tou == 0 else sum(int(x) for x in field[14:18])
    s += f"  From Grid: {imported/1000:.1f}kWh\n"
    s += f"  To Export: {exported/1000:.1f}kWh\n"
    s += f"  To House: {int(field[13])/1000:.1f}kWh"
    if len(field[8]) > 0:
        s += f"\n  ** {field[8]}" 
    return s

pv_url = "https://pvoutput.org/service/r2/addoutput.jsp"
pv_api_key = None
pv_system_id = None

# set_pvoutput app key for pushover (not currently used)
pvoutput_app_key = "a32i66pnyp9d8awshj5a4exypndzan"

# upload data for a day using pvoutput api
def set_pvoutput(d = None, system_id=None, tou = 0, push=2):
    global pv_url, pv_api_key, pv_system_id, tariff, pvoutput_app_key, pushover_user_key
    system_id = pv_system_id if system_id is None else system_id
    if pv_api_key is None or system_id is None or pv_api_key == 'my.pv_api_key' or system_id == 'my.pv_system_id':
        print(f"** set_pvoutput: 'pv_api_key' / 'pv_system_id' not configured")
        return None
    if d is None:
        d = date_list(span='2days', today = 1)
    tou = 0 if tariff is None else 1 if tou == 1 or tou == True else 0
    if type(d) is list:
        print(f"\n------------ set_pvoutput ({system_id}) -------------")
        print(f"Date range {d[0]} to {d[-1]} has {len(d)} days")
        if tou == 1 :
            print(f"Time of use: {tariff['name']}")
        print(f"------------------------------------------------")
        for x in d[:10]:
            csv = set_pvoutput(x, system_id, tou, push)
            push = 0 if push == 2 else push
            if csv is None:
                return None
            print(f"{csv}  # uploaded OK")
        return
    headers = {'X-Pvoutput-Apikey': pv_api_key, 'X-Pvoutput-SystemId': system_id, 'Content-Type': 'application/x-www-form-urlencoded'}
    csv = get_pvoutput(d, tou)
    if csv is None:
        return None
    if csv[0] == '#':
        return csv
    if pushover_user_key is not None and push > 0:
        output_message(pvoutput_app_key, pvoutput_str(system_id, csv, tou))
    try:
        response = requests.post(url=pv_url, headers=headers, data='data=' + csv)
    except Exception as e:
        print(f"** unable to upload data to pvoutput.org, {e}. Please try again later")
        return None
    result = response.status_code
    if result != 200:
        if result == 401:
            print(f"** access denied for pvoutput.org. Check 'pv_api_key' and 'pv_system_id' are correct")
            return None
        print(f"** set_pvoutput got response code {result}: {response.reason}")
        return None
    return csv


##################################################################################################
##################################################################################################
# Solcast Section
##################################################################################################
##################################################################################################

def c_int(i):
    # handle None in integer conversion
    if i is None :
        return None
    try:
        result = int(i)
    except:
        return 0
    return result

def c_float(n):
    # handle None in float conversion
    if n is None :
        return float(0)
    try:
        result = float(n)
    except:
        return 0
    return result

##################################################################################################
# Code for loading and displaying yield forecasts from Solcast.com.au.
##################################################################################################

# solcast settings
solcast_url = 'https://api.solcast.com.au/'
solcast_api_key = None
solcast_rids = []       # no longer used, rids loaded from solcast.com
solcast_save = 'solcast.txt'
page_width = 100        # maximum text string for display

class Solcast :
    """
    Load Solcast Estimate / Actuals / Forecast daily yield
    """ 

    def __init__(self, days = 7, reload = 2, quiet = False, estimated=0) :
        # days sets the number of days to get for forecasts (and estimated if enabled)
        # reload: 0 = use solcast.json, 1 = load new forecast, 2 = use solcast.json if date matches
        # The forecasts and estimated both include the current date, so the total number of days covered is 2 * days - 1.
        # The forecasts and estimated also both include the current time, so the data has to be de-duplicated to get an accurate total for a day
        global debug_setting, solcast_url, solcast_api_key, solcast_save
        data_sets = ['forecasts']
        if estimated == 1:
            data_sets += ['estimated_actuals']
        self.data = {}
        self.today = datetime.strftime(datetime.date(datetime.now()), '%Y-%m-%d')
        self.tomorrow = datetime.strftime(datetime.date(datetime.now() + timedelta(days=1)), '%Y-%m-%d')
        self.save = solcast_save #.replace('.', '_%.'.replace('%', self.today.replace('-','')))
        if reload == 1 and os.path.exists(self.save):
            os.remove(self.save)
        if self.save is not None and os.path.exists(self.save):
            file = open(self.save)
            self.data = json.load(file)
            file.close()
            if len(self.data) == 0:
                print(f"No data in {self.save}")
            elif reload == 2 and 'date' in self.data and self.data['date'] != self.today:
                self.data = {}
            elif debug_setting > 0 and not quiet:
                print(f"Using data for {self.data['date']} from {self.save}")
                if self.data.get('estimated_actuals') is None:
                    data_sets = ['forecasts']
                    estimated = 0
        if len(self.data) == 0 :
            if solcast_api_key is None or solcast_api_key == 'my.solcast_api_key>':
                print(f"\nSolcast: solcast_api_key not set, exiting")
                return
            self.credentials = HTTPBasicAuth(solcast_api_key, '')
            if debug_setting > 1 and not quiet:
                print(f"Getting rids from solcast.com")
            params = {'format' : 'json'}
            response = requests.get(solcast_url + 'rooftop_sites', auth = self.credentials, params = params)
            if response.status_code != 200:
                if response.status_code == 429:
                    print(f"\nSolcast API call limit reached for today")
                else:
                    print(f"Solcast: response code getting rooftop_sites was {response.status_code}: {response.reason}")
                return
            sites = response.json().get('sites')
            if debug_setting > 0 and not quiet:
                print(f"Getting forecast for {self.today} from solcast.com")
            self.data['date'] = self.today
            params = {'format' : 'json', 'hours' : 168, 'period' : 'PT30M'}     # always get 168 x 30 min values
            for t in data_sets :
                self.data[t] = {}
                for rid in [s['resource_id'] for s in sites] :
                    response = requests.get(solcast_url + 'rooftop_sites/' + rid + '/' + t, auth = self.credentials, params = params)
                    if response.status_code != 200 :
                        if response.status_code == 429:
                            print(f"\nSolcast: API call limit reached for today")
                        else:
                            print(f"Solcast: response code getting {t} was {response.status_code}: {response.reason}")
                        return
                    self.data[t][rid] = response.json().get(t)
            if self.save is not None :
                file = open(self.save, 'w')
                json.dump(self.data, file, sort_keys = True, indent=4, ensure_ascii= False)
                file.close()
        self.daily = {}
        for t in data_sets :
            for rid in self.data[t].keys() :            # aggregate sites
                if self.data[t][rid] is not None :
                    for f in self.data[t][rid] :            # aggregate 30 minute slots for each day
                        period_end = f.get('period_end')
                        date = period_end[:10]
                        hour = int(round_time(time_hours(period_end[11:16])-0.5))
                        if date not in self.daily.keys() :
                            self.daily[date] = {'hourly': {}, 'kwh': 0.0}
                        if hour not in self.daily[date]['hourly'].keys():
                            self.daily[date]['hourly'][hour] = 0.0
                        value = c_float(f.get('pv_estimate')) / 2                   # 30 minute power kw, yield / 2 = kwh
                        self.daily[date]['kwh'] += value
                        self.daily[date]['hourly'][hour] += value
        # ignore first and last dates as these only cover part of the day, so are not accurate
        self.keys = sorted(self.daily.keys())[1:-1]
        self.days = len(self.keys)
        # trim the range if fewer days have been requested
        while self.days > 2 * days :
            self.keys = self.keys[1:-1]
            self.days = len(self.keys)
        self.values = [self.daily[d]['kwh'] for d in self.keys]
        self.total = sum(self.values)
        if self.days > 0 :
            self.avg = self.total / self.days
        return

    def __str__(self) :
        # return printable Solcast info
        global debug_setting
        if not hasattr(self, 'days'):
            return 'Solcast: no days in forecast'
        s = f'\nSolcast forecast for {self.days} days'
        for d in self.keys :
            y = self.daily[d]['kwh']
            day = datetime.strptime(d, '%Y-%m-%d').strftime('%A')[:3]
            s += f"\n   {d} {day}: {y:5.2f}kWh"
        return s

    def plot_daily(self) :
        global figure_width, legend_location
        if not hasattr(self, 'daily') :
            print(f"Solcast: no daily data to plot")
            return
        plt.figure(figsize=(figure_width, figure_width/3))
        print()
        # plot estimated
        x = [f"{d} {datetime.strptime(d, '%Y-%m-%d').strftime('%A')[:3]} " for d in self.keys if d <= self.today]
        y = [self.daily[d]['kwh'] for d in self.keys if d <= self.today]
        if x is not None and len(x) != 0 :
            plt.bar(x, y, color='green', linestyle='solid', label='estimated', linewidth=2)
        # plot forecasts
        x = [f"{d} {datetime.strptime(d, '%Y-%m-%d').strftime('%A')[:3]} " for d in self.keys if d > self.today]
        y = [self.daily[d]['kwh'] for d in self.keys if d > self.today]
        if x is not None and len(x) != 0 :
            plt.bar(x, y, color='orange', linestyle='solid', label='forecast', linewidth=2)
        # annotations
        if hasattr(self, 'avg'):
            plt.axhline(self.avg, color='blue', linestyle='solid', label=f'average {self.avg:.1f} kwh / day', linewidth=2)
        title = f"Solcast daily yield on {self.today} for {self.days} days"
        title += f". Total yield = {self.total:.0f} kwh, Average = {self.avg:.0f}"    
        plt.title(title, fontsize=12)
        plt.grid()
#        plt.legend(fontsize=14, loc=legend_location)
        plt.xticks(rotation=45, ha='right')
        plot_show()
        return

    def plot_hourly(self, day = None) :
        if not hasattr(self, 'daily') :
            print(f"Solcast: no daily data to plot")
            return
        if day == 'today':
            day = self.today
        elif day == 'tomorrow':
            day = self.tomorrow
        elif day == 'all':
            day = self.keys
        elif day is None:
            day = [self.today, self.tomorrow]
        if type(day) is list:
            for d in day:
                self.plot_hourly(d)
            return
        plt.figure(figsize=(figure_width, figure_width/3))
        print()
        if day is None:
            day = self.tomorrow
        # plot forecasts
        hours = sorted([h for h in self.daily[day]['hourly'].keys()])
        x = [hours_time(h) for h in hours]
        y = [self.daily[day]['hourly'][h] for h in hours]
        color = 'orange' if day > self.today else 'green'
        if x is not None and len(x) != 0 :
            plt.plot(x, y, color=color, linestyle='solid', linewidth=2)
        title = f"Solcast hourly yield on {day} (UTC)"
        title += f". Total yield = {self.daily[day]['kwh']:.1f}kwh"    
        plt.title(title, fontsize=12)
        plt.grid()
        plt.xticks(rotation=45, ha='right')
        plot_show()
        return



##################################################################################################
##################################################################################################
# Forecast.Solar Section
##################################################################################################
##################################################################################################


# forecast.solar global settings
solar_api_key = None
solar_url = "https://api.forecast.solar/"
solar_save = "solar.txt"
solar_arrays = None

# configure a solar_array
def solar_array(name = None, lat=51.1790, lon=-1.8262, dec = 30, az = 0, kwp = 5.0, dam = None, inv = None, hor = None):
    global solar_arrays
    if name is None:
        return
    if solar_arrays is None:
        solar_arrays = {}
    if name not in solar_arrays.keys():
        solar_arrays[name] = {}
    solar_arrays[name]['lat'] = round(lat,4)
    solar_arrays[name]['lon'] = round(lon,4)
    solar_arrays[name]['dec'] = 30 if dec < 0 or dec > 90 else dec
    solar_arrays[name]['az'] = az - 360 if az > 180 else az
    solar_arrays[name]['kwp'] = kwp
    solar_arrays[name]['dam'] = dam
    solar_arrays[name]['inv'] = inv
    solar_arrays[name]['hor'] = hor
    return


class Solar :
    """
    load forecast.solar info using solar_arrays
    """ 

    # get solar forecast and return total expected yield
    def __init__(self, reload=0, quiet=False):
        global solar_arrays, solar_save, solar_total, solar_url, solar_api_key
        self.today = datetime.strftime(datetime.date(datetime.now()), '%Y-%m-%d')
        self.tomorrow = datetime.strftime(datetime.date(datetime.now() + timedelta(days=1)), '%Y-%m-%d')
        self.arrays = None
        self.results = None
        self.save = solar_save #.replace('.', '_%.'.replace('%',self.today.replace('-','')))
        if reload == 1 and os.path.exists(self.save):
            os.remove(self.save)
        if self.save is not None and os.path.exists(self.save):
            file = open(self.save)
            data = json.load(file)
            file.close()
            if data.get('date') is not None and (data['date'] == self.today and reload != 1):
                if debug_setting > 0 and not quiet:
                    print(f"Using data for {data['date']} from {self.save}")
                self.results = data['results'] if data.get('results') is not None else None
                self.arrays = data['arrays'] if data.get('arrays') is not None else None
        if self.arrays is None or self.results is None:
            if solar_arrays is None or len(solar_arrays) < 1:
                print(f"** Solar: you need to add an array using solar_array()")
                return
            self.api_key = solar_api_key + '/' if solar_api_key is not None else ''
            self.arrays = deepcopy(solar_arrays)
            self.results = {}
            for name, a in self.arrays.items():
                if debug_setting > 0 and not quiet:
                    print(f"Getting data for {name} array")
                path = f"{a['lat']}/{a['lon']}/{a['dec']}/{a['az']}/{a['kwp']}"
                params = {'start': '00:00', 'no_sun': 1, 'damping': a['dam'], 'inverter': a['inv'], 'horizon': a['hor']}
                response = requests.get(solar_url + self.api_key + 'estimate/' + path, params = params)
                if response.status_code != 200:
                    if response.status_code == 429:
                        print(f"\nSolar: forecast.solar API call limit reached for today")
                    else:
                        print(f"** Solar() got response code {response.status_code}: {response.reason}")
                    return
                self.results[name] = response.json().get('result')
            if self.save is not None :
                if debug_setting > 0 and not quiet:
                    print(f"Saving data to {self.save}")
                file = open(self.save, 'w')
                json.dump({'date': self.today, 'arrays': self.arrays, 'results': self.results}, file, indent=4, ensure_ascii= False)
                file.close()
        self.daily = {}
        for k in self.results.keys():
            if self.results[k].get('watt_hours_day') is not None:
                whd = self.results[k]['watt_hours_day']
                for d in whd.keys():
                    if d not in self.daily.keys():
                        self.daily[d] = {'hourly': {}, 'kwh': 0.0}
                    self.daily[d]['kwh'] += whd[d] / 1000
            if self.results[k].get('watt_hours_period') is not None:
                whp = self.results[k]['watt_hours_period']
                for dt in whp.keys():
                    date = dt[:10]
                    hour = int(dt[11:13])
                    if hour not in self.daily[date]['hourly'].keys():
                        self.daily[date]['hourly'][hour] = 0.0
                    self.daily[date]['hourly'][hour] += whp[dt] / 1000
        # fill out hourly forecast to cover 24 hours
        for d in self.daily.keys():
            for h in range(0,24):
                if self.daily[d]['hourly'].get(h) is None:
                    self.daily[d]['hourly'][h] = 0.0
        # drop forecast for today as it already happened
        self.keys = sorted(self.daily.keys())
        self.days = len(self.keys)
        self.values = [self.daily[d]['kwh'] for d in self.keys]
        self.total = sum(self.values)
        if self.days > 0:
            self.avg = self.total / self.days
        return

    def __str__(self) :
        # return printable Solar info
        global debug_setting
        if not hasattr(self, 'days'):
            return 'Solar: no days in forecast'
        s = f'\nSolar yield for {self.days} days'
        for d in self.keys :
            y = self.daily[d]['kwh']
            day = datetime.strptime(d, '%Y-%m-%d').strftime('%A')[:3]
            s += f"\n   {d} {day} : {y:5.2f}kWh"
        return s

    def plot_daily(self) :
        if not hasattr(self, 'daily') :
            print(f"Solcast: no daily data to plot")
            return
        plt.figure(figsize=(figure_width, figure_width/3))
        print()
        # plot estimated
        x = [f"{d} {datetime.strptime(d, '%Y-%m-%d').strftime('%A')[:3]} " for d in self.keys if d <= self.today]
        y = [self.daily[d]['kwh'] for d in self.keys if d <= self.today]
        if x is not None and len(x) != 0 :
            plt.bar(x, y, color='green', linestyle='solid', label='estimated', linewidth=2)
        # plot forecasts
        x = [f"{d} {datetime.strptime(d, '%Y-%m-%d').strftime('%A')[:3]} " for d in self.keys if d > self.today]
        y = [self.daily[d]['kwh'] for d in self.keys if d > self.today]
        if x is not None and len(x) != 0 :
            plt.bar(x, y, color='orange', linestyle='solid', label='forecast', linewidth=2)
        # annotations
        if hasattr(self, 'avg') :
            plt.axhline(self.avg, color='blue', linestyle='solid', label=f'average {self.avg:.1f} kwh / day', linewidth=2)
        title = f"Solar daily yield on {self.today} for {self.days} days"
        title += f". Total yield = {self.total:.0f} kwh, Average = {self.avg:.0f}"    
        plt.title(title, fontsize=12)
        plt.grid()
#        plt.legend(fontsize=14, loc=legend_location)
        plt.xticks(rotation=45, ha='right')
        plot_show()
        return

    def plot_hourly(self, day = None) :
        if not hasattr(self, 'daily') :
            print(f"Solar: no daily data to plot")
            return
        if day == 'today':
            day = self.today
        elif day == 'tomorrow':
            day = self.tomorrow
        elif day == 'all':
            day = self.keys
        elif day is None:
            day = [self.today, self.tomorrow]
        if type(day) is list:
            for d in day:
                self.plot_hourly(d)
            return
        plt.figure(figsize=(figure_width, figure_width/3))
        print()
        if day is None:
            day = self.tomorrow
        elif day == 'today':
            day = self.today
        elif day == 'tomorrow':
            day = self.tomorrow
        # plot forecasts
        if self.daily.get(day) is None:
            print(f"Solar: no data for {day}")
            return
        hours = sorted([h for h in self.daily[day]['hourly'].keys()])
        x = [hours_time(h) for h in hours]
        y = [self.daily[day]['hourly'][h] for h in hours]
        color = 'orange' if day > self.today else 'green'
        if x is not None and len(x) != 0 :
            plt.plot(x, y, color=color, linestyle='solid', linewidth=2)
        title = f"Solar hourly yield on {day}"
        title += f". Total yield = {self.daily[day]['kwh']:.1f}kwh"    
        plt.title(title, fontsize=12)
        plt.grid()
        plt.xticks(rotation=45, ha='right')
        plot_show()
        return


##################################################################################################
##################################################################################################
# Pushover API
##################################################################################################
##################################################################################################

pushover_user_key = None
pushover_url = "https://api.pushover.net/1/messages.json"

# generic app key for foxess cloud
foxesscloud_app_key = "aqj8up6jeg9hu4zr1pgir3368vda4q"

def pushover_post(message, file=None, app_key=None):
    global pushover_user_key, pushover_url, foxesscloud_app_key
    if pushover_user_key is None or message is None:
        return None
    if app_key is None:
        app_key = foxesscloud_app_key
    if len(message) > 1024:
        message = message[-1024:]
    body = {'token': app_key, 'user': pushover_user_key, 'message': message}
    files = {'attachment': open(file, 'rb')} if file is not None else None
    response = requests.post(pushover_url, data=body, files=files)
    if response.status_code != 200:
        print(f"** pushover_post() got response code {response.status_code}: {response.reason}")
        return None
    if debug_setting > 1:
        print(f"---- pushover message sent ----")
    return 200

spool_mode = None
spooled_output = None

# start spooling output for pushover messaging
# h is an optional message header
def output_spool(app_key=None, h=None):
    global spool_mode, spooled_output, pushover_user_key, foxesscloud_app_key
    output_close()
    if pushover_user_key is None:
        return None
    spool_mode = app_key if app_key is not None else foxesscloud_app_key
    if h is not None:
        dt_now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        h = h.replace("<time>", dt_now[11:19])
        h = h.replace("<date>", dt_now[0:10])
        h = h.replace("<datetime>", dt_now)
        spooled_output = h + "\n"
    return spool_mode

# stop spooling output and post with optional file attachment
def output_close(plot=0, file=None):
    global spool_mode, spooled_output, pushover_user_key, last_plot_filename
    if pushover_user_key is not None and spool_mode is not None and spooled_output is not None:
        if plot > 0 and file is None:
            file = last_plot_filename
        pushover_post(spooled_output, file=file, app_key=spool_mode)
    spool_mode = None
    spooled_output = None
    return None

# simple push message
def output_message(app_key=None, message=None, plot=0):
    output_spool(app_key, message)
    output_close(plot=plot)
    return None

# add to spooled_output
def output(s="", log_level=None):
    global spool_mode, spooled_output, debug_setting
    if log_level is not None and debug_setting < log_level:
        return
    # keep output stream up to date in case of problem / exception
    print(s)
    # spool output for pushover if needed
    if spool_mode is not None:
        if ((len(spooled_output) if spooled_output is not None else 0) + len(s)) > 1024:
            # more than 1024 chars, re-start spooling to avoid data loss
            output_spool(spool_mode)
        if spooled_output is None:
            spooled_output = s + "\n"
        else:
            spooled_output += s + "\n"
    return