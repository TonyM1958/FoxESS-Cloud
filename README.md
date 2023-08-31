# FoxESS-Cloud
This site contains sample python code for accessing the Fox cloud data via the REST API used by the Fox ESS Cloud web site and app.
There is also a Jupyter Lab notebook with examples of how to run the sample code.

** This project is not endorsed by, directly affiliated with, maintained, authorized, or sponsored by Fox ESS. You make use of this code at your own risk, There is no warrany express or implied **

## Setup
To initialise a Jupyter Lab notebook, copy the following text and edit the configuration variables needed to add your values:

```
!pip install random-user-agent --root-user-action=ignore --quiet
!pip install foxesscloud --root-user-action=ignore --quiet
import foxesscloud.foxesscloud as f

# add your info here
f.username = "my.fox_username"
f.password = "my.fox_password"
f.device_sn = "my.fox_device_sn"

f.pv_api_key = "my.pv_api_key"
f.pv_system_id = "my.pv_system_id"

f.solcast_api_key = "my.solcast_api_key"
f.solcast_rids = ["my.solcast_rid1","my.solcast_rid2"]
```

You don't have to configure all of the settings. Your Fox ESS Cloud username, password and device serial number are the minimum required to access data about your inverter.

For example, replace _my.fox_username_ with the login name and _my.fox_password_ with the password you use for [foxesscloud.com](https://www.foxesscloud.com/login) and _my.device_sn_ with the serial number of your inverter. Be sure to keep the double quotes around the values you enter or you will get a syntax error.

## User Information
Load information about the user:

```
f.get_info()
```

This set the variable f.info and returns a dictionary containing user information.

## Site, Logger and Device Information
Load information about a site, data logger or inverter (device):

```
f.get_site()
f.get_logger()
f.get_device()
```

By default, this will load the first item in the list provided by the cloud.

If there is more than 1 item, the call will show the list of items. To select a specific item to work with, call a qualifier:
+ Site: full or partial name of the site
+ Logger: full or partial serial number
+ Inverter: full or partial serial number

When an item is selected, the functions returns a dictionary containing item details. For an inverter, a list of variables that can be used with the device is also loaded and stored as raw_vars

Once an inverter is selected, you can make other calls to get information:

```
f.get_firmware()
f.get_battery()
f.get_settings()
f.get_charge()
f.get_min()
f.get_work_mode()
f.get_earnings()

```
Each of these calls will return a dictionary containing the relevant information.

get_firmware() returns the current inverter firmware versions. The result is stored as f.firmware.

get_battery() returns the current battery status, including soc, voltage, current, power, temperature and residual energy. The result is stored as f.battery.

get_settings() will return the battery settings and is equivalent to get_charge() and get_min(). The results are stored in f.battery_settings. The settings include minSoc, minGridSoc, enable charge from grid and the time periods.

get_work_mode() returns the current work mode. The result is stored in f.work_mode.

get_earnings() returns the power generated and earning data that is displayed on the Fox web site and in the app.

## Inverter Settings
You can change inverter settings using:

```
f.set_min(minGridSoc, minSoc)
f.set_charge(ch1, st1, en1, ch2, st2, en2)
f.set_work_mode(mode)
```

set_min() takes the min_soc settings from battery_settings and applies these to the inverter. The parameters are optional and will update battery_settings:
+ minGridSoc: min Soc on Grid setting e.g. 15 = 15%
+ minSoc: min Soc setting e.g. 10 = 10%

set_charge() takes the charge times from the battery_settings and applies these to the inverter. The parameters are optional and will update battery_settings. You should specify all 3 parameter for a time period:
+ ch1: enable charge from grid for period 1 (True or False)
+ st1: the start time for period 1
+ en1: the end time for period 1
+ ch2: enable charge from grid for period 2 (True or False)
+ st2: the start time for period 2
+ en2: the end time for period 2

set_work_mode(mode) takes a work mode as a parameter and sets the inverter to this work mode. Valid work modes are held in work_modes. The new mode is stored in work_mode.

## Raw Data
Raw data reports inverter variables, collected every 5 minutes, on a given date / time and period:

```
f.get_raw(time_span, d, v, summary)
```

+ time_span determines the period covered by the data, for example, 'hour', 'day' or 'week'. The default is 'hour'
+ d is a date and time in the format 'YYYY-MM-DD HH:MM:SS'. The default is today's date and time
+ v is a variable, or list of variables (see below)
+ summary is optional - see following section.

The list of variables that can be queried is stored in raw_vars. There is also a pred-defined list power_vars that lists the main power values provided by the inverter. Data generation for the full list of raw_vars can be slow and return a lot of data, so it's best to select the vars you want from the list if you can.

For example, this Jupyter Lab cell will load an inverter and return power data at 5 minute intervals for the 17th June 2023:

```
d = '2023-06-17 00:00:00'
result=f.get_raw('day', d=d, v=f.power_vars)
```

## Summary of Raw Data

Setting the optional parameter 'summary' when calling get_raw() provides a summary of the raw data

+ summary = 1: summary is calculated
+ summary = 2: summary is calculated and raw data is removed to save time / space
+ summary = 3: as (2) but for energy only, an hourly cumulative state is also generated, similar to the state used in Home Assistant long term statistics

The summary includes the following attributes:
+ count: the number of data points
+ average: the average value of the data points
+ max: the maximum value of the data points
+ max_time: the time when the maximum value occured (HH:MM)
+ min: the minimum value of the data points
+ min_time: the time when the minimum value occured (HH:MM)

For power values, the summary performs a Riemann sum of the data, integrating kW over the day to estimate energy in kWh. In this case, the following attributes are also added:
+ kwh: the total energy generated or consumed
+ kwh_off: the energy consumed or generated during the off-peak time of use
+ kwh_peak: the energy consumed or generated during the peak time of use

## Report Data
Report data provides information on the energy produced by the inverter, battery charge and discharge energy, grid consumption and feed-in energy and home energy consumption:

```
f.get_report(report_type, d, v, totals)
```
+ report_type sets the period covered by the report and is one of 'day', 'week', 'month', 'year':
+ when 'day' is selected, energy is reported each hour through the day
+ when 'week' is selected, energy is reported for the 7 days up to and including the date
+ when 'month' is selected, energy is reported each day through the month
+ when 'year' is selected, energy is reported each month through the year
+ d is a date and time in the format 'YYYY-MM-DD HH:MM:SS'. The default is yesterday
+ v is a variable, or list of variables. The default is to use report_vars
+ totals=1 quick report with just total for a day. report_type must be 'day' or this parameter will be ignored

The list of variables that can be reported on is stored in f.report_vars.

Note that reporting by 'day' produces inaccurate hourly data, where the sum does not reconcile with the daily total given in the monthly report. To correct this, reporting by day also gets the monthly data and uses the daily total to correctly report the total.

The result data for each variable include the following attributes when totals=1:
+ 'variable': name of the data set
+ 'total': corrected total of the data items

When totals=0, the following attributes are also available:

+ 'data': dictionary of 'index' and 'value' for each data point
+ 'date': that was used to produce the report
+ 'count': the number of data items
+ 'sum': the sum of the data items
+ 'max': the biggest value in 'data'
+ 'max_index': the index of the biggest value in 'data'
+ 'min': the smallest value in 'data'
+ 'min_index': the index of the smallest value in 'data'
+ 'average': corrected average of the data items

For example, this Jupyter Lab cell will report energy data by day for the month of June 2023:

```
d = '2023-06-17'
result=f.get_report('month', d=d)
```

# Built-in Utilities and Operations

The previous section provides functions that can be used to access and control your inverter. This section covers utilities and operations that build upon these functions.

## Charge Needed

Uses forecast PV yield for tomorrow to work out if charging from grid is needed tonight to deliver the expected consumption for tomorrow. If charging is needed, the charge times are configured. If charging is not needed, the charge times are cleared. The results are sent to the inverter.

```
f.charge_needed(forecast, annual_consumption, contingency, start_at, end_by, force_charge, charge_power, efficiency, run_after, update_setings)
```

All the parameters are optional:
+ forecast: the kWh expected tomorrow (optional, see below)
+ annual_consumption: the kWh consumption each year, delivered via the inverter. Default is your average consumption of the last 7 days
+ contingency: adds charge to allow for variations in consumption and reduction in battery residual prior to charging. 1.0 is no variation. Default is 1.25 (+25%)
+ start_at: time when charging will start in HH:MM or decimal hours e.g. '23:30' or 23.5 hours. The default is set by the tariff
+ end_by: time when charging must stop. The default is set by the tariff
+ force_charge: if set to 1, any remaining time between start_at and end_by has force charge set to preserve the battery. If 0, force charge is not set
+ charge_power: the kW of charge that will be applied. By default, the power rating is derrived from the inverter model. Set this figure if you have reduced your max charge current
+ efficiency: conversion factor from PV power or AC power to charge power. The default is 0.95 (95%)
+ run_after: the time in hours when the charge calculation should take place. The default is 22 (10pm). If run before this time, no action will be taken
+ update_settings: 1 allows charge_needed to update inverter settings. The default is 0

If a manual forecast is not provided but Solcast credentials have been set, your solcast forecast will be loaded and displayed. The average of the last 7 days generation will also be shown based on the power reported for PV and CT2 inputs. The figure used for tomorrow's generation will be the manual forecast, solcast forecast or average of the last 7 days, in that order, depending on what is available.

If an annual_consumption is not provided, the average of the last 7 days consumption based on the load power reported by the inverter will be used. For systems with multiple inverters where CT2 is not connected, the load power may not be correct. For this and other cases where you want to set your consumption, provide your annual_consumption. Daily consumption is calculated by dividing annual_consumption by 365 and applying seasonality that decreases consumption in the summer and increases it in winter. The seasonality can be adjusted by setting a list of weightings for the months Jan, Feb, Mar etc. The sum of the weightings should be 12.0 so that the overall annual consumption is accurate. The seasonality settings can be viewed and updated:

```
f.seasonality = [1.1, 1.1, 1.0, 1.0, 0.9, 0.9, 0.9, 0.9, 1.0, 1.0, 1.1, 1.1]
```

Note: if using Solcast, calls to the API for hobby accounts are very limited so repeated calls to charge_needed can exhaust the calls available, resulting in failure to get a forecast. It is recommended that charge_needed is scheduled to run once between 8pm and midnight to update the charging schedule. Running at this time gives a better view of the residual charge in the battery after charging from solar has finished for the day and peak early evening consumption is tailing off.

## Date Ranges

```
f.date_list(s, e, limit, span, today)
```

Returns a list of dates in the format 'YYYY-MM-DD'. This function will not return dates in the future. The last date will be yesterday or today (if today is True). All parameters are optional:

+ s: start date
+ e: end date
+ limit: maximum number of days. The default is 200
+ span: the range of dates. One of 'day', 'week', 'month' or 'year'
+ today: if set to 1 allows today to be included, otherwise, date list will stop at yesterday


## Time of Use

Time Of Use (TOU) periods configure when your battery can be charged and can be use to split your grid import and export into peak, off-peak and shoulder times when data is uploaded to PV Ouptut.

There are a number of different pre-configured tariffs:
+ f.octous_flux: charging from 02:00 to 05:00, off-peak from 02:00 to 05:00, peak from 16:00 to 19:00
+ f.intelligent_octopus: charging from 23:30 to 05:00. off-peak from 23:30 to 05:30
+ f.octopus_cosy: charging from 04:00 to 07:00, off-peak from 04:00 to 07:00 and 13:00 to 16:00, peak from 16:00 to 19:00
+ f.octopus_go: charging rofm 00:30 to 04:30, off peak from 00:30 to 04:30

Custom periods can be configured for specific times if required:
+ f.custom_periods: charging from 02:00 to 05:00, no off-peak or peak times

A list of the tariffs is held in f.tariff_list

The active tariff in configured in 'f.tou_periods'. The default setting is:

```
f.tou_periods = f.octopus_flux
```

Note: when TOU is applied, energy values are estimated using the Riemann sum of the 5 minute power values over a day. This means the results vary by up to 10% from the daily totals reported without time of use.

Time period settings are held as decimal hours. Functions are available to convert time strings with the format 'HH:MM:SS' to decimal hours and back are:

```
f.time_hours(s, d)
f.hours_time(h, ss)
```

Where:
+ s: is a time string ('HH:MM' or 'HH:MM:SS')
+ d: is optional and is the default time if s is None
+ h: is decimal hours (e.g 1.5)
+ ss: is optional. When True, time strings include seconds HH:MM:SS, otherwise they are hours and minutes 'HH:MM' 


# PV Output
These functions produce CSV data for upload to [pvoutput.org](https://pvoutput.org) including PV generation, Export, Load and Grid consumption by day in Wh. The functions use the energy estimates created from the raw power data (see above). The estimates include PV energy generation that are not otherwise available from the Fox Cloud. Typically, the energy results are within 3% of the values reported by the meters built into the inverter.


## Get PV Output Data

Returns CSV upload data using the [API format](https://pvoutput.org/help/api_specification.html#csv-data-parameter):

```
f.get_pvoutput(d, tou)
```

+ d is the date or a list of dates, to get data for. The default is yesterday
+ tou: optional, setting tou=1 uploads data with time of use. The default, tou=0 does not split data and is more accurate.

You can copy and paste the output data to the pvoutput data CSV Loader, using the following settings:

![image](https://github.com/TonyM1958/FoxESS-Cloud/assets/63789168/21459cdc-a943-4e9d-a204-7efd45a422d8)

For example, this Jupyer Lab cell will provide a CSV data upload for June 2023:

```
f.get_pvoutput(f.date_list('2023-06-01', '2023-06-30'))
```

## Set PV Output Data

Loads CSV data directly using the PV Ouput API:

```
f.set_pvoutput(d, system_id, today, tou)
```

+ d is optional and is the date, or a list of dates, to upload. For default, see today below
+ system_id is optional and allow you to select where data is uploaded to (where you have more than 1 registered system)
+ today = True is optional and sets the default day to today. The default is False and sets the default day to yesterday 
+ tou: optional, setting tou=1 uploads data with time of use. The default, tou=0 does not split data and is more accurate.


## Troubleshooting

If needed, you can add the following setting to increase the level of information reported by the foxesscloud module:

```
f.debug_setting = 2
```

This setting can be:
+ 0: silent mode (minimal output)
+ 1: information reporting (default)
+ 2: more debug information, updating of inverter settings is disabled


## Version Info

0.3.4: updated report_data for quick totals. Boolean parameters accept 0/1 or True/False<br>
0.3.3: Updated Jupyter notebooks and default parameter values. Added tariffs and tou_periods with settings for Octopus Flux, Intelligent, Cosy and Go<br>
0.3.2: Added time input in 'HH:MM'. Added get_access(). More information output when running charge_needed and set_pvoutput<br>
0.3.1: Added ability to flip polarity of CT2. Improved data reporting for charge_needed<br>
0.3.0: Added time_span 'week' to raw_data. Added max and max_time to energy reporting. Added max, max_index, min, min_index to report_data. Added 7 days average generation and consumption to charge_needed, printing of parameters and general update of progress reporting<br>
0.2.8: Added max and min to get_report(). Adjusted parsing for inverter charge power. Changed run_after to 10pm. Fixed solcast print/ plot<br>
0.2.3: Added charge_needed() and solcast forcast<br>
