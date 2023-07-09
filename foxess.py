##################################################################################################
"""
Module:   Fox ESS Cloud
Created:  3 June 2023
Updated:  9 July 2023
By:       Tony Matthews
"""
##################################################################################################
# This is sample code for getting and setting inverter data via the Fox ESS cloud web site
##################################################################################################

import os.path
import json
import datetime
import requests
from requests.auth import HTTPBasicAuth
import hashlib
from random_user_agent.user_agent import UserAgent
from random_user_agent.params import SoftwareName, OperatingSystem
import private

software_names = [SoftwareName.CHROME.value]
operating_systems = [OperatingSystem.WINDOWS.value, OperatingSystem.LINUX.value]
user_agent_rotator = UserAgent(software_names=software_names, operating_systems=operating_systems, limit=100)

# global settings and vars
debug_setting = 1

token = {'value': None, 'valid_from': None, 'valid_for': datetime.timedelta(hours=4).seconds, 'user_agent': None}

def query_date(d):
    t = datetime.datetime.now() if d is None else datetime.datetime.strptime(d, "%Y-%m-%d %H:%M:%S")
    return {'year': t.year, 'month': t.month, 'day': t.day, 'hour': t.hour, 'minute': t.minute, 'second': t.second}

# login and get token if required. Check if token has expired and renew if required.
def get_token():
    global username, password, token, device_list, device, device_id
    time_now = datetime.datetime.now()
    if token['valid_from'] is not None:
        if (time_now - token['valid_from']).seconds <= token['valid_for']:
            if debug_setting > 1:
                print(f"token is still valid")
            return token['value']
    if debug_setting > 0:
        print(f"loading new token")
    device_list = None
    device = None
    token['user_agent'] = user_agent_rotator.get_random_user_agent()
    headers = {'User-Agent': token['user_agent'], 'lang': 'en', 'Connection': 'keep-alive'}
    credentials = {'user': private.username, 'password': hashlib.md5(private.password.encode()).hexdigest()}
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

device_list = None
device = None
device_id = None
device_sn = None
raw_vars = None

# get list of available devices and select one
def get_device(n=None):
    global token, device_list, device, device_id, device_sn, firmware, battery, raw_vars
    if get_token() is None:
        print(f"** could not get a token")
        return None
    if device is not None:
        return device
    if debug_setting > 0:
        print(f"getting device")
    headers = {'token': token['value'], 'User-Agent': token['user_agent'], 'lang': 'en', 'Connection': 'keep-alive'}
    query = {'pageSize': 100, 'currentPage': 1, 'total': 0, 'queryDate': {'begin': 0, 'end':0} }
    response = requests.post(url="https://www.foxesscloud.com/c/v0/device/list", headers=headers, data=json.dumps(query))
    if response.status_code != 200:
        print(f"** list response code: {response.status_code}")
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
    total = len(device_list)
    if (n is None and total > 1) or (n is not None and n > total):
        print(f"** {total} devices were found")
        for d in device_list:
            print(f"SN={d['deviceSN']}, Type={d['deviceType']}, ID={d['deviceID']} ")
        return None
    device = device_list[0 if n is None else n]
    device_id = device.get('deviceID')
    device_sn = device.get('deviceSN')
    firmware = None
    battery = None
    battery_settings = {}
    raw_vars = get_vars()
    return device


# get list of variables for selected device
def get_vars():
    global token, device_id
    if get_device() is None:
        print(f"** could not get a device")
        return None
    if debug_setting > 0:
        print(f"getting variables")
    headers = {'token': token['value'], 'User-Agent': token['user_agent'], 'lang': 'en', 'Connection': 'keep-alive'}
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


firmware = None

# get current firmware versions for selected device
def get_firmware():
    global token, device_id, firmware
    if get_device() is None:
        print(f"** could not get a device")
        return None
    if debug_setting > 0:
        print(f"getting firmware")
    headers = {'token': token['value'], 'User-Agent': token['user_agent'], 'lang': 'en', 'Connection': 'keep-alive'}
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

battery = None
battery_settings = {}

# get battery info and save to battery
def get_battery():
    global token, device_id, battery
    if get_device() is None:
        print(f"** could not get a device")
        return None
    if debug_setting > 0:
        print(f"getting battery")
    headers = {'token': token['value'], 'User-Agent': token['user_agent'], 'lang': 'en', 'Connection': 'keep-alive'}
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


# get charge times and save to battery_settings
def get_charge():
    global token, device_sn, battery_settings
    if get_device is None:
        print(f"** could not get a device")
        return None
    if debug_setting > 0:
        print(f"getting charge times")
    headers = {'token': token['value'], 'User-Agent': token['user_agent'], 'lang': 'en', 'Connection': 'keep-alive'}
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

# set charge times from battery
def set_charge():
    global token, device_sn, battery_settings
    if get_device() is None:
        print(f"** could not get a device")
        return None
    if battery_settings.get('times') is None:
        print(f"** no times to set")
        return None
    if debug_setting > 0:
        print(f"setting charge times")
    headers = {'token': token['value'], 'User-Agent': token['user_agent'], 'lang': 'en', 'Connection': 'keep-alive'}
    data = {'sn': device_sn, 'times': battery_settings.get('times')}
    response = requests.post(url="https://www.foxesscloud.com/c/v0/device/battery/time/set", headers=headers, data=json.dumps(data))
    if response.status_code != 200:
        print(f"** set charge response code: {response.status_code}")
        return None
    result = response.json().get('errno')
    if result != 0:
        print(f"** return code = {result}")
    elif debug_setting > 0:
        print(f"success") 
    return result

# get min soc settings and save in battery_settings
def get_min():
    global token, device_sn, battery_settings
    if get_device() is None:
        print(f"** could not get a device")
        return None
    if debug_setting > 0:
        print(f"getting min soc settings")
    headers = {'token': token['value'], 'User-Agent': token['user_agent'], 'lang': 'en', 'Connection': 'keep-alive'}
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

# set min soc from battery_settings
def set_min():
    global token, device_sn, bat_settings
    if get_device() is None:
        print(f"** could not get a device")
        return None
    if battery_settings.get('minGridSoc') is None or battery_settings.get('minSoc') is None:
        print(f"** no min soc settings")
        return None
    if debug_setting > 0:
        print(f"setting min soc")
    headers = {'token': token['value'], 'User-Agent': token['user_agent'], 'lang': 'en', 'Connection': 'keep-alive'}
    data = {'minGridSoc': battery_settings['minGridSoc'], 'minSoc': battery_settings['minSoc'], 'sn': device_sn}
    response = requests.post(url="https://www.foxesscloud.com/c/v0/device/battery/soc/set", headers=headers, data=json.dumps(data))
    if response.status_code != 200:
        print(f"** set min response code: {response.status_code}")
        return None
    result = response.json().get('errno')
    if result != 0:
        print(f"** return code = {result}")
    elif debug_setting > 0:
        print(f"success") 
    return result

# get times and min soc settings and save in bat_settings
def get_settings():
    global battery_settings
    get_charge()
    get_min()
    return battery_settings

work_mode = None

# get work mode
def get_work_mode():
    global token, device_id, work_mode
    if get_device() is None:
        print(f"** could not get a device")
        return None
    if debug_setting > 0:
        print(f"getting work mode")
    headers = {'token': token['value'], 'User-Agent': token['user_agent'], 'lang': 'en', 'Connection': 'keep-alive'}
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

work_modes = ['SelfUse', 'Feedin', 'Backup', 'PowerStation', 'PeakShaving']

# set work mode
def set_work_mode(mode):
    global token, device_id, work_modes, work_mode
    if get_device() is None:
        print(f"** could not get a device")
        return None
    if mode not in work_modes:
        print(f"** work mode: must be one of {work_modes}")
        return None
    if debug_setting > 0:
        print(f"setting work mode")
    headers = {'token': token['value'], 'User-Agent': token['user_agent'], 'lang': 'en', 'Connection': 'keep-alive'}
    data = {'id': device_id, 'key': 'operation_mode__work_mode', 'values': {'operation_mode__work_mode': mode}, 'raw': ''}
    response = requests.post(url="https://www.foxesscloud.com/c/v0/device/setting/set", headers=headers, data=json.dumps(data))
    if response.status_code != 200:
        print(f"** set work mode response code: {response.status_code}")
        return None
    result = response.json().get('errno')
    if result != 0:
        print(f"** return code = {result}")
        return None
    elif debug_setting > 0:
        print(f"success")
    work_mode = mode
    return work_mode


power_vars = ['generationPower', 'feedinPower','loadsPower','gridConsumptionPower','batChargePower', 'batDischargePower', 'pvPower']

# get raw data values
def get_raw(time_span = 'hour', d = None, v = None):
    global token, device_id, debug_setting, raw_vars
    if get_device() is None:
        print(f"** could not get device")
        return None
    headers = {'token': token['value'], 'User-Agent': token['user_agent'], 'lang': 'en', 'Connection': 'keep-alive'}
    if v is None:
        if raw_vars is None:
            raw_vars = get_vars()
        v = [x['variable'] for x in raw_vars]
    elif type(v) is not list:
        v = [v]
    query = {'deviceID': device_id, 'variables': v, 'timespan': time_span, 'beginDate': query_date(d)}
    response = requests.post(url="https://www.foxesscloud.com/c/v0/device/history/raw", headers=headers, data=json.dumps(query))
    if response.status_code != 200:
        print(f"** raw data response code: {response.status_code}")
        return None
    result = response.json().get('result')
    if result is None:
        print(f"** no raw data")
        return None
    # integrate kW to kWh based on 5 minute sample
    for x in [x for x in result if x['unit'] == 'kW']:
        sum0 = 0.0
        sum1 = 0.0
        sum2 = 0.0
        for y in x['data']:
            z = y['value']/12
            sum0 += abs(z)
            if z >= 0:
                sum1 += z
            else:
                sum2 -= z
        x['kWh0'] = round(sum0,3)
        x['kWh1'] = round(sum1,3)
        x['kWh2'] = round(sum2,3)
    return result

report_vars = ['generation', 'feedin', 'loads', 'gridConsumption', 'chargeEnergyToTal', 'dischargeEnergyToTal']

# get energy report data in kWh
def get_report(report_type = 'day', d = None, v = None ):
    global token, device_id, var_list, debug_setting, report_vars
    if get_device() is None:
        print(f"** could not get device")
        return None
    headers = {'token': token['value'], 'User-Agent': token['user_agent'], 'lang': 'en', 'Connection': 'keep-alive'}
    if v is None:
        v = report_vars
    elif type(v) is not list:
        v = [v]
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

# get earnings data
def get_earnings():
    global token, device_id, var_list, debug_setting, report_vars
    if get_device() is None:
        print(f"** could not get device")
        return None
    headers = {'token': token['value'], 'User-Agent': token['user_agent'], 'lang': 'en', 'Connection': 'keep-alive'}
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
