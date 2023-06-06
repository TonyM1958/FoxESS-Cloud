##################################################################################################
"""
Module:   Fox ESS Cloud Query
Created:  3 June 2023
Updated:  3 June 2023
By:       Tony Matthews
"""
##################################################################################################
# This is the code used for the getting inverter data for the Fox ESS cloud web site
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

url_raw = "https://www.foxesscloud.com/c/v0/device/history/raw"
url_report = "https://www.foxesscloud.com/c/v0/device/history/report"

token = {'value': None, 'valid_from': None, 'valid_for': datetime.timedelta(hours=4).seconds, 'user_agent': None}
device_list = None
device = None
device_id = None
battery = None
firmware = None
variables = None
var_list = None

allData = {
    "report":{},
    "reportDailyGeneration": {},
    "raw":{},
    "online":False
    }

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

# get list of available devices and select one
def get_device(n=None):
    global token, device_list, device, device_id
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
    get_firmware()
    get_variables()
    return device

# get battery info for selected device
def get_battery():
    global token, device_id, battery
    if get_device() is None:
        print(f"** could not get a device")
        return None
    if debug_setting > 0:
        print(f"getting battery")
    headers = {'token': token['value'], 'User-Agent': token['user_agent'], 'lang': 'en', 'Connection': 'keep-alive'}
    response = requests.get(url="https://www.foxesscloud.com/c/v0/device/battery/info?id=" + device_id, headers=headers)
    if response.status_code != 200:
        print(f"** battery response code: {response.status_code}")
        return None
    result = response.json().get('result')
    if result is None:
        print(f"** no battery info")
        return None
    battery = result
    return battery

# get list of variables available for selected device
def get_variables():
    global token, device_id, variables, var_list
    if get_device() is None:
        print(f"** could not get a device")
        return None
    if debug_setting > 0:
        print(f"getting variables")
    var_list = None
    headers = {'token': token['value'], 'User-Agent': token['user_agent'], 'lang': 'en', 'Connection': 'keep-alive'}
    # v1 api required for full list with {name, variable, unit}
    response = requests.get(url="https://www.foxesscloud.com/c/v1/device/variables?deviceID=" + device_id, headers=headers)
    if response.status_code != 200:
        print(f"** variables response code: {response.status_code}")
        return None
    result = response.json().get('result')
    if result is None:
        print(f"** no variables result")
        return None
    variables = result.get('variables')
    if variables is None:
        print(f"** no variables list")
        return None
    var_list = []
    for v in variables:
        var_list.append(v['variable'])
    return variables

# get current firmware versions for selected device
def get_firmware():
    global token, device_id, firmware
    if get_device() is None:
        print(f"** could not get a device")
        return None
    if debug_setting > 0:
        print(f"getting firmware")
    headers = {'token': token['value'], 'User-Agent': token['user_agent'], 'lang': 'en', 'Connection': 'keep-alive'}
    response = requests.get(url="https://www.foxesscloud.com/c/v0/device/addressbook?deviceID=" + device_id, headers=headers)
    if response.status_code != 200:
        print(f"** address book response code: {response.status_code}")
        return None
    result = response.json().get('result')
    if result is None:
        print(f"** no address book result data")
        return None
    firmware = result.get('softVersion')
    if firmware is None:
        print(f"** no firmware data")
        return None
    return firmware

# get raw data values
def get_rawdata():
    global token, device_id, var_list, debug_setting
    if get_device() is None:
        print(f"** could not get device")
        return None
    if var_list is None:
        get_variables()
    headers = {'token': token['value'], 'User-Agent': token['user_agent'], 'lang': 'en', 'Connection': 'keep-alive'}
    t = datetime.datetime.now()
    query = {'deviceID': device_id, 'variables': var_list, 'timespan': 'hour',
          'beginDate': {'year': t.year, 'month': t.month, 'day': t.day, 'hour': t.hour, 'minute': t.minute, 'second': t.second}}
    response = requests.post(url="https://www.foxesscloud.com/c/v0/device/history/raw", headers=headers, data=json.dumps(query))
    if response.status_code != 200:
        print(f"** raw data response code: {response.status_code}")
        return None
    result = response.json().get('result')
    if result is None:
        print(f"** no raw data")
        return None
    return result

def async_update_data():
    _LOGGER.debug("Updating data from https://www.foxesscloud.com/")
    user_agent = user_agent_rotator.get_random_user_agent()
    headersData = {"token": token['value'],
                   "User-Agent": token['user_agent'],
                   "lang": "en",
                   "sec-ch-ua-platform": "macOS",
                   "Sec-Fetch-Site": "same-origin",
                   "Sec-Fetch-Mode": "cors",
                   "Sec-Fetch-Dest": "empty",
                   "Referer": "https://www.foxesscloud.com/bus/device/inverterDetail?id=xyz&flowType=1&status=1&hasPV=true&hasBattery=false",
                   "Accept-Language":"en-US;q=0.9,en;q=0.8,de;q=0.7,nl;q=0.6",
                   "X-Requested-With": "XMLHttpRequest"}
    getAddresbook(hass, headersData, allData, deviceID, username, hashedPassword,0)
    if int(allData["addressbook"]["result"]["status"]) == 1 or int(allData["addressbook"]["result"]["status"]) == 2 or int(allData["addressbook"]["result"]["status"]) == 3:
        allData["online"] = True
        getRaw(hass, headersData, allData, deviceID)
        getReport(hass, headersData, allData, deviceID)
        getReportDailyGeneration(hass, headersData, allData, deviceID)
    return allData



async def getReport(hass, headersData, allData, deviceID):
    now = datetime.now()


    reportData = '{"deviceID":"'+deviceID+'","reportType":"day","variables":["feedin","generation","gridConsumption","chargeEnergyToTal","dischargeEnergyToTal","loads"],"queryDate":{"year":'+now.strftime(
        "%Y")+',"month":'+now.strftime("%_m")+',"day":'+now.strftime("%_d")+'}}'

    restReport = RestData(hass, METHOD_POST, _ENDPOINT_REPORT,DEFAULT_ENCODING,
                          None, headersData, None, reportData, DEFAULT_VERIFY_SSL, SSLCipherList.PYTHON_DEFAULT)

    await restReport.async_update()

    if restReport.data is None:
        _LOGGER.error("Unable to get Report data from FoxESS Cloud")
        return False
    else:
        _LOGGER.debug("FoxESS Report data fetched correctly " +
                      restReport.data[:150] + " ... ")

        for item in json.loads(restReport.data)['result']:
            variableName = item['variable']
            allData['report'][variableName] = None
            # Daily reports break down the data hour by hour for the whole day
            # even if we're only partially through, so sum the values together
            # to get our daily total so far...
            cumulative_total = 0
            for dataItem in item['data']:
                cumulative_total += dataItem['value']
            allData['report'][variableName] = cumulative_total


async def getReportDailyGeneration(hass, headersData, allData, deviceID):
    now = datetime.now()

    generationData = ('{"deviceID":"' + deviceID + '","reportType": "month",' + '"variables": ["generation"],' + '"queryDate": {' + '"year":' + now.strftime(
        "%Y") + ',"month":' + now.strftime("%_m") + ',"day":' + now.strftime("%_d") + ',"hour":' + now.strftime("%_H") + "}}")

    restGeneration = RestData(
        hass,
        METHOD_POST,
        _ENDPOINT_REPORT,
        DEFAULT_ENCODING,
        None,
        headersData,
        None,
        generationData,
        DEFAULT_VERIFY_SSL,
        SSLCipherList.PYTHON_DEFAULT
    )

    await restGeneration.async_update()

    if restGeneration.data is None:
        _LOGGER.error("Unable to get daily generation from FoxESS Cloud")
        return False
    else:
        _LOGGER.debug("FoxESS daily generation data fetched correctly " +
                      restGeneration.data)

        parsed = json.loads(restGeneration.data)["result"]
        allData["reportDailyGeneration"] = parsed[0]["data"][int(
            now.strftime("%d")) - 1]


