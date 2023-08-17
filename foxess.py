##################################################################################################
"""
Module:   Fox ESS Cloud
Created:  3 June 2023
Updated:  17 August 2023
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

software_names = [SoftwareName.CHROME.value]
operating_systems = [OperatingSystem.WINDOWS.value, OperatingSystem.LINUX.value]
user_agent_rotator = UserAgent(software_names=software_names, operating_systems=operating_systems, limit=100)

# global settings and vars
debug_setting = 1

##################################################################################################
# Inverter information and settings
##################################################################################################

token = {'value': None, 'valid_from': None, 'valid_for': timedelta(hours=1).seconds, 'user_agent': None, 'lang': 'en'}

def query_date(d):
    if d is not None and len(d) < 18:
        d += ' 00:00:00'
    t = datetime.now() if d is None else datetime.strptime(d, "%Y-%m-%d %H:%M:%S")
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
        print(f"** login response code: {response.status_code}")
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
        print(f"** could not get a token")
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
        print(f"** could not get a token")
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
        print(f"** could not get a token")
        return None
    if device is not None:
        if sn is None:
            return device
        if device_sn[:len(sn)].upper() == sn.upper():
            return device
    if debug_setting > 1:
        print(f"getting device")
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
    device = device_list[n]
    device_id = device.get('deviceID')
    device_sn = device.get('deviceSN')
    firmware = None
    battery = None
    battery_settings = {}
    raw_vars = get_vars()
    return device

##################################################################################################
# get list of variables for selected device
##################################################################################################

def get_vars():
    global token, device_id, debug_setting
    if get_device() is None:
        print(f"** could not get a device")
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
        print(f"** could not get a device")
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
battery_settings = {}

def get_battery():
    global token, device_id, battery, debug_setting
    if get_device() is None:
        print(f"** could not get a device")
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
    if get_device is None:
        print(f"** could not get a device")
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
    battery_settings['times'] = times
    return battery_settings

##################################################################################################
# set charge times from battery
##################################################################################################

def set_charge():
    global token, device_sn, battery_settings, debug_setting
    if get_device() is None:
        print(f"** could not get a device")
        return None
    if battery_settings.get('times') is None:
        print(f"** no times to set")
        return None
    if debug_setting > 1:
        print(f"setting charge times")
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
        print(f"** could not get a device")
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
    battery_settings['minSoc'] = result.get('minSoc')
    battery_settings['minGridSoc'] = result.get('minGridSoc')
    return battery_settings

##################################################################################################
# set min soc from battery_settings
##################################################################################################

def set_min():
    global token, device_sn, bat_settings, debug_setting
    if get_device() is None:
        print(f"** could not get a device")
        return None
    if battery_settings.get('minGridSoc') is None or battery_settings.get('minSoc') is None:
        print(f"** no min soc settings")
        return None
    if debug_setting > 1:
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
    get_charge()
    get_min()
    return battery_settings

##################################################################################################
# get work mode
##################################################################################################

work_mode = None

def get_work_mode():
    global token, device_id, work_mode, debug_setting
    if get_device() is None:
        print(f"** could not get a device")
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
        print(f"** could not get a device")
        return None
    if mode not in work_modes:
        print(f"** work mode: must be one of {work_modes}")
        return None
    if debug_setting > 1:
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
        print(f"** could not get device")
        return None
    headers = {'token': token['value'], 'User-Agent': token['user_agent'], 'lang': token['lang'], 'Connection': 'keep-alive'}
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
        if energy ==2:
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
        print(f"** could not get device")
        return None
    headers = {'token': token['value'], 'User-Agent': token['user_agent'], 'lang': token['lang'], 'Connection': 'keep-alive'}
    if v is None:
        v = report_vars
    elif type(v) is not list:
        v = [v]
    if debug_setting > 1:
        print(f"getting report data")
    query = {'deviceID': device_id, 'reportType': report_type, 'variables': v, 'queryDate': query_date(d)}
    response = requests.post(url="https://www.foxesscloud.com/c/v0/device/history/report", headers=headers, data=json.dumps(query))
    if response.status_code != 200:
        print(f"** report data response code: {response.status_code}")
        return None
    result = response.json().get('result')
    if result is None:
        print(f"** no report data")
        return None
    for x in result:
        sum = 0.0
        for y in x['data']:
            sum += y['value']
        x['total'] = round(sum,3)
    return result

##################################################################################################
# get earnings data
##################################################################################################

def get_earnings():
    global token, device_id, var_list, debug_setting, report_vars
    if get_device() is None:
        print(f"** could not get device")
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
##################################################################################################
#
# PV Output Data Handling
#
##################################################################################################
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
    values = get_raw('day', d=d + ' 00:00:00', v = pvoutput_vars, energy=2)
    if values is None:
        return None
    result = ''
    generate = ''
    export = ','
    export2 = ',,,'
    consume = ','
    grid = ',,,,'
    for v in values:     # process values
        standard = int(v['kwh'] * 1000)
        peak = int(v['kwh_peak'] * 1000)
        off_peak = int(v['kwh_off'] * 1000)
        if v['variable'] == 'pvPower':
            generate = f"{v['date'].replace('-','')},{standard},"
        elif v['variable'] == 'feedinPower':
            export = f"{standard}," if tou == 0 else f","
            export2 = f",,," if tou == 0 else f"{peak},{off_peak},{standard - peak - off_peak},0"
        elif v['variable'] == 'loadsPower':
            consume = f"{standard},"
        elif v['variable'] == 'gridConsumptionPower':
            grid = f"0,0,{standard},0," if tou == 0 else f"{peak},{off_peak},{standard - peak - off_peak},0,"
    if generate != '':
        return generate + export + ',,,,,,' + grid + consume + export2
    return None

api_key = None
system_id = None

# set data for a day using pvoutput api
def set_pvoutput(d = None, tou = 1, today = False):
    global api_key, system_id, debug_setting
    if d is None:
        d = date_list(today = today)[0]
    if api_key is None or system_id is None or api_key == '<your api key>' or system_id == '<your system id>':
        print(f"** please enter your PV Output api_key and system_id")
        return None
    headers = {'X-Pvoutput-Apikey': api_key, 'X-Pvoutput-SystemId': system_id, 'Content-Type': 'application/x-www-form-urlencoded'}
    csv = get_pvoutput(d, tou)
    if csv is None:
        return None
    if debug_setting > 0:
        print(f"{csv}")
    response = requests.post(url="https://pvoutput.org/service/r2/addoutput.jsp", headers=headers, data='data=' + csv)
    result = response.status_code
    if result != 200:
        print(f"** put_pvoutput response code: {result}")
    return result
