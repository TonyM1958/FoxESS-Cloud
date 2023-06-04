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

url_auth = "https://www.foxesscloud.com/c/v0/user/login"
url_device = "https://www.foxesscloud.com/c/v0/device"
url_raw = "https://www.foxesscloud.com/c/v0/device/history/raw"
url_report = "https://www.foxesscloud.com/c/v0/device/history/report"

token = {'value': None, 'valid_from': None, 'valid_for': datetime.timedelta(hours=4).seconds, 'user_agent': None}
device_list = None
device = None
device_id = None
firmware = None
variables = None
battery = None
allData = {
    "report":{},
    "reportDailyGeneration": {},
    "raw":{},
    "online":False
    }

def get_token():
    global username, password, token
    time_now = datetime.datetime.now()
    if token['valid_from'] is not None:
        if (time_now - token['valid_from']).seconds <= token['valid_for']:
            if debug_setting > 0:
                print(f"token is still valid")
            return token['value']
    if debug_setting > 0:
        print(f"loading new token")
    credentials = {'user': private.username, 'password': hashlib.md5(private.password.encode()).hexdigest()}
    token['user_agent'] = user_agent_rotator.get_random_user_agent()
    headers = {'User-Agent': token['user_agent'], 'lang': 'en', 'Connection': 'keep-alive'}
    response = requests.post(url=url_auth, headers=headers, data=credentials)
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

def get_device():
    global token, device_list, device, device_id
    if device is not None:
        return device
    if get_token() is None:
        print(f"** could not get a token")
        return None
    if debug_setting > 0:
        print(f"getting device")
    headers = {'token': token['value'], 'User-Agent': token['user_agent'], 'lang': 'en', 'Connection': 'keep-alive'}
    query = {'pageSize': 10, 'currentPage': 1, 'total': 0, 'queryDate': {'begin': 0, 'end':0} }
    response = requests.post(url_device + '/list', headers=headers, data=query)
    if response.status_code != 200:
        print(f"** list response code: {response.status_code}")
        return None
    result = response.json().get('result')
    if result is None:
        print(f"** no device list result data")
        return None
    device_list = result.get('devices')
    if device_list is None or len(device_list) < 1:
        print(f"** no devices found")
        return None
    if len(device_list) > 1:
        print(f"** {len(device_list)} devices were found")
        for d in device_list:
            print(f"SN={d['deviceSN']}, Type={d['deviceType']}, ID={d['deviceID']} ")
    device = device_list[0]
    device_id = device.get('deviceID')
    return device

def get_battery():
    global token, device_list, device, device_id, battery
    if get_device() is None:
        print(f"** could not get a device")
        return None
    if battery is not None:
        return battery
    if debug_setting > 0:
        print(f"getting battery")
    headers = {'token': token['value'], 'User-Agent': token['user_agent'], 'lang': 'en', 'Connection': 'keep-alive'}
    response = requests.get(url_device + '/battery/info?id=' + device_id, headers=headers)
    if response.status_code != 200:
        print(f"** battery response code: {response.status_code}")
        return None
    result = response.json().get('result')
    if result is None:
        print(f"** no battery info")
        return None
    battery = result
    return battery

def get_variables():
    global token, device_list, device, device_id, variables
    if get_device() is None:
        print(f"** could not get a device")
        return None
    if variables is not None:
        return variables
    if debug_setting > 0:
        print(f"getting variables")
    headers = {'token': token['value'], 'User-Agent': token['user_agent'], 'lang': 'en', 'Connection': 'keep-alive'}
    response = requests.get(url_device + '/variables?deviceID=' + device_id, headers=headers)
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
    return variables

def get_firmware():
    global token, device_id, firmware
    if get_device() is None:
        print(f"** could not get a device")
        return None
    if debug_setting > 0:
        print(f"getting firmware")
    headers = {'token': token['value'], 'User-Agent': token['user_agent'], 'lang': 'en', 'Connection': 'keep-alive'}
    response = requests.get(url_device + '/addressbook?deviceID=' + device_id, headers=headers)
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


def get_rawdata():
    if get_addressbook() is None:
        print(f"** could not get address book")
        return None
    headers = {'token': token['value'], 'User-Agent': token['user_agent'], 'lang': 'en', 'Connection': 'keep-alive'}
    raw = {'deviceID' : private.device_id, 'variables': ['invBatVolt'], 'timespan': 'hour'}
    response = requests.post(url_raw, headers=headers, data=raw)
    if response.status_code != 200:
        print(f"** raw data response code: {response.status_code}")
        return None
    result = response.json().get('result')
    if result is None:
        print(f"** no raw data")
        return None
    return result

    rawData = '{"deviceID":"'+deviceID+'","variables":["ambientTemperation","batChargePower","batCurrent","batDischargePower","batTemperature","batVolt","boostTemperation","chargeEnergyToTal","chargeTemperature","dischargeEnergyToTal","dspTemperature","epsCurrentR","epsCurrentS","epsCurrentT","epsPower","epsPowerR","epsPowerS","epsPowerT","epsVoltR","epsVoltS","epsVoltT","feedin","feedin2","feedinPower","generation","generationPower","gridConsumption","gridConsumption2","gridConsumptionPower","input","invBatCurrent","invBatPower","invBatVolt","invTemperation","loads","loadsPower","loadsPowerR","loadsPowerS","loadsPowerT","meterPower","meterPower2","meterPowerR","meterPowerS","meterPowerT","PowerFactor","pv1Current","pv1Power","pv1Volt","pv2Current","pv2Power","pv2Volt","pv3Current","pv3Power","pv3Volt","pv4Current","pv4Power","pv4Volt","pvPower","RCurrent","ReactivePower","RFreq","RPower","RVolt","SCurrent","SFreq","SoC","SPower","SVolt","TCurrent","TFreq","TPower","TVolt"],"timespan":"hour","beginDate":{"year":'+now.strftime(
        "%Y")+',"month":'+now.strftime("%_m")+',"day":'+now.strftime("%_d")+',"hour":'+now.strftime("%_H")+'}}'

    restRaw = RestData(hass, METHOD_POST, _ENDPOINT_RAW,DEFAULT_ENCODING,
                       None, headersData, None, rawData, DEFAULT_VERIFY_SSL, SSLCipherList.PYTHON_DEFAULT)

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


async def getRaw(hass, headersData, allData, deviceID):
    now = datetime.now()

    rawData = '{"deviceID":"'+deviceID+'","variables":["ambientTemperation","batChargePower","batCurrent","batDischargePower","batTemperature","batVolt","boostTemperation","chargeEnergyToTal","chargeTemperature","dischargeEnergyToTal","dspTemperature","epsCurrentR","epsCurrentS","epsCurrentT","epsPower","epsPowerR","epsPowerS","epsPowerT","epsVoltR","epsVoltS","epsVoltT","feedin","feedin2","feedinPower","generation","generationPower","gridConsumption","gridConsumption2","gridConsumptionPower","input","invBatCurrent","invBatPower","invBatVolt","invTemperation","loads","loadsPower","loadsPowerR","loadsPowerS","loadsPowerT","meterPower","meterPower2","meterPowerR","meterPowerS","meterPowerT","PowerFactor","pv1Current","pv1Power","pv1Volt","pv2Current","pv2Power","pv2Volt","pv3Current","pv3Power","pv3Volt","pv4Current","pv4Power","pv4Volt","pvPower","RCurrent","ReactivePower","RFreq","RPower","RVolt","SCurrent","SFreq","SoC","SPower","SVolt","TCurrent","TFreq","TPower","TVolt"],"timespan":"hour","beginDate":{"year":'+now.strftime(
        "%Y")+',"month":'+now.strftime("%_m")+',"day":'+now.strftime("%_d")+',"hour":'+now.strftime("%_H")+'}}'

    restRaw = RestData(hass, METHOD_POST, _ENDPOINT_RAW,DEFAULT_ENCODING,
                       None, headersData, None, rawData, DEFAULT_VERIFY_SSL, SSLCipherList.PYTHON_DEFAULT)
    await restRaw.async_update()

    if restRaw.data is None:
        _LOGGER.error("Unable to get Raw data from FoxESS Cloud")
        return False
    else:
        _LOGGER.debug("FoxESS Raw data fetched correctly " +
                      restRaw.data[:150] + " ... ")
        allData['raw'] = {}
        for item in json.loads(restRaw.data)['result']:
            variableName = item['variable']
            # If data is a non-empty list, pop the last value off the list, otherwise return the previously found value
            if item["data"]:
                allData['raw'][variableName] = item["data"].pop().get("value",None)

