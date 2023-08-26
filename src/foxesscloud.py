##################################################################################################
"""
Module:   Fox ESS Cloud
Version:  0.2.4
Created:  3 June 2023
Updated:  26 August 2023
By:       Tony Matthews
"""
##################################################################################################
# This is sample code for getting and setting inverter data via the Fox ESS cloud web site
##################################################################################################

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

# global settings and vars
debug_setting = 1

##################################################################################################
# Inverter information and settings
##################################################################################################

token = {'value': None, 'valid_from': None, 'valid_for': timedelta(hours=1).seconds, 'user_agent': None, 'lang': 'en'}

def query_date(d, offset = None):
    if d is not None and len(d) < 18:
        d += ' 00:00:00'
    t = datetime.now() if d is None else datetime.strptime(d, "%Y-%m-%d %H:%M:%S")
    if offset is not None:
        t += timedelta(days = offset)
    return {'year': t.year, 'month': t.month, 'day': t.day, 'hour': t.hour, 'minute': t.minute, 'second': t.second}

username = None
password = None

# login and get token if required. Check if token has expired and renew if required.
def get_token():
    global username, password, token, device_list, device, device_id, debug_setting
    time_now = datetime.now()
    if token['valid_from'] is not None:
        if (time_now - token['valid_from']).seconds <= token['valid_for']:
            if debug_setting > 1:
                print(f"token is still valid")
            return token['value']
    if debug_setting > 1:
        print(f"loading new token")
    device_list = None
    device = None
    token['user_agent'] = user_agent_rotator.get_random_user_agent()
    headers = {'User-Agent': token['user_agent'], 'lang': token['lang'], 'Connection': 'keep-alive'}
    if username is None or password is None:
        print(f"** please setup your Fox ESS Cloud username and password")
        return None
    credentials = {'user': username, 'password': hashlib.md5(password.encode()).hexdigest()}
    response = requests.post(url="https://www.foxesscloud.com/c/v0/user/login", headers=headers, data=json.dumps(credentials))
    if response.status_code != 200:
        print(f"** could not login to Fox ESS Cloud - response code: {response.status_code}")
        return None
    result = response.json().get('result')
    if result is None:
        print(f"** no login result data")
        return None
    token['value'] = result.get('token')
    if token['value'] is None:
        print(f"** no token  in result data")
    token['valid_from'] = time_now
    return token['value']

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
        print(f"** sites list response code: {response.status_code}")
        return None
    result = response.json().get('result')
    if result is None:
        print(f"** no site list result data")
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
            print(f"** please pick a name from the list")
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
        print(f"** logger list response code: {response.status_code}")
        return None
    result = response.json().get('result')
    if result is None:
        print(f"** no logger list result data")
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
            print(f"** please pick a serial number from the list")
            for l in logger_list:
                print(f"SN={l['moduleSN']}, Plant={l['plantName']}, StationID={l['stationID']}")
            return None
    else:
        n = 0
    logger = logger_list[n]
    return logger


##################################################################################################
# get list of available devices and select one, using the serial number if there is more than 1
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
    # get device list
    headers = {'token': token['value'], 'User-Agent': token['user_agent'], 'lang': token['lang'], 'Connection': 'keep-alive'}
    query = {'pageSize': 100, 'currentPage': 1, 'total': 0, 'queryDate': {'begin': 0, 'end':0} }
    response = requests.post(url="https://www.foxesscloud.com/c/v0/device/list", headers=headers, data=json.dumps(query))
    if response.status_code != 200:
        print(f"** device list response code: {response.status_code}")
        return None
    result = response.json().get('result')
    if result is None:
        print(f"** no device list result data")
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
            print(f"** please pick a serial number from this list")
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
    model_code = device['deviceType'].replace('-','').upper()
    # first 2 letters / numbers e.g. H1, H3, KH
    model = model_code[:2]
    if model not in ['H1', 'H3', 'KH']:
        model = model_code[:3]
        if  model not in ['AC1', 'AC3']:
            model = model_code[:5]
            if model not in ['AIOH1', 'AIOH3']:
                print(f"** device model not recognised: {device['deviceType']}")
                return device
    device['model'] = model
    device['phase'] = 3 if model[-1:] == '3' else 1
    eps = model_code[-1:] == 'E'
    device['eps'] = eps
    power = model_code.replace(model,'').replace('E', '')
    if power.replace('.','').isnumeric():
        device['power'] = float(power)
    return device

##################################################################################################
# get list of variables for selected device
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
        print(f"** variables response code: {response.status_code}")
        return None
    result = response.json().get('result')
    if result is None:
        print(f"** no variables result")
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
        print(f"** firmware response code: {response.status_code}")
        return None
    result = response.json().get('result')
    if result is None:
        print(f"** no firmware result data")
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
        print(f"** battery response code: {response.status_code}")
        return None
    result = response.json().get('result')
    if result is None:
        print(f"** no battery info")
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
        print(f"** get charge response code: {response.status_code}")
        return None
    result = response.json().get('result')
    if result is None:
        print(f"** no charge result data")
        return None
    times = result.get('times')
    if times is None:
        print(f"** no times data")
        return None
    if battery_settings is None:
        battery_settings = {}
    battery_settings['times'] = times
    return battery_settings

# helper to format time period structures
def time_period(t):
    result = f"{t['startTime']['hour']:02d}:{t['startTime']['minute']:02d} - {t['endTime']['hour']:02d}:{t['endTime']['minute']:02d}"
    if t['enableGrid']:
        result += f" Charge from grid"
    return result


##################################################################################################
# set charge times from battery
##################################################################################################

def set_charge(ch1 = None, st1 = None, en1 = None, ch2 = None, st2 = None, en2 = None):
    global token, device_sn, battery_settings, debug_setting
    if get_device() is None:
        return None
    if battery_settings.get('times') is None:
        print(f"** invalid battery settings")
        return None
    # configure time period 1
    if st1 is not None:
        if st1 == en1:
            st1 = 0
            en1 = 0
            ch1 = False
        battery_settings['times'][0]['enableCharge'] = True
        battery_settings['times'][0]['enableGrid'] = ch1
        battery_settings['times'][0]['startTime']['hour'] = int(st1)
        battery_settings['times'][0]['startTime']['minute'] = int(60 * (st1 - int(st1)))
        battery_settings['times'][0]['endTime']['hour'] = int(en1)
        battery_settings['times'][0]['endTime']['minute'] = int(60 * (en1 - int(en1)))
    # configure time period 2
    if st2 is not None:
        if st2 == en2:
            st2 = 0
            en2 = 0
            ch2 = False
        battery_settings['times'][1]['enableCharge'] = True
        battery_settings['times'][1]['enableGrid'] = ch2
        battery_settings['times'][1]['startTime']['hour'] = int(st2)
        battery_settings['times'][1]['startTime']['minute'] = int(60 * (st2 - int(st2)))
        battery_settings['times'][1]['endTime']['hour'] = int(en2)
        battery_settings['times'][1]['endTime']['minute'] = int(60 * (en2 - int(en2)))
    if debug_setting > 1:
        print(battery_settings)
        return None
    if debug_setting > 0:
        print(f"Setting time periods:")
        print(f"   Time Period 1 = {time_period(battery_settings['times'][0])}")
        print(f"   Time Period 2 = {time_period(battery_settings['times'][1])}")
    # set charge times
    headers = {'token': token['value'], 'User-Agent': token['user_agent'], 'lang': token['lang'], 'Connection': 'keep-alive'}
    data = {'sn': device_sn, 'times': battery_settings.get('times')}
    response = requests.post(url="https://www.foxesscloud.com/c/v0/device/battery/time/set", headers=headers, data=json.dumps(data))
    if response.status_code != 200:
        print(f"** set charge response code: {response.status_code}")
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
        print(f"** get min soc response code: {response.status_code}")
        return None
    result = response.json().get('result')
    if result is None:
        print(f"** no min soc result data")
        return None
    if battery_settings is None:
        battery_settings = {}
    battery_settings['minSoc'] = result.get('minSoc')
    battery_settings['minGridSoc'] = result.get('minGridSoc')
    return battery_settings

##################################################################################################
# set min soc from battery_settings
##################################################################################################

def set_min(minGridSoc = None, minSoc = None):
    global token, device_sn, bat_settings, debug_setting
    if get_device() is None:
        return None
    if battery_settings.get('minGridSoc') is None or battery_settings.get('minSoc') is None:
        print(f"** no min soc settings")
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
        print(f"** set min response code: {response.status_code}")
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
        print(f"** get work mode response code: {response.status_code}")
        return None
    result = response.json().get('result')
    if result is None:
        print(f"** no work mode result data")
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
        print(f"** set work mode response code: {response.status_code}")
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
# returns a list of variables and their values / attributes
# energy determines operating mode - 0: raw data, 1: estimate kwh, 2: estimate kwh and drop raw data
##################################################################################################

# generationPower must be first
power_vars = ['generationPower', 'feedinPower','loadsPower','gridConsumptionPower','batChargePower', 'batDischargePower', 'pvPower']
# corresponding names to use after integration to kWh, input is extra and must be last
energy_vars = ['output_daily', 'feedin_daily', 'load_daily', 'grid_daily', 'bat_charge_daily', 'bat_discharge_daily', 'pv_energy_daily', 'input_daily']

# convert time to fractional hours
def frac_hour(s):
    return sum(float(t) / x for x, t in zip([1, 60, 3600], s.split(":")))

# time periods settings for TOU allocation.
off_peak1 = {'start': 2.0, 'end': 5.0}
off_peak2 = {'start': 0.0, 'end': 0.0}
peak = {'start': 16.0, 'end': 19.0 }

def get_raw(time_span = 'hour', d = None, v = None, energy = 0):
    global token, device_id, debug_setting, raw_vars, off_peak1, off_peak2, peak
    if get_device() is None:
        return None
    headers = {'token': token['value'], 'User-Agent': token['user_agent'], 'lang': token['lang'], 'Connection': 'keep-alive'}
    if d is None:
        d = datetime.strftime(datetime.now() - timedelta(days=1), "%Y-%m-%d")
    if v is None:
        if raw_vars is None:
            raw_vars = get_vars()
        v = [x['variable'] for x in raw_vars]
    elif type(v) is not list:
        v = [v]
    if debug_setting > 1:
        print(f"getting raw data")
    query = {'deviceID': device_id, 'variables': v, 'timespan': time_span, 'beginDate': query_date(d)}
    response = requests.post(url="https://www.foxesscloud.com/c/v0/device/history/raw", headers=headers, data=json.dumps(query))
    if response.status_code != 200:
        print(f"** raw data response code: {response.status_code}")
        return None
    result = response.json().get('result')
    if result is None:
        print(f"** no raw data")
        return None
    # integrate kW to kWh based on 5 minute samples
    if energy == 0:
        return result
    if debug_setting > 1:
        print(f"estimating kwh from raw data")
    # copy generationPower to produce inputPower data
    generation_name = power_vars[0]
    input_name = None
    if generation_name in v:
        input_name = energy_vars[-1]
        input_result = deepcopy(result[v.index(generation_name)])
        input_result['name'] = input_name
        for y in input_result['data']:
            y['value'] = -y['value'] if y['value'] < 0.0 else 0.0
        result.append(input_result)
    for x in [x for x in result if x['unit'] == 'kW']:
        d = None
        kwh = 0.0       # kwh total
        kwh_off = 0.0   # kwh during off peak time (02:00-05:00)
        kwh_peak = 0.0  # kwh during peak time (16:00-19:00)
        hour = 0
        x['date'] = x['data'][0]['time'][0:10]
        x['state'] = []
        for y in x['data']:
            h = frac_hour(y['time'][11:19]) # time
            z = y['value'] / 12             # 12 x 5 minute samples = 1 hour
            if z >= 0.0:
                kwh += z
                if h >= off_peak1['start'] and h < off_peak1['end']:
                    kwh_off += z
                elif h >= off_peak2['start'] and h < off_peak2['end']:
                    kwh_off += z
                elif h >= peak['start'] and h < peak['end']:
                    kwh_peak += z
            else:
                y['value'] = 0.0            # remove ignored values
            if h > hour:    # new hour
                x['state'].append(round(kwh,3))
                hour = h
        x['kwh'] = round(kwh,3)
        x['kwh_off'] = round(kwh_off,3)
        x['kwh_peak'] = round(kwh_peak,3)
        x['state'].append(round(kwh,3))
        if energy == 2:
            if input_name is None or x['name'] != input_name:
                x['name'] = energy_vars[power_vars.index(x['variable'])]
            x['unit'] = 'kWh'
            del x['data']
    return result

##################################################################################################
# get energy report data in kWh
##################################################################################################

report_vars = ['generation', 'feedin', 'loads', 'gridConsumption', 'chargeEnergyToTal', 'dischargeEnergyToTal']

def get_report(report_type = 'day', d = None, v = None ):
    global token, device_id, var_list, debug_setting, report_vars
    if get_device() is None:
        return None
    headers = {'token': token['value'], 'User-Agent': token['user_agent'], 'lang': token['lang'], 'Connection': 'keep-alive'}
    if d is None:
        d = datetime.strftime(datetime.now() - timedelta(days=1), "%Y-%m-%d")
    if v is None:
        v = report_vars
    elif type(v) is not list:
        v = [v]
    if debug_setting > 1:
        print(f"getting report data")
    current = query_date(None)
    first = query_date(d)
    last_result = None
    if report_type == 'week':
        last = query_date(d, -7)
        if first['month'] != last['month']:
            # overlapping months in week, get last months data
            query = {'deviceID': device_id, 'reportType': 'month', 'variables': v, 'queryDate': last}
            response = requests.post(url="https://www.foxesscloud.com/c/v0/device/history/report", headers=headers, data=json.dumps(query))
            if response.status_code != 200:
                print(f"** report data response code: {response.status_code}")
                return None
            last_result = response.json().get('result')
            if last_result is None:
                print(f"** no report data for last month")
                return None
            # prune results for last month to just the days required
            for v in last_result:
                v['data'] = v['data'][int(last['day']):]
    query = {'deviceID': device_id, 'reportType': report_type.replace('week', 'month'), 'variables': v, 'queryDate': first}
    response = requests.post(url="https://www.foxesscloud.com/c/v0/device/history/report", headers=headers, data=json.dumps(query))
    if response.status_code != 200:
        print(f"** report data response code: {response.status_code}")
        return None
    result = response.json().get('result')
    if result is None:
        print(f"** no report data")
        return None
    # prune results back to only valid, complete data for day, week, month or year
    if report_type == 'day' and first['year'] == current['year'] and first['month'] == current['month'] and first['day'] == current['day']:
        for v in result:
            # prune current day to hours that are valid
            v['data'] = v['data'][:int(current['hour'])]
    if report_type == 'week':
        for v in range(len(result)):
            # prune results to days required
            result[v]['data'] = result[v]['data'][:int(first['day'])]
            if last_result is not None:
                # prepend last months results if required
                result[v]['data'] = last_result[v]['data'] + result[v]['data']
            # prune to week required
            result[v]['data'] = result[v]['data'][-7:]
    elif report_type == 'month' and first['year'] == current['year'] and first['month'] == current['month']:
        for v in result:
            # prune current month to days that are valid
            v['data'] = v['data'][:int(current['day'])]
    elif report_type == 'year' and first['year'] == current['year']:
        for v in result:
            # prune current year to months that are valid
            v['data'] = v['data'][:int(current['month'])]
    # calculate and add summary data
    for v in result:
        sum = 0.0
        count = 0
        for y in v['data']:
            sum += y['value']
            count += 1
        v['total'] = round(sum,3)
        v['average'] = round(sum / count, 3) if count > 0 else None
        v['date'] = d
        v['count'] = count
    return result


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
        print(f"** earnings data response code: {response.status_code}")
        return None
    result = response.json().get('result')
    if result is None:
        print(f"** no earnings data")
        return None
    return result


##################################################################################################
# calculate charge needed from current battery charge, forecast yield and expected load
##################################################################################################

# roll over 24 hours times and round times to 1 minute for time in decimal hours
def round_time(h):
    if h > 24:
        h -= 24
    return int(h) + round(60 * (h - int(h)), 0) / 60

# how consumption varies by month across a year. Total of all 12 values must be 12.0
seasonality = [1.1, 1.1, 1.0, 1.0, 0.9, 0.9, 0.9, 0.9, 1.0, 1.0, 1.1, 1.1]

# work out the charge times to set using the parameters:
#  forecast: the kWh expected tomorrow. If none, forecast data is loaded from solcast
#  annual_consumption: the kWh consumed each year via the inverter
#  contingency: a factor to add to allow for variations. 1.0 is no variation. Default is 1.25
#  charge_power: the kW of charge that will be applied
#  start_at: time in hours when charging will start e.g. 1:30 = 1.5 hours
#  end_by: time in hours when charging will stop
#  force_charge: if True, the remainder of the time, force charge is set. If false, force charge is not set
#  run_after: the time in hours when calculation should take place. The default is 20 or 8pm.
#  efficiency: inverter conversion factor from PV power or AC power to charge power. The default is 0.95 (95%)

def charge_needed(forecast = None, annual_consumption = None, contingency = 1.25, charge_power = None, start_at = 2.0, end_by = 5.0, force_charge = False, run_after = 20, efficiency = 0.95):
    global device, seasonality, debug_setting
    now = datetime.now()
    if now.hour < run_after:
        print(f"{datetime.strftime(now, '%H:%M')}, not time yet, run_after = {run_after}")
        return None
    tomorrow = datetime.strftime(now + timedelta(days=1), '%Y-%m-%d')
    # get battery info
    get_settings()
    get_battery()
    min = battery_settings['minGridSoc']
    soc = battery['soc']
    residual = round(battery['residual']/1000, 3)
    capacity = round(residual * 100 / soc if soc > 0 else residual, 3)
    reserve = round(capacity * min / 100, 3)
    available = round(residual - reserve, 3)
    if debug_setting > 0:
        print(f"Battery")
        print(f"   Capacity = {capacity}kWh")
        print(f"   Min SoC on Grid = {min}%")
        print(f"   Current SoC = {soc}%")
        print(f"   Residual = {residual}kWh")
        print(f"   Available energy = {available}kWh")
    # get forecast info
    if forecast is not None:
        expected = round(forecast,3)
    else:
        forecast = Solcast(days=2)
        if forecast is None:
            return None
        expected = round(forecast.daily[tomorrow]['kwh'] if forecast is not None else 0, 3)
    if debug_setting > 0:
        print(f"Forecast PV generation tomorrow = {expected}kWh")
    # get consumption info
    if annual_consumption is not None:
        consumption = round(annual_consumption / 365 * seasonality[now.month - 1], 3)
    else:
        consumption = get_report('week', v='loads')[0]['average']
        if consumption is None or consumption <= 0:
            print(f"** unable to get your average weekly consumption. Please provide your annual consumption")
            return None
    if debug_setting > 0:
        print(f"Estimated consumption tomorrow = {consumption}kWh")
    # calculate charge to add to battery
    charge = round((consumption - available - expected * efficiency) * contingency,3)
    if charge < 0.0:
        charge = 0.0
    if debug_setting > 0:
        print(f"Charge needed is {charge}kWh")
    if (residual + charge) > capacity:
        print(f"** charge needed exceeds battery capacity by {charge - capacity + residual}kWh")
    # calculate charge time
    if charge_power is None or charge_power <= 0:
        charge_power = device.get('power')
        if charge_power is None:
            charge_power = 3.7
    hours = round_time(charge / charge_power / efficiency)
    # don't charge for less than 15 minutes
    if hours > 0 and hours < 0.25:
        hours = 0.25
    if debug_setting > 0:
        print(f"  Charge time is {hours} hours using {charge_power}kW charge power")
    # work out charge periods settings
    start1 = start_at
    end1 = round_time(start1 + hours)
    if end1 > end_by:
        print(f"** charge end time {end1} exceeds end by {end_by}")
        end1 = end_by
    if force_charge:
        start2 = round_time(end1 + 1 / 60)
        start2 = end_by if start2 > end_by else start2
        end2 = end_by
    else:
        start2 = 0
        end2 = 0
    # setup charging
    set_charge(ch1 = True, st1 = start1, en1 = end1, ch2 = False, st2 = start2, en2 = end2)
    return None



##################################################################################################
# PV Output
##################################################################################################

# generate a list of up to 200 dates, where the last date is not later than yeterday or today

def date_list(s = None, e = None, limit = None, today = False):
    global debug_setting
    latest_date = datetime.date(datetime.now())
    if not today:
        latest_date -= timedelta(days=1)
    d = datetime.date(datetime.strptime(s, '%Y-%m-%d')) if s is not None else latest_date
    if d > latest_date:
        d = lastest_date
    l = [datetime.strftime(d, '%Y-%m-%d')]
    if s is None:
        return l
    last = datetime.date(datetime.strptime(e, '%Y-%m-%d')) if e is not None else latest_date
    limit = 200 if limit is None or limit < 1 else limit
    while d < last and d < latest_date and len(l) < limit:
        d += timedelta(days=1)
        l.append(datetime.strftime(d, '%Y-%m-%d'))
    if debug_setting > 0 and len(l) > 1:
        print(f"Date range from {l[0]} to {l[-1]} has {len(l)} days")
    return l

##################################################################################################
# get PV Output upload data from the Fox Cloud as energy values for a list of dates
##################################################################################################

pvoutput_vars = ['pvPower', 'feedinPower', 'loadsPower', 'gridConsumptionPower']

# get pvoutput data for upload to pvoutput api or via Bulk Loader.

def get_pvoutput(d = None, tou = 1):
    global debug_setting
    if d is None:
        d = date_list()[0]
    # get power information for day
    values = get_raw('day', d=d + ' 00:00:00', v = pvoutput_vars, energy=2)
    if values is None:
        return None
    generate = ''
    export = ','
    export_tou = ',,,'
    consume = ','
    grid = ',,,,'
    for v in values:     # process list of power / energy values
        standard = int(v['kwh'] * 1000)
        peak = int(v['kwh_peak'] * 1000)
        off_peak = int(v['kwh_off'] * 1000)
        if v['variable'] == 'pvPower':
            generate = f"{v['date'].replace('-','')},{standard},"
        elif v['variable'] == 'feedinPower':
            export = f"{standard}," if tou == 0 else f","
            export_tou = f",,," if tou == 0 else f"{peak},{off_peak},{standard - peak - off_peak},0"
        elif v['variable'] == 'loadsPower':
            consume = f"{standard},"
        elif v['variable'] == 'gridConsumptionPower':
            grid = f"0,0,{standard},0," if tou == 0 else f"{peak},{off_peak},{standard - peak - off_peak},0,"
    if generate == '':
        return None
    return generate + export + ',,,,,,' + grid + consume + export_tou

pv_url = "https://pvoutput.org/service/r2/addoutput.jsp"
pv_api_key = None
pv_system_id = None

# set data for a day using pvoutput api
def set_pvoutput(d = None, tou = 1, today = False):
    global pv_url, pv_api_key, pv_system_id, debug_setting
    if d is None:
        d = date_list(today = today)[0]
    if pv_api_key is None or pv_system_id is None or pv_api_key == '<your api key>' or pv_system_id == '<your system id>':
        print(f"** please enter your PV Output api_key and system_id")
        return None
    headers = {'X-Pvoutput-Apikey': pv_api_key, 'X-Pvoutput-SystemId': pv_system_id, 'Content-Type': 'application/x-www-form-urlencoded'}
    csv = get_pvoutput(d, tou)
    if csv is None:
        return None
    if debug_setting > 0:
        print(f"{csv}")
    response = requests.post(url=pv_url, headers=headers, data='data=' + csv)
    result = response.status_code
    if result != 200:
        print(f"** put_pvoutput response code: {result}")
    return result


##################################################################################################
# Solar forecast using solcast.com.au
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

# solcast settings
solcast_url = 'https://api.solcast.com.au/'
solcast_api_key = None
solcast_rids = []
solcast_save = 'solcast.json'
solcast_cal = 1.0
page_width = 100        # maximum text string for display
figure_width = 24       # width of plots

# This is the code used for loading and displaying yield forecasts from Solcast.com.au.

class Solcast :
    """
    Load Solcast Estimate / Actuals / Forecast daily yield
    """ 

    def __init__(self, days = 7, reload = 2) :
        # days sets the number of days to get for forecasts and estimated.
        # The forecasts and estimated both include the current date, so the total number of days covered is 2 * days - 1.
        # The forecasts and estimated also both include the current time, so the data has to be de-duplicated to get an accurate total for a day
        global debug_setting, solcast_url, solcast_api_key, solcast_rids, solcast_save, solcast_cal
        if solcast_api_key is None:
            print(f"** no api key provided")
            return None
        self.credentials = HTTPBasicAuth(solcast_api_key, '')
        if solcast_rids is None:
            print(f"** no rids provided")
            return None
        data_sets = ['forecasts', 'estimated_actuals']
        self.data = {}
        self.today =datetime.strftime(datetime.date(datetime.now()), '%Y-%m-%d')
        if reload == 1 and os.path.exists(solcast_save):
            os.remove(solcast_save)
        if solcast_save is not None and os.path.exists(solcast_save):
            f = open(solcast_save)
            self.data = json.load(f)
            f.close()
            if len(self.data) == 0:
                print(f"No data in {solcast_save}")
            elif reload == 2 and 'date' in self.data and self.data['date'] != self.today:
                self.data = {}
            elif debug_setting > 0:
                print(f"Using data for {self.data['date']} from {solcast_save}")
        if len(self.data) == 0 :
            if debug_setting > 0:
                print(f"Loading data from solcast.com.au for {self.today}")
            self.data['date'] = self.today
            params = {'format' : 'json', 'hours' : 168, 'period' : 'PT30M'}     # always get 168 x 30 min values
            for t in data_sets :
                self.data[t] = {}
                for rid in solcast_rids :
                    response = requests.get(solcast_url + 'rooftop_sites/' + rid + '/' + t, auth = self.credentials, params = params)
                    if response.status_code != 200 :
                        print(f"** response code getting {t} for {rid} from {response.url} was {response.status_code}")
                        return
                    self.data[t][rid] = response.json().get(t)
            if solcast_save is not None :
                f = open(solcast_save, 'w')
                json.dump(self.data, f, sort_keys = True, indent=4, ensure_ascii= False)
                f.close()
        self.daily = {}
        self.rids = []
        for t in data_sets :
            for rid in self.data[t].keys() :            # aggregate sites
                if self.data[t][rid] is not None :
                    self.rids.append(rid)
                    for f in self.data[t][rid] :            # aggregate 30 minute slots for each day
                        period_end = f.get('period_end')
                        date = period_end[:10]
                        time = period_end[11:16]
                        if date not in self.daily.keys() :
                            self.daily[date] = {'forecast' : t == 'forecasts', 'kwh' : 0.0}
                        if rid not in self.daily[date].keys() :
                            self.daily[date][rid] = []
                        if time not in self.daily[date][rid] :
                            self.daily[date]['kwh'] += c_float(f.get('pv_estimate')) / 2      # 30 minute kw yield / 2 = kwh
                            self.daily[date][rid].append(time)
                        elif debug_setting > 1 :
                                print(f"** overlapping data was ignored for {rid} in {t} at {date} {time}")
        # ignore first and last dates as these are forecast and estimates only cover part of the day, so are not accurate
        self.keys = sorted(self.daily.keys())[1:-1]
        self.days = len(self.keys)
        # trim the range if fewer days have been requested
        while self.days > 2 * days :
            self.keys = self.keys[1:-1]
            self.days = len(self.keys)
        self.values = [self.daily[k]['kwh'] for k in self.keys]
        self.total = sum(self.values)
        if self.days > 0 :
            self.avg = self.total / self.days
        self.cal = solcast_cal
        return

    def __str__(self) :
        # return printable Solcast info
        global debug_setting
        s = f'Solcast yield for {self.days} days'
        if self.cal is not None and self.cal != 1.0 :
            s += f", calibration = {self.cal}"
        s += f" (E = estimated, F = forecasts):\n\n"
        for k in self.keys :
            tag = 'F' if self.daily[k]['forecast'] else 'E'
            y = self.daily[k]['kwh'] * self.cal
            d = datetime.datetime.strptime(k, '%Y-%m-%d').strftime('%A')[:3]
            s += "\033[1m--> " if k == self.today else "    "
            s += f"{k} {d} {tag}: {y:5.2f} kwh"
            s += "\033[0m\n" if k == self.today else "\n"
            for r in self.rids :
                n = len(self.daily[k][r])
                if n != 48 and debug_setting > 0:
                    print(f" ** {k} rid {r} should have 48 x 30 min values. {n} values found")
        return s

    def plot_daily(self) :
        if not hasattr(self, 'daily') :
            print(f"** no daily data available")
            return
        figwidth = 12 * self.days / 7
        self.figsize = (figwidth, figwidth/3)     # size of charts
        plt.figure(figsize=self.figsize)
        # plot estimated
        x = [f"{k} {datetime.datetime.strptime(k, '%Y-%m-%d').strftime('%A')[:3]} " for k in self.keys if not self.daily[k]['forecast']]
        y = [self.daily[k]['kwh'] * self.cal for k in self.keys if not self.daily[k]['forecast']]
        if x is not None and len(x) != 0 :
            plt.bar(x, y, color='orange', linestyle='solid', label='estimated', linewidth=2)
        # plot forecasts
        x = [f"{k} {datetime.datetime.strptime(k, '%Y-%m-%d').strftime('%A')[:3]} " for k in self.keys if self.daily[k]['forecast']]
        y = [self.daily[k]['kwh'] * self.cal for k in self.keys if self.daily[k]['forecast']]
        if x is not None and len(x) != 0 :
            plt.bar(x, y, color='green', linestyle='solid', label='forecast', linewidth=2)
        # annotations
        if hasattr(self, 'avg') :
            plt.axhline(self.avg, color='blue', linestyle='solid', label=f'average {self.avg:.1f} kwh / day', linewidth=2)
        title = f"Solcast yield on {self.today} for {self.days} days"
        if self.cal != 1.0 :
            title += f" (calibration = {self.cal})"
        title += f". Total yield = {self.total:.0f} kwh"    
        plt.title(title, fontsize=16)
        plt.grid()
        plt.legend(fontsize=14)
        plt.xticks(rotation=45, ha='right')
        plt.show()
        return
