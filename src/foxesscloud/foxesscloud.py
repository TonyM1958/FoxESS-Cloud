##################################################################################################
"""
Module:   Fox ESS Cloud
Updated:  15 September 2023
By:       Tony Matthews
"""
##################################################################################################
# Code for getting and setting inverter data via the Fox ESS cloud web site, including
# getting forecast data from solcast.com.au and sending inverter data to pvoutput.org
##################################################################################################

version = "0.5.0"
debug_setting = 1

print(f"FoxESS-Cloud version {version}")

import os.path
import json
from datetime import datetime, timedelta
from copy import deepcopy
import requests
from requests.auth import HTTPBasicAuth
import hashlib
from random_user_agent.user_agent import UserAgent
from random_user_agent.params import SoftwareName, OperatingSystem
import math
import matplotlib.pyplot as plt

software_names = [SoftwareName.CHROME.value]
operating_systems = [OperatingSystem.WINDOWS.value, OperatingSystem.LINUX.value]
user_agent_rotator = UserAgent(software_names=software_names, operating_systems=operating_systems, limit=100)

##################################################################################################
##################################################################################################
# Fox ESS Cloud API Section
##################################################################################################
##################################################################################################

def query_date(d, offset = None):
    if d is not None and len(d) < 18:
        d += ' 00:00:00'
    t = datetime.now() if d is None else datetime.strptime(d, "%Y-%m-%d %H:%M:%S")
    if offset is not None:
        t += timedelta(days = offset)
    return {'year': t.year, 'month': t.month, 'day': t.day, 'hour': t.hour, 'minute': t.minute, 'second': t.second}

# global username and password settings
username = None
password = None

token = None
token_save = "token.txt"
token_renewal = timedelta(hours=2).seconds       # interval before token needs to be renewed

# login and get token if required. Check if token has expired and renew if required.
def get_token():
    global username, password, token, device_list, device, device_id, debug_setting, token_save, token_renewal
    if token is None:
        token = {'value': None, 'valid_from': None, 'valid_for': token_renewal, 'user_agent': None, 'lang': 'en'}
    if token['value'] is None and os.path.exists(token_save):
        file = open(token_save)
        token = json.load(file)
        file.close()
    time_now = datetime.now()
    if token['value'] is not None and token['valid_from'] is not None:
        if (time_now - datetime.fromisoformat(token['valid_from'])).seconds <= token['valid_for']:
            if debug_setting > 1:
                print(f"token is still valid")
            return token['value']
    if debug_setting > 1:
        print(f"loading new token")
    device_list = None
    device = None
    token['user_agent'] = user_agent_rotator.get_random_user_agent()
    headers = {'User-Agent': token['user_agent'], 'lang': token['lang'], 'Connection': 'keep-alive'}
    if username is None or password is None or username == '<my.fox_username>' or password == 'my.fox_password':
        print(f"** please configure your Fox ESS Cloud username and password")
        return None
    credentials = {'user': username, 'password': hashlib.md5(password.encode()).hexdigest()}
    response = requests.post(url="https://www.foxesscloud.com/c/v0/user/login", headers=headers, data=json.dumps(credentials))
    if response.status_code != 200:
        print(f"** could not login to Fox ESS Cloud - check your username and password - got response code: {response.status_code}")
        return None
    result = response.json().get('result')
    if result is None:
        errno = response.json().get('errno')
        print(f"** no login result data, errno = {errno}")
        return None
    token['value'] = result.get('token')
    if token['value'] is None:
        print(f"** no token  in result data")
    token['valid_from'] = time_now.isoformat()
    if token_save is not None :
        file = open(token_save, 'w')
        json.dump(token, file, indent=4, ensure_ascii= False)
        file.close()
    return token['value']

##################################################################################################
# get user / access info
##################################################################################################

info = None

def get_info():
    global token, debug_setting, info
    if get_token() is None:
        return None
    if debug_setting > 1:
        print(f"getting access")
    headers = {'token': token['value'], 'User-Agent': token['user_agent'], 'lang': token['lang'], 'Connection': 'keep-alive'}
    response = requests.get(url="https://www.foxesscloud.com/c/v0/user/info", headers=headers)
    if response.status_code != 200:
        print(f"** get_info() got info response code: {response.status_code}")
        return None
    result = response.json().get('result')
    if result is None:
        errno = response.json().get('errno')
        print(f"** no info result, errno = {errno}")
        return None
    info = result
    response = requests.get(url="https://www.foxesscloud.com/c/v0/user/access", headers=headers)
    if response.status_code != 200:
        print(f"** get_info() got access response code: {response.status_code}")
        return None
    result = response.json().get('result')
    if result is None:
        print(f"** no access result")
        return None
    info['access'] = result['access']
    return info


##################################################################################################
# get list of sites
##################################################################################################

site_list = None
site = None

def get_site(name=None):
    global token, site_list, site, debug_setting
    if get_token() is None:
        return None
    if site is not None and name is None:
        return site
    if debug_setting > 1:
        print(f"getting sites")
    headers = {'token': token['value'], 'User-Agent': token['user_agent'], 'lang': token['lang'], 'Connection': 'keep-alive'}
    query = {'pageSize': 100, 'currentPage': 1, 'total': 0, 'condition': {'status': 0, 'contentType': 2, 'content': ''} }
    response = requests.post(url="https://www.foxesscloud.com/c/v1/plant/list", headers=headers, data=json.dumps(query))
    if response.status_code != 200:
        print(f"** get_sites() got response code: {response.status_code}")
        return None
    result = response.json().get('result')
    if result is None:
        errno = response.json().get('errno')
        print(f"** no site list result data, errno = {errno}")
        return None
    total = result.get('total')
    if total is None or total == 0 or total > 100:
        print(f"** invalid list of sites returned: {total}")
        return None
    site_list = result.get('plants')
    n = None
    if len(site_list) > 1:
        if name is not None:
            for i in range(len(site_list)):
                if site_list[i]['name'][:len(name)].upper() == name.upper():
                    n = i
                    break
        if n is None:
            print(f"\nget_site(): please provide a name from the list:")
            for s in site_list:
                print(f"Name={s['name']}")
            return None
    else:
        n = 0
    site = site_list[n]
    return site

##################################################################################################
# get list of data loggers
##################################################################################################

logger_list = None
logger = None

def get_logger(sn=None):
    global token, logger_list, logger, debug_setting
    if get_token() is None:
        return None
    if logger is not None and sn is None:
        return logger
    if debug_setting > 1:
        print(f"getting loggers")
    headers = {'token': token['value'], 'User-Agent': token['user_agent'], 'lang': token['lang'], 'Connection': 'keep-alive'}
    query = {'pageSize': 100, 'currentPage': 1, 'total': 0, 'condition': {'communication': 0, 'moduleSN': '', 'moduleType': ''} }
    response = requests.post(url="https://www.foxesscloud.com/c/v0/module/list", headers=headers, data=json.dumps(query))
    if response.status_code != 200:
        print(f"** get_logger() got response code: {response.status_code}")
        return None
    result = response.json().get('result')
    if result is None:
        errno = response.json().get('errno')
        print(f"** no logger list result data, errno = {errno}")
        return None
    total = result.get('total')
    if total is None or total == 0 or total > 100:
        print(f"** invalid list of loggers returned: {total}")
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
            print(f"\nget_logger(): please provide a serial number from this list:")
            for l in logger_list:
                print(f"SN={l['moduleSN']}, Plant={l['plantName']}, StationID={l['stationID']}")
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
    global token, device_list, device, device_id, device_sn, firmware, battery, raw_vars, debug_setting
    if get_token() is None:
        return None
    if device is not None:
        if sn is None:
            return device
        if device_sn[:len(sn)].upper() == sn.upper():
            return device
    if debug_setting > 1:
        print(f"getting device")
    if sn is None and device_sn is not None and len(device_sn) == 15:
        sn = device_sn
    # get device list
    headers = {'token': token['value'], 'User-Agent': token['user_agent'], 'lang': token['lang'], 'Connection': 'keep-alive'}
    query = {'pageSize': 100, 'currentPage': 1, 'total': 0, 'queryDate': {'begin': 0, 'end':0} }
    response = requests.post(url="https://www.foxesscloud.com/c/v0/device/list", headers=headers, data=json.dumps(query))
    if response.status_code != 200:
        print(f"** get_device() got response code: {response.status_code}")
        return None
    result = response.json().get('result')
    if result is None:
        errno = response.json().get('errno')
        print(f"** no device list result data, errno = {errno}")
        return None
    total = result.get('total')
    if total is None or total == 0 or total > 100:
        print(f"** invalid list of devices returned: {total}")
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
            print(f"\nget_device(): please provide a serial number from this list:")
            for d in device_list:
                print(f"SN={d['deviceSN']}, Type={d['deviceType']}")
            return None
    # load information for the device
    device = device_list[n]
    device_id = device.get('deviceID')
    device_sn = device.get('deviceSN')
    firmware = None
    battery = None
    battery_settings = None
    raw_vars = get_vars()
    # parse the model code to work out attributes
    model_code = device['deviceType'].upper()
    # first 2 letters / numbers e.g. H1, H3, KH
    if model_code[:2] == 'KH':
        mode_code = 'KH-' + model_code[2:]
    elif model_code[:4] == 'AIO-':
        mode_code = 'AIO' + model_code[4:]
    device['eps'] = 'E' in model_code
    parts = model_code.split('-')
    model = parts[0]
    if model not in ['KH', 'H1', 'AC1', 'H3', 'AC3', 'AIOH1', 'AIOH3']:
        print(f"** device model not recognised for deviceType: {device['deviceType']}")
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
        print(f"** device power not found for deviceType: {device['deviceType']}")
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
    global token, device_id, debug_setting
    if get_device() is None:
        return None
    if debug_setting > 1:
        print(f"getting variables")
    headers = {'token': token['value'], 'User-Agent': token['user_agent'], 'lang': token['lang'], 'Connection': 'keep-alive'}
    params = {'deviceID': device_id}
    # v1 api required for full list with {name, variable, unit}
    response = requests.get(url="https://www.foxesscloud.com/c/v1/device/variables", params=params, headers=headers)
    if response.status_code != 200:
        print(f"** get_vars() got response code: {response.status_code}")
        return None
    result = response.json().get('result')
    if result is None:
        errno = response.json().get('errno')
        print(f"** no variables result, errno = {errno}")
        return None
    vars = result.get('variables')
    if vars is None:
        print(f"** no variables list")
        return None
    return vars

##################################################################################################
# get current firmware versions for selected device
##################################################################################################

firmware = None

def get_firmware():
    global token, device_id, firmware, debug_setting
    if get_device() is None:
        return None
    if debug_setting > 1:
        print(f"getting firmware")
    headers = {'token': token['value'], 'User-Agent': token['user_agent'], 'lang': token['lang'], 'Connection': 'keep-alive'}
    params = {'deviceID': device_id}
    response = requests.get(url="https://www.foxesscloud.com/c/v0/device/addressbook", params=params, headers=headers)
    if response.status_code != 200:
        print(f"** get_firmware() got response code: {response.status_code}")
        return None
    result = response.json().get('result')
    if result is None:
        errno = response.json().get('errno')
        print(f"** no firmware result data, errno = {errno}")
        return None
    firmware = result.get('softVersion')
    if firmware is None:
        print(f"** no firmware data")
        return None
    return firmware

##################################################################################################
# get battery info and save to battery
##################################################################################################

battery = None
battery_settings = None

def get_battery():
    global token, device_id, battery, debug_setting
    if get_device() is None:
        return None
    if debug_setting > 1:
        print(f"getting battery")
    headers = {'token': token['value'], 'User-Agent': token['user_agent'], 'lang': token['lang'], 'Connection': 'keep-alive'}
    params = {'id': device_id}
    response = requests.get(url="https://www.foxesscloud.com/c/v0/device/battery/info", params=params, headers=headers)
    if response.status_code != 200:
        print(f"** get_battery() got response code: {response.status_code}")
        return None
    result = response.json().get('result')
    if result is None:
        errno = response.json().get('errno')
        print(f"** no battery info, errno = {errno}")
        return None
    battery = result
    return battery

##################################################################################################
# get charge times and save to battery_settings
##################################################################################################

def get_charge():
    global token, device_sn, battery_settings, debug_setting
    if get_device() is None:
        return None
    if debug_setting > 1:
        print(f"getting charge times")
    headers = {'token': token['value'], 'User-Agent': token['user_agent'], 'lang': token['lang'], 'Connection': 'keep-alive'}
    params = {'sn': device_sn}
    response = requests.get(url="https://www.foxesscloud.com/c/v0/device/battery/time/get", params=params, headers=headers)
    if response.status_code != 200:
        print(f"** get_charge() got response code: {response.status_code}")
        return None
    result = response.json().get('result')
    if result is None:
        print(f"** no charge result data")
        return None
    times = result.get('times')
    if times is None:
        errno = response.json().get('errno')
        print(f"** no times data, errno = {errno}")
        return None
    if battery_settings is None:
        battery_settings = {}
    battery_settings['times'] = times
    return battery_settings


##################################################################################################
# set charge times from battery_settings or parameters
##################################################################################################

# helper to format time period structure
def time_period(t):
    result = f"{t['startTime']['hour']:02d}:{t['startTime']['minute']:02d} - {t['endTime']['hour']:02d}:{t['endTime']['minute']:02d}"
    if t['enableGrid']:
        result += f" Charge from grid"
    return result

def set_charge(ch1 = None, st1 = None, en1 = None, ch2 = None, st2 = None, en2 = None):
    global token, device_sn, battery_settings, debug_setting
    if get_device() is None:
        return None
    if battery_settings.get('times') is None or len(battery_settings['times']) != 2:
        print(f"** set_charge(): invalid battery settings")
        print(battery_settings)
        return None
    # configure time period 1
    if st1 is not None:
        if st1 == en1:
            st1 = 0
            en1 = 0
            ch1 = False
        st1 = time_hours(st1)
        en1 = time_hours(en1)
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
        st2 = time_hours(st2)
        en2 = time_hours(en2)
        battery_settings['times'][1]['enableCharge'] = True
        battery_settings['times'][1]['enableGrid'] = True if ch2 == True or ch2 == 1 else False
        battery_settings['times'][1]['startTime']['hour'] = int(st2)
        battery_settings['times'][1]['startTime']['minute'] = int(60 * (st2 - int(st2)) + 0.5)
        battery_settings['times'][1]['endTime']['hour'] = int(en2)
        battery_settings['times'][1]['endTime']['minute'] = int(60 * (en2 - int(en2)) + 0.5)
    if debug_setting > 1:
        print(battery_settings)
        return None
    if debug_setting > 0:
        print(f"\nSetting time periods:")
        print(f"   Time Period 1 = {time_period(battery_settings['times'][0])}")
        print(f"   Time Period 2 = {time_period(battery_settings['times'][1])}")
    # set charge times
    headers = {'token': token['value'], 'User-Agent': token['user_agent'], 'lang': token['lang'], 'Connection': 'keep-alive'}
    data = {'sn': device_sn, 'times': battery_settings.get('times')}
    response = requests.post(url="https://www.foxesscloud.com/c/v0/device/battery/time/set", headers=headers, data=json.dumps(data))
    if response.status_code != 200:
        print(f"** set_charge() got response code: {response.status_code}")
        return None
    result = response.json().get('errno')
    if result != 0:
        print(f"** return code = {result}")
    elif debug_setting > 1:
        print(f"success") 
    return result

##################################################################################################
# get min soc settings and save in battery_settings
##################################################################################################

def get_min():
    global token, device_sn, battery_settings, debug_setting
    if get_device() is None:
        return None
    if debug_setting > 1:
        print(f"getting min soc")
    headers = {'token': token['value'], 'User-Agent': token['user_agent'], 'lang': token['lang'], 'Connection': 'keep-alive'}
    params = {'sn': device_sn}
    response = requests.get(url="https://www.foxesscloud.com/c/v0/device/battery/soc/get", params=params, headers=headers)
    if response.status_code != 200:
        print(f"** get_min() got response code: {response.status_code}")
        return None
    result = response.json().get('result')
    if result is None:
        errno = response.json().get('errno')
        print(f"** no min soc result data, errno = {errno}")
        return None
    if battery_settings is None:
        battery_settings = {}
    battery_settings['minSoc'] = result.get('minSoc')
    battery_settings['minGridSoc'] = result.get('minGridSoc')
    return battery_settings

##################################################################################################
# set min soc from battery_settings or parameters
##################################################################################################

def set_min(minGridSoc = None, minSoc = None):
    global token, device_sn, bat_settings, debug_setting
    if get_device() is None:
        return None
    if battery_settings.get('minGridSoc') is None or battery_settings.get('minSoc') is None:
        print(f"** no min soc settings")
        print(battery_settings)
        return None
    if minGridSoc is not None:
        battery_settings['minGridSoc'] = minGridSoc
    if minSoc is not None:
        battery_settings['minSoc'] = minSoc
    if debug_setting > 1:
        print(battery_settings)
        return None
    if debug_setting > 0:
        print(f"setting min soc")
    headers = {'token': token['value'], 'User-Agent': token['user_agent'], 'lang': token['lang'], 'Connection': 'keep-alive'}
    data = {'minGridSoc': battery_settings['minGridSoc'], 'minSoc': battery_settings['minSoc'], 'sn': device_sn}
    response = requests.post(url="https://www.foxesscloud.com/c/v0/device/battery/soc/set", headers=headers, data=json.dumps(data))
    if response.status_code != 200:
        print(f"** set_min() got response code: {response.status_code}")
        return None
    result = response.json().get('errno')
    if result != 0:
        print(f"** return code = {result}")
    elif debug_setting > 1:
        print(f"success") 
    return result

##################################################################################################
# get times and min soc settings and save in bat_settings
##################################################################################################

def get_settings():
    global battery_settings
    if battery_settings is None or battery_settings.get('times') is None:
        get_charge()
    if battery_settings.get('minGridSoc') is None:
        get_min()
    return battery_settings

##################################################################################################
# get work mode
##################################################################################################

work_mode = None

def get_work_mode():
    global token, device_id, work_mode, debug_setting
    if get_device() is None:
        return None
    if debug_setting > 1:
        print(f"getting work mode")
    headers = {'token': token['value'], 'User-Agent': token['user_agent'], 'lang': token['lang'], 'Connection': 'keep-alive'}
    params = {'id': device_id, 'hasVersionHead': 1, 'key': 'operation_mode__work_mode'}
    response = requests.get(url="https://www.foxesscloud.com/c/v0/device/setting/get", params=params, headers=headers)
    if response.status_code != 200:
        print(f"** get_work_mode() got response code: {response.status_code}")
        return None
    result = response.json().get('result')
    if result is None:
        errno = response.json().get('errno')
        print(f"** no work mode result data, errno = {errno}")
        return None
    values = result.get('values')
    if values is None:
        print(f"** no work mode values data")
        return None
    work_mode = values.get('operation_mode__work_mode')
    if work_mode is None:
        print(f"** no work mode data")
        return None
    return work_mode

##################################################################################################
# set work mode
##################################################################################################

work_modes = ['SelfUse', 'Feedin', 'Backup', 'PowerStation', 'PeakShaving']

def set_work_mode(mode):
    global token, device_id, work_modes, work_mode, debug_setting
    if get_device() is None:
        return None
    if mode not in work_modes:
        print(f"** work mode: must be one of {work_modes}")
        return None
    if debug_setting > 1:
        print(mode)
        return None
    if debug_setting > 0:
        print(f"setting work mode")
    headers = {'token': token['value'], 'User-Agent': token['user_agent'], 'lang': token['lang'], 'Connection': 'keep-alive'}
    data = {'id': device_id, 'key': 'operation_mode__work_mode', 'values': {'operation_mode__work_mode': mode}, 'raw': ''}
    response = requests.post(url="https://www.foxesscloud.com/c/v0/device/setting/set", headers=headers, data=json.dumps(data))
    if response.status_code != 200:
        print(f"** set_work_mode() got response code: {response.status_code}")
        return None
    result = response.json().get('errno')
    if result != 0:
        print(f"** return code = {result}")
        return None
    elif debug_setting > 1:
        print(f"success")
    work_mode = mode
    return work_mode


##################################################################################################
# get raw data values
##################################################################################################
# returns a list of variables and their values / attributes
# time_span = 'hour', 'day', 'week'. For 'week', gets history of 7 days up to and including d
# d = day 'YYYY-MM-DD'. Can also include 'HH:MM' in 'hour' mode
# v = list of variables to get
# summary = 0: raw data, 1: add max, min, sum, 2: summarise and drop raw data, 3: calculate state
# save = "xxxxx": save the raw results to xxxxx_raw_<time_span>_<d>.json
# load= "<file>": load the raw results from <file>
##################################################################################################

# variables that cover inverter power data: generationPower must be first
power_vars = ['generationPower', 'feedinPower','loadsPower','gridConsumptionPower','batChargePower', 'batDischargePower', 'pvPower', 'meterPower2']
#  names after integration of power to energy. List must be in the same order as above. input_daily must be last
energy_vars = ['output_daily', 'feedin_daily', 'load_daily', 'grid_daily', 'bat_charge_daily', 'bat_discharge_daily', 'pv_energy_daily', 'ct2_daily', 'input_daily']

def get_raw(time_span='hour', d=None, v=None, summary=1, save=None, load=None, plot=0):
    global token, device_id, debug_setting, raw_vars, off_peak1, off_peak2, peak, flip_ct2, tariff, max_power_kw
    if get_device() is None:
        return None
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
            plot_raw(result_list, plot)
        return result_list
    if v is None:
        if raw_vars is None:
            raw_vars = get_vars()
        v = [x['variable'] for x in raw_vars]
    elif type(v) is not list:
        v = [v]
    for var in v:
        if var not in [x['variable'] for x in raw_vars]:
            print(f"** get_raw(): invalid variable '{var}'")
            print(f"{[x['variable'] for x in raw_vars]}")
            return None
    if debug_setting > 1:
        print(f"getting raw data")
    if load is None:
        headers = {'token': token['value'], 'User-Agent': token['user_agent'], 'lang': token['lang'], 'Connection': 'keep-alive'}
        query = {'deviceID': device_id, 'variables': v, 'timespan': time_span, 'beginDate': query_date(d)}
        response = requests.post(url="https://www.foxesscloud.com/c/v0/device/history/raw", headers=headers, data=json.dumps(query))
        if response.status_code != 200:
            print(f"** get_raw() got response code: {response.status_code}")
            return None
        result = response.json().get('result')
        if result is None:
            errno = response.json().get('errno')
            print(f"** no raw data, errno = {errno}")
            return None
    else:
        file = open(load)
        result = json.load(file)
        file.close()
    if save is not None:
        file_name = save + "_raw_" + time_span + "_" + d[0:10].replace('-','') + ".txt"
        file = open(file_name, 'w')
        json.dump(result, file, indent=4, ensure_ascii= False)
        file.close()
    for var in result:
        var['date'] = d[0:10]
    if summary == 0 or time_span == 'hour':
        if plot > 0:
            plot_raw(result, plot)
        return result
    # integrate kW to kWh based on 5 minute samples
    if debug_setting > 1:
        print(f"calculating summary data")
    # copy generationPower to produce inputPower data
    input_name = None
    if 'generationPower' in v:
        input_name = energy_vars[-1]
        input_result = deepcopy(result[v.index('generationPower')])
        input_result['name'] = input_name
        for y in input_result['data']:
            y['value'] = -y['value'] if y['value'] < 0.0 else 0.0
        result.append(input_result)
    for var in result:
        energy = var['unit'] == 'kW'
        hour = 0
        if energy:
            kwh = 0.0       # kwh total
            kwh_off = 0.0   # kwh during off peak time (02:00-05:00)
            kwh_peak = 0.0  # kwh during peak time (16:00-19:00)
            kwh_neg = 0.0
        sum = 0.0
        count = 0
        max = None
        max_time = None
        min = None
        min_time = None
        if summary == 3 and energy:
            var['state'] = [{}]
        for y in var['data']:
            h = time_hours(y['time'][11:19]) # time
            value = y['value']
            sum += value
            count += 1
            max = value if max is None or value > max else max
            min = value if min is None or value < min else min
            if energy:
                e = value / 12      # convert kW samples to kWh energy
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
                    var['state'][hour]['state'] = round(kwh,3)
                var['kwh'] = round(kwh,3)
                var['kwh_off'] = round(kwh_off,3)
                var['kwh_peak'] = round(kwh_peak,3)
                var['kwh_neg'] = round(kwh_neg,3)
        var['count'] = count
        var['average'] = round(sum / count, 3) if count > 0 else None
        var['max'] = round(max, 3) if max is not None else None
        var['max_time'] = var['data'][[y['value'] for y in var['data']].index(max)]['time'][11:16] if max is not None else None
        var['min'] = round(min, 3) if min is not None else None
        var['min_time'] = var['data'][[y['value'] for y in var['data']].index(min)]['time'][11:16] if min is not None else None
        if summary >= 2:
            if energy and var['variable'] in power_vars and (input_name is None or var['name'] != input_name):
                var['name'] = energy_vars[power_vars.index(var['variable'])]
            if energy:
                var['unit'] = 'kWh'
            del var['data']
    if plot > 0 and summary < 2:
        plot_raw(result)
    return result

# plot raw results data
def plot_raw(result, plot=1):
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
            if lines == 0:
                plt.figure(figsize=(figure_width, figure_width/3))
                plt.xticks(ticks=range(0,24), labels=[hours_time(h) for h in range(0,24)], rotation=90, fontsize=8)
            for v in [v for v in result if v['unit'] == unit and v['date'] == d]:
                n = len(v['data'])
                x = [time_hours(v['data'][i]['time'][11:16]) for i in range(0, n)]
                y = [v['data'][i]['value'] for i in range(0, n)]
                name = v['name']
                label = f"{name} {d}" if plot == 2 and len(dates) > 1 else name
                plt.plot(x, y ,label=label)
                lines += 1
            if lines >= 1 and (plot == 1 or d == dates[-1]) :
                if lines > 1:
                    plt.legend(fontsize=6)
                title = f"Units = {unit}"
                title = f" {d}, {title}" if plot == 1 or len(dates) == 1 or lines == 1 else title
                title = f"{name}, {title}" if len(vars) == 1 or lines == 1 else title
                plt.title(title, fontsize=12)
                plt.grid()
                plt.show()
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
# load= "<file>": load the report results from <file>
##################################################################################################

report_vars = ['generation', 'feedin', 'loads', 'gridConsumption', 'chargeEnergyToTal', 'dischargeEnergyToTal']

def get_report(report_type='day', d=None, v=None, summary=1, save=None, load=None, plot=0):
    global token, device_id, var_list, debug_setting, report_vars
    if get_device() is None:
        return None
    # process list of days
    if d is not None and type(d) is list:
        result_list = []
        for day in d:
            result = get_report(report_type, d=day, v=v, summary=summary, save=save, load=load, plot=0)
            if result is None:
                return None
            result_list += result
        if plot > 0:
            plot_report(result_list, plot)
        return result_list
    # validate parameters
    report_type = report_type.lower()
    summary = 1 if summary == True else 0 if summary == False else summary
    if summary == 2 and report_type != 'day':
        summary = 1
    if summary == 0 and report_type == 'week':
        report_type = 'day'
    headers = {'token': token['value'], 'User-Agent': token['user_agent'], 'lang': token['lang'], 'Connection': 'keep-alive'}
    if d is None:
        d = datetime.strftime(datetime.now(), "%Y-%m-%d")
    if v is None:
        v = report_vars
    elif type(v) is not list:
        v = [v]
    for var in v:
        if var not in report_vars:
            print(f"** get_report(): invalid variable '{var}'")
            print(f"{report_vars}")
            return None
    if debug_setting > 1:
        print(f"getting report data")
    current_date = query_date(None)
    main_date = query_date(d)
    side_result = None
    if report_type in ('day', 'week') and summary > 0:
        # side report needed
        side_date = query_date(d, -7) if report_type == 'week' else main_date
        if report_type == 'day' or main_date['month'] != side_date['month']:
            query = {'deviceID': device_id, 'reportType': 'month', 'variables': v, 'queryDate': side_date}
            response = requests.post(url="https://www.foxesscloud.com/c/v0/device/history/report", headers=headers, data=json.dumps(query))
            if response.status_code != 200:
                print(f"** get_report() side report got response code: {response.status_code}")
                return None
            side_result = response.json().get('result')
            if side_result is None:
                errno = response.json().get('errno')
                print(f"** no side report data, errno = {errno}")
                return None
    if summary < 2:
        query = {'deviceID': device_id, 'reportType': report_type.replace('week', 'month'), 'variables': v, 'queryDate': main_date}
        response = requests.post(url="https://www.foxesscloud.com/c/v0/device/history/report", headers=headers, data=json.dumps(query))
        if response.status_code != 200:
            print(f"** get_report() main report got response code: {response.status_code}")
            return None
        result = response.json().get('result')
        if result is None:
            errno = response.json().get('errno')
            print(f"** no main report data, errno = {errno}")
            return None
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
        file = open(file_name, 'w')
        json.dump(result, file, indent=4, ensure_ascii= False)
        file.close()
    if summary == 0:
        return result
    # calculate and add summary data
    for i, var in enumerate(result):
        count = 0
        sum = 0.0
        max = None
        min = None
        for y in var['data']:
            value = y['value']
            count += 1
            sum += value
            max = value if max is None or value > max else max
            min = value if min is None or value < min else min
        # correct day total from side report
        var['total'] = round(sum,3) if report_type != 'day' else side_result[i]['data'][int(main_date['day'])-1]['value']
        var['type'] = report_type
        if summary < 2:
            var['sum'] = round(sum,3)
            var['average'] = round(var['total'] / count, 3) if count > 0 else None
            var['date'] = d
            var['count'] = count
            var['max'] = round(max,3) if max is not None else None
            var['max_index'] = [y['value'] for y in var['data']].index(max) if max is not None else None
            var['min'] = round(min,3) if min is not None else None
            var['min_index'] = [y['value'] for y in var['data']].index(min) if min is not None else None
    if plot > 0 and summary < 2:
        plot_report(result, plot)
    return result

# plot get_report result
def plot_report(result, plot=1):
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
#    print(f"vars = {vars}, dates = {dates}, types = {types}, index = {index}")
    if len(vars) == 0:
        return
    # plot variables by date with the same units on the same charts
    lines = 0
    width = 0.8 / (len(vars) if plot == 2 else len(dates))
    align = 0.0
    for var in vars:
        if lines == 0:
            plt.figure(figsize=(figure_width, figure_width/3))
            if types[0] == 'day':
                plt.xticks(ticks=index, labels=[hours_time(h) for h in range(0,24)],rotation=90, fontsize=8)
        for v in [v for v in result if v['variable'] == var]:
            d = v['date']
            n = len(v['data'])
            x = [i + align  for i in range(1, n+1)]
            y = [v['data'][i]['value'] for i in range(0, n)]
            label = f"{var} {d}"
            plt.bar(x, y ,label=label, width=width)
            align += width
            lines += 1
        if lines >= 1 and (plot == 1 or d == dates[-1]) :
            if lines > 1:
                plt.legend(fontsize=6)
            title = var
            plt.title(title, fontsize=12)
            plt.grid()
            plt.show()
            lines = 0
            align = -0.4
    return

##################################################################################################
# get earnings data
##################################################################################################

def get_earnings():
    global token, device_id, var_list, debug_setting, report_vars
    if get_device() is None:
        return None
    if debug_setting > 1:
        print(f"getting earnings")
    headers = {'token': token['value'], 'User-Agent': token['user_agent'], 'lang': token['lang'], 'Connection': 'keep-alive'}
    params = {'deviceID': device_id}
    response = requests.get(url="https://www.foxesscloud.com/c/v0/device/earnings", params=params, headers=headers)
    if response.status_code != 200:
        print(f"** get_earnings() got response code: {response.status_code}")
        return None
    result = response.json().get('result')
    if result is None:
        errno = response.json().get('errno')
        print(f"** no earnings data, errno = {errno}")
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
# deimal hours allows maths operations to be performed simply

# roll over decimal times after maths and round to 1 minute
def round_time(h):
    while h < 0:
        h += 24
    while h >= 24:
        h -= 24
    return int(h) + int(60 * (h - int(h)) + 0.5) / 60

# convert time string HH:MM:SS to decimal hours
def time_hours(s, d = None):
    if s is None:
        s = d
    if type(s) is float:
        return s
    elif type(s) is int:
        return float(s)
    elif type(s) is str and s.replace(':', '').isnumeric() and s.count(':') <= 2:
        s += ':00' if s.count(':') == 1 else ''
        return sum(float(t) / x for x, t in zip([1, 60, 3600], s.split(":")))
    print(f"** invalid time string for time_hours()")
    return None

# convert decimal hours to time string HH:MM:SS
def hours_time(h, ss = False, day = False, mm = True):
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

# True if a decimal hour is within a time period
def hour_in(h, period):
    if period is None:
        return False
    s = period['start']
    e = period['end']
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

# Return the hours in a time period with optional value check
def period_hours(period, check = None, value = 1):
    if period is None:
        return 0
    if check is not None and period[check] != value:
        return 0
    return round_time(period['end'] - period['start'])

def format_period(period):
    return f"{hours_time(period['start'])} - {hours_time(period['end'])}"


##################################################################################################
# Tariffs / time of user (TOU)
# time values are decimal hours
##################################################################################################

# time periods for Octopus Flux
octopus_flux = {
    'name': 'Octopus Flux',
    'off_peak1': {'start': 2.0, 'end': 5.0, 'force': 1},        # off-peak period 1 / am charging period
    'off_peak2': {'start': 0.0, 'end': 0.0, 'force': 0},        # off-peak period 2 / pm charging period
    'peak': {'start': 16.0, 'end': 19.0 },                      # peak period 1
    'peak2': {'start': 0.0, 'end': 0.0 },                       # peak period 2
    'feedin': {'start': 16.0, 'end': 7.0},                      # when feedin work mode is set
    'backup': {'start': 0.0, 'end': 0.0},                       # when backup work mode is set
    }

# time periods for Intelligent Octopus
intelligent_octopus = {
    'name': 'Intelligent Octopus',
    'off_peak1': {'start': 23.5, 'end': 5.5, 'force': 1},
    'off_peak2': {'start': 0.0, 'end': 0.0, 'force': 0},
    'peak': {'start': 0.0, 'end': 0.0 },
    'peak2': {'start': 0.0, 'end': 0.0 },
    'feedin': {'start': 0.0, 'end': 0.0},
    'backup': {'start': 0.0, 'end': 0.0},
    }

# time periods for Octopus Cosy
octopus_cosy = {
    'name': 'Octopus Cosy',
    'off_peak1': {'start': 4.0, 'end': 7.0, 'force': 1},
    'off_peak2': {'start': 13.0, 'end': 16.0, 'force': 0},
    'peak': {'start': 16.0, 'end': 19.0 },
    'peak2': {'start': 0.0, 'end': 0.0 },
    'feedin': {'start': 0.0, 'end': 0.0},
    'backup': {'start': 0.0, 'end': 0.0},
    }   

# time periods for Octopus Go
octopus_go = {
    'name': 'Octopus Go',
    'off_peak1': {'start': 0.5, 'end': 4.5, 'force': 1},
    'off_peak2': {'start': 0.0, 'end': 0.0, 'force': 0},
    'peak': {'start': 0.0, 'end': 0.0 },
    'peak2': {'start': 0.0, 'end': 0.0 },
    'feedin': {'start': 0.0, 'end': 0.0},
    'backup': {'start': 0.0, 'end': 0.0},
    }

# custom time periods / template
custom_periods = {'name': 'Custom',
    'off_peak1': {'start': 2.0, 'end': 5.0, 'force': 1},
    'off_peak2': {'start': 0.0, 'end': 0.0, 'force': 0},
    'peak': {'start': 16.0, 'end': 19.0 },
    'peak2': {'start': 0.0, 'end': 0.0 },
    'feedin': {'start': 0.0, 'end': 0.0},
    'backup': {'start': 0.0, 'end': 0.0},
    }

tariff_list = [octopus_flux, intelligent_octopus, octopus_cosy, octopus_go, custom_periods]
tariff = octopus_flux

charge_config = {
    'min_hours': 0.25,                # minimum charge time in decimal hours
    'min_kwh': 1.0,                   # minimum to add in kwh
    'generation_days': 3,             # number of days to use for average generation (1-7)
    'consumption_days': 3,            # number of days to use for average consumption (1-7)
    'consumption_span': 'week',       # 'week' = last 7 days or 'weekday' = last 7 weekdays
    'conversion_loss': 0.94,          # conversion loss from inverter power conversion
    'battery_loss': 0.95,             # conversion loss from battery charge to residual
    'operation_loss': 0.1,            # inverter operating power kW
    'volt_swing': 4,                  # bat volt % swing from 0% to 100% SoC
    'volt_overdrive': 1.007,          # increase in bat volt when charging
    'solcast': {'start' : 21.0},
    'solar':   {'start': 21.0}
}

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
        print(f"** can only create 24 hour profile from report_type 'day' or 'week'")
        return None
    data = []
    for h in range(0,24):
        data.append((0.0, 0)) # value sum, count of values
    totals = 0
    n = 0
    for day in result:
        hours = 0
        # sum and count available values by hour
        for i in range(0, len(day['data'])):
            data[i] = (data[i][0] + day['data'][i]['value'], data[i][1]+1)
            hours += 1
        totals += day['total'] * (24 / hours if hours >= 4 else 1)
        n += 1
    daily_average = round(totals / n, 3) if n !=0 else None
    # average for each hour
    by_hour = []
    for h in data:
        by_hour.append(h[0] / h[1] if h[1] != 0 else 0.0)   # sum / count
    if daily_average is None:
        print(f"** cannot create profile where daily average is None")
        return None
    # rescale to match daily_average
    current_total = sum(by_hour)
    return (daily_average, [round(h * daily_average / current_total, 3) for h in by_hour])

# take forecast and return (value and timed profile)
def forecast_value_timed(forecast, today, tomorrow, hour_now, run_time):
    if not hasattr(forecast, 'daily'):
        return None
    value = round(forecast.daily[tomorrow]['kwh'], 1)
    profile = []
    for h in range(0, 24):
        profile.append(c_float(forecast.daily[tomorrow]['hourly'].get(h)))
    timed = []
    for h in range(int(hour_now), 24):
        timed.append(c_float(forecast.daily[today]['hourly'].get(h)))
    return (value, (timed + profile + profile)[:run_time])

##################################################################################################
# calculate charge needed from current battery charge, forecast yield and expected load
##################################################################################################

# work out the charge times to set using the parameters:
#  forecast: the kWh expected tomorrow. If none, forecast data is loaded from solcast
#  annual_consumption: the kWh consumed each year via the inverter
#  contingency: a factor to add to allow for variations. Default is 20%
#  force_charge: if True, force charge is set. If false, force charge is not set
#  charge_current: the maximum charge current that will be applied. Default is 35A
#  export_limit: the kW of charge that will be applied (battery voltage * max current)
#  run_after: time constraint for Solcast and updating settings. The default is 21:00.
#  update_settings: 1 allows inverter charge time settings to be updated. The default is 0
#  show_data: 1 shows battery SoC, 2 shows battery residual. Default = 0
#  show_plot: 1 plots battery SoC, 2 plots battery residual. Default = 1

def charge_needed(forecast = None, annual_consumption = None, contingency = 20,
        force_charge = None, timed_mode = None, charge_current = None, export_power = None,
        update_settings = 0, show_data = None, show_plot = None, run_after = None):
    global device, seasonality, solcast_api_key, debug_setting, tariff, solar_arrays
    print(f"\n---------------- charge_needed ----------------")
    # validate parameters
    args = locals()
    s = ""
    for k in [k for k in args.keys() if args[k] is not None]:
        s += f"\n  {k} = {args[k]}"
    if len(s) > 0:
        print(f"Parameters: {s}")
    # convert any boolean flag values and set default parameters
    force_charge = 1 if force_charge is not None and (force_charge == 1 or force_charge == True) else 0
    update_settings = 1 if update_settings is not None and (update_settings == 1 or update_settings == True) else 0
    timed_mode = 1 if timed_mode is not None and (timed_mode == 1 or timed_mode == True) else 0
    show_data = 1 if show_data is None or show_data == True else 0 if show_data == False else show_data
    show_plot = 1 if show_plot is None or show_plot == True else 0 if show_plot == False else show_plot
    run_after = time_hours(run_after, 22)
    # get dates and times
    now = datetime.now()
    today = datetime.strftime(now, '%Y-%m-%d')
    tomorrow = datetime.strftime(now + timedelta(days=1), '%Y-%m-%d')
    hour_now = time_hours(f"{now.hour:02}:{now.minute:02}")
    print(f"  datetime = {today} {hours_time(hour_now)}")
    if tariff is not None:
        print(f"  tariff = {tariff['name']}")
    # get next charge times from am/pm charge times
    start_am = time_hours(tariff['off_peak1']['start'] if tariff is not None else 2.0)
    end_am = time_hours(tariff['off_peak1']['end'] if tariff is not None else 5.0)
    force_charge_am = 0 if tariff is not None and tariff['off_peak1']['force'] == 0 or force_charge == 0 else 1
    time_to_am = int(round_time(start_am - hour_now + 1))
    start_pm = time_hours(tariff['off_peak2']['start'] if tariff is not None else 0.0)
    end_pm = time_hours(tariff['off_peak2']['end'] if tariff is not None else 0.0)
    force_charge_pm = 0 if tariff is not None and tariff['off_peak2']['force'] == 0 or force_charge == 0 else 1
    time_to_pm = int(round_time(start_pm - hour_now + 1)) if start_pm > 0 else None
    # choose next charge time period
    if time_to_pm is not None and time_to_pm < time_to_am:
        time_to_next = time_to_pm
        run_time = time_to_am + 1
        charge_pm = True
    else:
        time_to_next = time_to_am
        run_time = time_to_am + 25 if time_to_pm is None else time_to_pm + 1
        charge_pm = False
    start_at = start_pm if charge_pm else start_am
    end_by = end_pm if charge_pm else end_am
    force_charge = force_charge_pm if charge_pm else force_charge_am
    if debug_setting > 1:
        print(f"\nstart_am = {start_am}, end_am = {end_am}, force_am = {force_charge_am}, time_to_am = {time_to_am}")
        print(f"start_pm = {start_pm}, end_pm = {end_pm}, force_pm = {force_charge_pm}, time_to_pm = {time_to_pm}")
        print(f"start_at = {start_at}, end_by = {end_by}, force_charge = {force_charge}")
        print(f"time_to_next = {time_to_next}, run_time = {run_time}, charge_pm = {charge_pm}")
    # get battery info
    get_settings()
    get_battery()
    min_soc = battery_settings['minGridSoc']
    soc = battery['soc']
    bat_volt = battery['volt']
    residual = round(battery['residual']/1000, 1)
    capacity = round(residual * 100 / soc if soc > 0 else residual, 1)
    reserve = round(capacity * min_soc / 100, 1)
    available = round(residual - reserve, 1)
    print(f"\nBattery:")
    print(f"  Capacity = {capacity}kWh")
    print(f"  Voltage = {bat_volt}v")
    print(f"  Min SoC on Grid = {min_soc}%")
    print(f"  Current SoC = {soc}%")
    print(f"  Residual = {residual}kWh")
    print(f"  Available = {available}kWh")
    # get charge power / export limit
    device_power = device.get('power')
    device_current = device.get('max_charge_current')
    if device_power is None or device_current is None:
        model = device.get('deviceType') if device.get('deviceType') is not None else 'deviceType?'
        print(f"** could not get parameters for {model}")
        device_power = 3.68
        device_current = 26
    # battery voltage when charging
    charge_volt = bat_volt * (1 + charge_config['volt_swing'] / 100 * (100 - soc) / 100) * charge_config['volt_overdrive']
    # charge power limit for inverter, after conversion losses
    charge_limit = round(device_power * charge_config['conversion_loss'], 1)
    # charge power if we are limited by charge current
    charge_power = round(charge_volt * (charge_current if charge_current is not None else device_current) / 1000, 1)
    # effective limit for charge power (InvBatVolt x InvBatCurrent)
    charge_limit = charge_power if charge_power < charge_limit else charge_limit
    # configure export limit
    export_limit = (device_power if export_power is None else export_power) / charge_config['conversion_loss']
    if debug_setting > 1:
        print(f"device_power = {device_power}, device_current = {device_current}")
        print(f"bat_volt = {bat_volt}, soc = {soc}, mid_volt = {mid_volt}, charge_current = {charge_current}, charge_power = {charge_power}")
        print(f"charge_limit = {charge_limit}, export_limit = {export_limit}")
    # get consumption data
    if annual_consumption is not None:
        consumption = round(annual_consumption / 365 * seasonality[now.month - 1] / sum(seasonality), 1)
        consumption_by_hour = daily_consumption
        print(f"\nEstimated consumption = {consumption}kWh")
        consumption = round(consumption * (1 + contingency / 100),1)
    else:
        consumption_days = charge_config['consumption_days']
        consumption_days = 3 if consumption_days > 7 or consumption_days < 1 else consumption_days
        consumption_span = charge_config['consumption_span']
        consumption_span = 'week' if consumption_span not in ['week', 'weekday'] else consumption_span
        history = get_report('day', d = date_list(span=consumption_span, today=1)[-consumption_days:], v='loads')
        (consumption, consumption_by_hour) = report_value_profile(history)
        print(f"\nConsumption (kWh):")
        s = ""
        for h in history:
            s += f"  {h['date']} = {h['total']:4.1f},"
        print(s[:-1])
        s = ""
        print(f"  Average of last {consumption_days} {consumption_span}s = {consumption}kWh")
    # factor in contingency on consumption
    consumption = round(consumption * (1 + contingency / 100),1)
    print(f"  With {contingency}% contingency = {consumption}kWh")
    # create time line for consumption
    daily_sum = sum(consumption_by_hour)
    consumption_timed = timed_list([round(consumption * x / daily_sum, 3) for x in consumption_by_hour], hour_now, run_time)
    # add contingency to consumption
    # get Solcast data
    solcast_value = None
    solcast_profile = None
    if solcast_api_key is not None and solcast_api_key != 'my.solcast_api_key':
        if hour_now >= run_after or hour_now >= charge_config['solcast']['start']:
            fsolcast = Solcast(quiet=True, estimated=0)
            if fsolcast is not None:
                (solcast_value, solcast_timed) = forecast_value_timed(fsolcast, today, tomorrow, hour_now, run_time)
                print(f"\nSolcast forecast: {solcast_value}kWh")
        else:
            print(f"\nSolcast forecast will run after {hours_time(charge_config['solcast']['start'])}")
    # get forecast.solar data
    solar_value = None
    solar_profile = None
    if solar_arrays is not None:
        if hour_now >= run_after or hour_now >= charge_config['solar']['start']:
            fsolar = Solar(quiet=True)
            if fsolar is not None:
                (solar_value, solar_timed) = forecast_value_timed(fsolar, today, tomorrow, hour_now, run_time)
                print(f"\nSolar forecast: {solar_value}kWh")
        else:
            print(f"\nSolar forecast will run after {hours_time(charge_config['solar']['start'])}")
    # get generation data
    history = get_raw('week', d=today, v=['pvPower','meterPower2'], summary=2)
    pv_history = {}
    for day in history:
        date = day['date']
        if pv_history.get(date) is None:
            pv_history[date] = 0.0
        pv_history[date] += round(day['kwh_neg'] / 0.92 if day['variable'] == 'meterPower2' else day['kwh'], 1)
    gen_days = charge_config['generation_days']
    pv_sum = sum([pv_history[d] for d in sorted(pv_history.keys())[-gen_days:]])
    print(f"\nGeneration (kWh):")
    s = ""
    for d in sorted(pv_history.keys()):
        s += f"  {d} = {pv_history[d]:4.1f},"
    print(s[:-1])
    generation = round(pv_sum / gen_days, 1)
    print(f"  Average of last {gen_days} days = {generation}kWh")
    # choose expected value
    quarter = now.month // 3 % 4
    sun_name = seasonal_sun[quarter]['name']
    sun_profile = seasonal_sun[quarter]['sun']
    sun_sum = sum(sun_profile)
    sun_timed = timed_list(sun_profile, hour_now, run_time)
    if forecast is not None:
        expected = forecast
        generation_timed = [round(expected * x / sun_sum, 3) for x in sun_timed]
        print(f"\nUsing manual forecast of {expected}kWh with {sun_name} sun profile")
    elif solcast_value is not None:
        expected = solcast_value
        generation_timed = solcast_timed
        print(f"\nUsing Solcast forecast of {expected}kWh")
    elif solar_value is not None:
        expected = solar_value
        generation_timed = solar_timed
        print(f"\nUsing Solar forecast of {expected}kWh")
    else:
        expected = generation
        generation_timed = [round(expected * x / sun_sum, 3) for x in sun_timed]
        print(f"\nUsing forecast generation of {expected}kWh with {sun_name} sun profile")
    # build profiles for charge and discharge (after losses)
    charge_timed = [round(x * charge_config['conversion_loss'], 3) for x in generation_timed]
    discharge_timed = [round(x / charge_config['conversion_loss'], 3) for x in consumption_timed]
    # adjust charge / discharge profile for work mode, force charge and inverter power limit
    for i in range(0, run_time):
        h = int(hour_now) + i
        if force_charge_am == 1 and hour_in(h, {'start': start_am, 'end': end_am}):
            discharge_timed[i] = 0.0
        elif force_charge_pm == 1 and hour_in(h, {'start': start_pm, 'end': end_pm}):
            discharge_timed[i] = 0.0
        elif timed_mode == 1 and tariff is not None and hour_in(h, tariff['backup']):
            discharge_timed[i] = 0.0
        elif timed_mode == 1 and tariff is not None and hour_in(h, tariff['feedin']):
            (discharge_timed[i], charge_timed[i]) = (0.0 if (charge_timed[i] >= discharge_timed[i]) else (discharge_timed[i] - charge_timed[i]),
            0.0 if (charge_timed[i] <= export_limit + discharge_timed[i]) else (charge_timed[i] - export_limit - discharge_timed[i]))
        # cap charge power
        charge_timed[i] = charge_limit if charge_timed[i] > charge_limit else charge_timed[i]
    # work out change in battery residual from charge / discharge
    kwh_timed = []
    for charge, discharge in zip(charge_timed, discharge_timed):
        kwh_timed.append(round(charge * charge_config['battery_loss'] - discharge - charge_config['operation_loss'], 3))
    if debug_setting > 1:
        print(f"\nGeneration timed: {generation_timed}")
        print(f"Charge timed: {charge_timed}")
        print(f"Consumption timed: {consumption_timed}")
        print(f"Discharge timed: {discharge_timed}")
        print(f"kWh timed: {kwh_timed}")
    # track the battery residual over the run time (if we don't add any charge)
    # adjust residual from hour_now what it was at the start of current hour
    h = int(hour_now)
    current_kwh = round(residual - kwh_timed[0] * (hour_now - h), 1)
    bat_timed = []
    min_kwh = current_kwh
    min_hour = None
    for kwh in kwh_timed:
        current_kwh = round(current_kwh, 1) if current_kwh <= capacity else capacity
        bat_timed.append(current_kwh)
        if current_kwh < min_kwh:       # track minimum and time
            min_kwh = current_kwh
            min_hour = h
        current_kwh += kwh
        h += 1
    if show_data > 0:
        s = f"\nBattery Energy kWh:\n" if show_data == 2 else f"\nBattery SoC:\n"
        s += "                 " * (int(hour_now) % 6)
        h = int(hour_now)
        for r in bat_timed:
            s += "\n" if h > 0 and h % 6 == 0 else ""
            if show_data == 2:
                s += f"  {hours_time(h, day=True)} = {r:4.1f},"
            else:
                s += f"  {hours_time(h, day=True)} = {int(r / capacity * 100):3}%,"
            h += 1
        print(s[:-1])
    if show_plot > 0:
        print()
        plt.figure(figsize=(figure_width, figure_width/2))
        x = [hours_time(int(hour_now) + i, day=True) for i in range(0, run_time)]
        if show_plot == 1:
            title = f"Battery SoC %"
            plt.plot(x, [int(bat_timed[i] * 100 / capacity) for i in range(0, run_time)], label='Battery', color='blue')
        else:
            title = f"Energy Flow kWh"
            plt.plot(x, bat_timed, label='Battery', color='blue')
            plt.plot(x, generation_timed, label='Generation', color='orange')
            plt.plot(x, consumption_timed, label='Consumption', color='red')
            if show_plot == 3:
                plt.plot(x, charge_timed, label='Charge', color='green')
                plt.plot(x, discharge_timed, label='Discharge', color='brown')
        plt.title(title, fontsize=12)
        plt.grid()
        if show_plot > 1:
            plt.legend()
        plt.xticks(rotation=90, ha='center', fontsize=8)
        plt.show()
    # work out what we need to add to the residual to stay above reserve
    kwh_needed = round(reserve - min_kwh, 1)
    if kwh_needed < charge_config['min_kwh']:
        print(f"\nLowest forecast SoC = {int(min_kwh / capacity * 100)}% at {hours_time(min_hour, day=True)} (Residual = {min_kwh}kWh)")
        print(f"  No charging needed")
        hours = 0.0
        start1 = start_at
        end1 = start1
    else:
        print(f"\nCharge needed = {kwh_needed}kWh")
        start_residual = bat_timed[time_to_next]
        if (start_residual + kwh_needed) > capacity:
            bigger_battery = round((start_residual + kwh_needed - reserve) / (100 - min_soc) * 100, 1)
            print(f"** can't add enough charge: you need a capacity of {bigger_battery}kWh")
            kwh_needed = capacity - start_residual
        # calculate charging time
        hours = round_time(kwh_needed / charge_limit / charge_config['battery_loss'])
        # don't charge for less than minimum time period
        if hours > 0.0 and hours < charge_config['min_hours']:
            hours = charge_config['min_hours']
        start1 = start_at
        end1 = round_time(start1 + hours)
        if end1 > end_by:
            print(f"** can't add enough charge: end time {hours_time(end1)} is later than {hours_time(end_by)}")
            end1 = end_by
            hours = round_time(end1 - start1)
        kwh_added = round(charge_limit * hours * charge_config['battery_loss'], 1)
        target_residual = round(start_residual + kwh_added, 1)
        target_residual = capacity if target_residual > capacity else target_residual
        target_soc = int(target_residual / capacity * 100)
        print(f"  Charge time = {hours_time(start_at)} - {hours_time(end_by)}{' (force charge)' if force_charge == 1 else ''}")
        print(f"  Charging for {int(hours * 60)} minutes with charge limit of {charge_limit}kW adds {kwh_added}kWh")
        print(f"  Target SoC = {target_soc}% at {hours_time(end1)} (Residual = {target_residual}kWh)")
        # work out charge periods settings
    if force_charge == 1:
        start2 = round_time(start1 if hours == 0 else end1 + 1 / 60)       # add 1 minute to end time
        start2 = end_by if start2 > end_by else start2
        end2 = end_by
    else:
        start2 = 0
        end2 = 0
    # setup charging
    if update_settings == 1:
        set_charge(ch1 = True, st1 = start1, en1 = end1, ch2 = False, st2 = start2, en2 = end2)
    else:
        print(f"\n** no changes have been made, update_settings=1 will set your battery charge times")
    return None

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
    first = datetime.date(datetime.strptime(s, '%Y-%m-%d')) if s is not None else None
    last = datetime.date(datetime.strptime(e, '%Y-%m-%d')) if e is not None else None
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
            # e.g. last 7 days with same day of the week
            last = first + timedelta(days=42) if first is not None else last
            first = last - timedelta(days=42) if first is None else first
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
    d = latest_date if first is None or first > latest_date else first
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

##################################################################################################
# get PV Output upload data from the Fox Cloud as energy values for a list of dates
##################################################################################################

# get pvoutput data for upload to pvoutput api or via Bulk Loader
# tou: 0 = no time of use, 1 = use time of use periods if available

def get_pvoutput(d = None, tou = 0):
    if d is None:
        d = date_list()[0]
    tou = 0 if (tou == 1 or tou == True) and tariff is None else tou
    tou = 1 if tou == 1 or tou == True else 0
    if type(d) is list:
        print(f"---------------- get_pvoutput ------------------")
        print(f"Date range {d[0]} to {d[-1]} has {len(d)} days")
        if tou == 1:
            print(f" Time of use: {tariff['name']}")
        print(f"------------------------------------------------")
        for x in d:
            csv = get_pvoutput(x)
            if csv is None:
                return None
            print(csv)
        return
    # get quick report of totals for the day
    v = ['loads'] if tou else ['loads', 'feedin', 'gridConsumption']
    report_data = [] if tou else get_report('day', d=d, v=v, summary=2)
    if report_data is None:
        return None
    # get raw power data for the day
    v = ['pvPower', 'meterPower2'] + (['feedinPower', 'gridConsumptionPower'] if tou else [])
    raw_data = get_raw('day', d=d + ' 00:00:00', v=v , summary=1)
    if raw_data is None:
        return None
    if raw_data[0].get('kwh') is None or raw_data[0].get('max') is None:
        return(f"# error: {d.replace('-','')} No generation data")
    # merge raw_data for meterPower2 into pvPower:
    pv_index = v.index('pvPower')
    ct2_index = v.index('meterPower2')
    for i, data in enumerate(raw_data[ct2_index]['data']):
        # meterPower2 is -ve when generating
        raw_data[pv_index]['data'][i]['value'] -= data['value'] / 0.92 if data['value'] <= 0.0 else 0
    # kwh is positive for generation
    raw_data[pv_index]['kwh'] += raw_data[ct2_index]['kwh'] / 0.92
    pv_max = max(data['value'] for data in raw_data[pv_index]['data'])
    max_index = [data['value'] for data in raw_data[pv_index]['data']].index(pv_max)
    raw_data[pv_index]['max'] = pv_max
    raw_data[pv_index]['max_time'] = raw_data[pv_index]['data'][max_index]['time'][11:16]
    # validation check: max_pv_power against max pvPower (including meterPower2)
    if pv_max > max_pv_power:
        return(f"# error: {d.replace('-','')} PV power ({pv_max}kWh) exceeds max_pv_power ({max_pv_power}kWh)")
    # generate output
    generate = ''
    export = ','
    power = ',,'
    export_tou = ',,,'
    consume = ','
    grid = ',,,,'
    for var in raw_data:     # process list of raw_data values (with TOU)
        wh = int(var['kwh'] * 1000)
        peak = int(var['kwh_peak'] * 1000)
        off_peak = int(var['kwh_off'] * 1000)
        if var['variable'] == 'pvPower':
            generation = wh
            date = var['date'].replace('-','')
            generate = f"{date},{generation},"
            power = f"{int(var['max'] * 1000)},{var['max_time']},"
        elif var['variable'] == 'feedinPower':
            export = f"{wh}," if tou == 0 else f","
            export_tou = f",,," if tou == 0 else f"{peak},{off_peak},{wh - peak - off_peak},0"
        elif var['variable'] == 'loadsPower':
            consume = f"{wh},"
        elif var['variable'] == 'gridConsumptionPower':
            grid = f"0,0,{wh},0," if tou == 0 else f"{peak},{off_peak},{wh - peak - off_peak},0,"
    for var in report_data:     # process list of report_data values (no TOU)
        wh = int(var['total'] * 1000)
        if var['variable'] == 'feedin':
            # check exported is less than generated
            if wh > generation:
                print(f"# warning: {date} Exported {wh}Wh is more than Generation")
                wh = generation
            export = f"{wh},"
            export_tou = f",,,"
        elif var['variable'] == 'loads':
            consume = f"{wh},"
        elif var['variable'] == 'gridConsumption':
            grid = f"0,0,{wh},0,"
    if generate == '':
        return None
    csv = generate + export + power + ',,,,' + grid + consume + export_tou
    return csv

pv_url = "https://pvoutput.org/service/r2/addoutput.jsp"
pv_api_key = None
pv_system_id = None

# upload data for a day using pvoutput api
def set_pvoutput(d = None, tou = 0):
    global pv_url, pv_api_key, pv_system_id
    if pv_api_key is None or pv_system_id is None or pv_api_key == 'my.pv_api_key' or pv_system_id == 'my.pv_system_id':
        print(f"** set_pvoutput: 'pv_api_key' / 'pv_system_id' not configured")
        return None
    if d is None:
        d = date_list(span='2days', today = 1)
    tou = 0 if (tou == 1 or tou == True) and tariff is None else tou
    tou = 1 if tou == 1 or tou == True else 0
    if type(d) is list:
        print(f"\n--------------- set_pvoutput -----------------")
        print(f"Date range {d[0]} to {d[-1]} has {len(d)} days")
        if tou == 1 :
            print(f"Time of use: {tariff['name']}\n")
        print(f"------------------------------------------------")
        for x in d[:10]:
            csv = set_pvoutput(x)
            if csv is None:
                return None
            print(f"{csv}  # uploaded OK")
        return
    headers = {'X-Pvoutput-Apikey': pv_api_key, 'X-Pvoutput-SystemId': pv_system_id, 'Content-Type': 'application/x-www-form-urlencoded'}
    csv = get_pvoutput(d, tou)
    if csv is None:
        return None
    if csv[0] == '#':
        return csv
    response = requests.post(url=pv_url, headers=headers, data='data=' + csv)
    result = response.status_code
    if result != 200:
        if result == 401:
            print(f"** access denied for pvoutput.org. Check 'pv_api_key' and 'pv_system_id' are correct")
            return None
        print(f"** set_pvoutput got response code: {result}")
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
    return int(i)

def c_float(n):
    # handle None in float conversion
    if n is None :
        return float(0)
    return float(n)

##################################################################################################
# Code for loading and displaying yield forecasts from Solcast.com.au.
##################################################################################################

# solcast settings
solcast_url = 'https://api.solcast.com.au/'
solcast_api_key = None
solcast_rids = []       # no longer used, rids loaded from solcast.com
solcast_save = 'solcast.txt'
page_width = 100        # maximum text string for display
figure_width = 9       # width of plots

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
                    print(f"Solcast: response code getting rooftop_sites was {response.status_code}")
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
                            print(f"Solcast: response code getting {t} was {response.status_code}")
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
                        hour = int(period_end[11:13])
                        if date not in self.daily.keys() :
                            self.daily[date] = {'hourly': {}, 'kwh': 0.0}
                        if hour not in self.daily[date]['hourly'].keys():
                            self.daily[date]['hourly'][hour] = 0.0
                        value = c_float(f.get('pv_estimate')) / 2                   # 30 minute power kw, yield / 2 = kwh
                        self.daily[date]['kwh'] = round(self.daily[date]['kwh'] + value, 3)
                        self.daily[date]['hourly'][hour] = round(self.daily[date]['hourly'][hour] + value, 3)
        # ignore first and last dates as these only cover part of the day, so are not accurate
        self.keys = sorted(self.daily.keys())[1:-1]
        self.days = len(self.keys)
        # trim the range if fewer days have been requested
        while self.days > 2 * days :
            self.keys = self.keys[1:-1]
            self.days = len(self.keys)
        self.values = [self.daily[d]['kwh'] for d in self.keys]
        self.total = round(sum(self.values),3)
        if self.days > 0 :
            self.avg = round(self.total / self.days, 3)
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
            s += f"\n   {d} {day}: {y:5.2f} kwh"
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
        if hasattr(self, 'avg'):
            plt.axhline(self.avg, color='blue', linestyle='solid', label=f'average {self.avg:.1f} kwh / day', linewidth=2)
        title = f"Solcast daily yield on {self.today} for {self.days} days"
        title += f". Total yield = {self.total:.0f} kwh, Average = {self.avg:.0f}"    
        plt.title(title, fontsize=12)
        plt.grid()
#        plt.legend(fontsize=14)
        plt.xticks(rotation=45, ha='right')
        plt.show()
        return

    def plot_hourly(self, day = None) :
        if not hasattr(self, 'daily') :
            print(f"Solcast: no daily data to plot")
            return
        if day == 'today':
            day = self.today
        elif day == 'tomorrow':
            day = self.tomorrow
        elif day is None:
            day = self.keys
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
        title = f"Solcast hourly yield on {day}"
        title += f". Total yield = {self.daily[day]['kwh']:.1f}kwh"    
        plt.title(title, fontsize=12)
        plt.grid()
        plt.xticks(rotation=45, ha='right')
        plt.show()
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
                        print(f"\nForecast.solar API call limit reached for today")
                    else:
                        print(f"** Solar() got response code: {response.status_code}")
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
                    self.daily[d]['kwh'] = round(self.daily[d]['kwh'] + whd[d] / 1000, 3)
            if self.results[k].get('watt_hours_period') is not None:
                whp = self.results[k]['watt_hours_period']
                for dt in whp.keys():
                    date = dt[:10]
                    hour = int(dt[11:13])
                    if hour not in self.daily[date]['hourly'].keys():
                        self.daily[date]['hourly'][hour] = 0.0
                    self.daily[date]['hourly'][hour] = round((self.daily[date]['hourly'][hour] + whp[dt]) / 1000, 3)
        # fill out hourly forecast to cover 24 hours
        for d in self.daily.keys():
            for h in range(0,24):
                if self.daily[d]['hourly'].get(h) is None:
                    self.daily[d]['hourly'][h] = 0.0
        # drop forecast for today as it already happened
        self.keys = sorted(self.daily.keys())
        self.days = len(self.keys)
        self.values = [self.daily[d]['kwh'] for d in self.keys]
        self.total = round(sum(self.values), 3)
        if self.days > 0:
            self.avg = round(self.total / self.days, 3)
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
            s += f"\n   {d} {day} : {y:5.2f} kwh"
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
#        plt.legend(fontsize=14)
        plt.xticks(rotation=45, ha='right')
        plt.show()
        return

    def plot_hourly(self, day = None) :
        if not hasattr(self, 'daily') :
            print(f"Solar: no daily data to plot")
            return
        if day == 'today':
            day = self.today
        elif day == 'tomorrow':
            day = self.tomorrow
        elif day is None:
            day = self.keys
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
        plt.show()
        return