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
from datetime import datetime, timedelta
from copy import deepcopy
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

token = {'value': None, 'valid_from': None, 'valid_for': timedelta(hours=4).seconds, 'user_agent': None, 'lang': 'en'}

def query_date(d):
    t = datetime.now() if d is None else datetime.strptime(d, "%Y-%m-%d %H:%M:%S")
    return {'year': t.year, 'month': t.month, 'day': t.day, 'hour': t.hour, 'minute': t.minute, 'second': t.second}

# login and get token if required. Check if token has expired and renew if required.
def get_token():
    global username, password, token, device_list, device, device_id
    time_now = datetime.now()
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
    headers = {'User-Agent': token['user_agent'], 'lang': token['lang'], 'Connection': 'keep-alive'}
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

# get list of available devices and select one, using the serial number if there is more than 1
def get_device(sn=None):
    global token, device_list, device, device_id, device_sn, firmware, battery, raw_vars
    if get_token() is None:
        print(f"** could not get a token")
        return None
    if device is not None:
        return device
    if debug_setting > 0:
        print(f"getting device")
    headers = {'token': token['value'], 'User-Agent': token['user_agent'], 'lang': token['lang'], 'Connection': 'keep-alive'}
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
    n = None
    if len(device_list) > 1:
        if sn is not None:
            for i in range(len(device_list)):
                if device_list[i]['deviceSN'][:len(sn)] == sn:
                    n = i
                    break
        if n is None:
            print(f"** multiple devices found, please specify a serial number from the list")
            for d in device_list:
                print(f"SN={d['deviceSN']}, Type={d['deviceType']}, ID={d['deviceID']} ")
            return None
    else:
        n = 0
    device = device_list[n]
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

firmware = None

# get current firmware versions for selected device
def get_firmware():
    global token, device_id, firmware
    if get_device() is None:
        print(f"** could not get a device")
        return None
    if debug_setting > 0:
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

# get charge times and save to battery_settings
def get_charge():
    global token, device_sn, battery_settings
    if get_device is None:
        print(f"** could not get a device")
        return None
    if debug_setting > 0:
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
    headers = {'token': token['value'], 'User-Agent': token['user_agent'], 'lang': token['lang'], 'Connection': 'keep-alive'}
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
    headers = {'token': token['value'], 'User-Agent': token['user_agent'], 'lang': token['lang'], 'Connection': 'keep-alive'}
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
    elif debug_setting > 0:
        print(f"success")
    work_mode = mode
    return work_mode

# generationPower must be first
power_vars = ['generationPower', 'feedinPower','loadsPower','gridConsumptionPower','batChargePower', 'batDischargePower', 'pvPower']
# equivalent data after integration from kW into kWh, input name must be last
energy_vars = ['output_daily', 'feedin_daily', 'load_daily', 'grid_daily', 'bat_charge_daily', 'bat_discharge_daily', 'pv_energy_daily', 'input_daily']

# get raw data values
# transform determines operating mode - 0: return raw data, 1: add kwh, 2: add kwh and drop raw data
def get_raw(time_span = 'hour', d = None, v = None, transform = 0):
    global token, device_id, debug_setting, raw_vars
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
    if transform == 0:
        return result
    # copy generationPower to produce inputPower data
    generation_name = power_vars[0]
    generation_index = None
    if generation_name in v:
        generation_index = v.index(generation_name)
        input_name = energy_vars[-1]
        input_result = deepcopy(result[generation_index])
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
            h = int(y['time'][11:13])       # current hour
            z = y['value']/12               # convert kW to kWh
            if z >= 0.0:
                kwh += z
                if h >= 2 and h < 5:        # hour is between 2am and 5am
                    kwh_off += z
                if h >= 16 and h < 19:      # hour is between 4pm and 7pm
                    kwh_peak += z
            else:                           # remove ignored -ve values
                y['value'] = 0.0
            if h > hour:    # new hour
                x['state'].append(round(kwh,1))
                hour = h
        x['kwh'] = round(kwh,1)
        x['kwh_off'] = round(kwh_off,1)
        x['kwh_peak'] = round(kwh_peak,1)
        x['state'].append(round(kwh,1))
        if transform ==2:
            if generation_index is not None and x['name'] != input_name:
                x['name'] = energy_vars[power_vars.index(x['variable'])]
            x['unit'] = 'kWh'
            del x['data']
            del x['variable']
    return result

report_vars = ['generation', 'feedin', 'loads', 'gridConsumption', 'chargeEnergyToTal', 'dischargeEnergyToTal']

# get energy report data in kWh
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
    if debug_setting > 0:
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

# get earnings data
def get_earnings():
    global token, device_id, var_list, debug_setting, report_vars
    if get_device() is None:
        print(f"** could not get device")
        return None
    if debug_setting > 0:
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
# pvoutput upload
##################################################################################################

# generate a list of up to 200 dates, where the last date is not later than yeterday
def date_list(s=None, e=None):
    yesterday = datetime.date(datetime.now() - timedelta(days=1))
    d = datetime.date(datetime.strptime(s, '%Y-%m-%d')) if s is not None else yesterday
    if d > yesterday:
        d = yesterday
    l = [datetime.strftime(d, '%Y-%m-%d')]
    if e is None:
        return l
    last = datetime.date(datetime.strptime(e, '%Y-%m-%d'))
    n = 0
    while d < last and d < yesterday and n < 200:
        d += timedelta(days=1)
        l.append(datetime.strftime(d, '%Y-%m-%d'))
        n += 1
    return l

def format_data(dat, gen, exp, con = '', imp = ''):
    return f"{dat},{gen},{exp},,,,,,,0,{imp},0,0,{con},,,,"

pvoutput_vars = ['pvPower', 'feedinPower', 'loadsPower', 'gridConsumptionPower']
pvoutput_names = ['gen', 'exp', 'con', 'imp']

# get CSV upload data from the Fox Cloud as energy values for a list of dates
def get_pvoutput(dates):
    if len(dates) == 0:
        print(f"** invalid date range")
        return
    print(f"CSV upload data: {pvoutput_names}")
    for d in dates:
        values = get_raw('day', d=d + ' 00:00:00', v = pvoutput_vars, transform=2)
        result = {'date' : d}
        text = d
        for i in range(len(pvoutput_names)):
            v = round(values[i]['kwh'],3)
            text += f",{v}"
        if debug_setting > 0:
            print(text)
    return


# upload data for day 'dat' via pvoutput api
def put_pvoutput(data, system_id = None):
    global debug_setting
    if system_id is None:
        system_id = private.pvoutput_systemid
    headers = {'X-Pvoutput-Apikey': private.api_key, 'X-Pvoutput-SystemId': system_id, 'Content-Type': 'application/x-www-form-urlencoded'}
    if debug_setting > 1:
        print(system_id)
        print(data)
    response = requests.post(url="https://pvoutput.org/service/r2/addoutput.jsp", headers=headers, data='data=' + data)
    result = response.status_code
    if result != 200:
        print(f"** put_pvoutput response code: {result}")
        return None
    return result
