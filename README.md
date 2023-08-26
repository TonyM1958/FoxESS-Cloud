# FoxESS-Cloud
This site contains sample python code for accessing the Fox cloud data via the REST API used by the Fox ESS Cloud web site and app.
There is also a Jupyter Lab notebook with examples of how to run the sample code.

## Setup
To initialise a Jupyter Lab notebook, copy the following text:

```
!pip install random-user-agent --root-user-action=ignore --quiet
!pip install foxesscloud --root-user-action=ignore --quiet
import foxesscloud.foxesscloud as f

# add your info here
f.username = "<your username>"
f.password = "<your password"
f.device_sn = "<your serial number>"

f.pv_api_key = "<your api key>"
f.pv_system_id = "<your system id>"

f.solcast_api_key = "<your api key"
f.solcast_rids = ["<your rid 1>","<your rid2>"]
```

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
f.set_min()
f.set_charge()
f.set_work_mode(mode)
```

set_min() takes the min_soc settings from battery_settings and applies these to the inverter.

set_charge() takes the charge times from the battery_settings and applies these to the inverter.

set_work_mode(mode) takes a work mode as a parameter and sets the inverter to this work mode. Valid work modes are held in work_modes. The new mode is stored in work_mode.

## Raw Data
Raw data reports inverter variables, collected every 5 minutes, on a given date / time and period:

```
f.get_raw(time_span, d, v, energy)
```

+ time_span determines the period covered by the data, for example, 'hour' or 'day'
+ d is a text string containing a date and time in the format 'yyyy-mm-dd hh:mm:ss'
+ v is a variable, or list of variables
+ energy is optional - see following section.

The list of variables that can be queried is stored in raw_vars. There is also a pred-defined list power_vars that lists the main power values provided by the inverter.

For example, this Jupyter Lab cell will load an inverter and return power data at 5 minute intervals for the 17th June 2023:

```
d = '2023-06-17 00:00:00'
result=f.get_raw('day', d=d, v=f.power_vars)
```

## Estimated Energy

Setting the optional parameter 'energy' when calling get_raw() provides daily energy stats from the power data

+ energy = 1: energy stats (kwh) are calculated
+ energy = 2: energy stats (kwh) are calculated and raw power data is removed to save space

The transform performs a Riemann sum of the power data, integrating kW over the day to estimate energy in kWh. Comparison with the inverter built-in energy meters indicates the estimates are within 3%.

In addition to daily energy totals, it implements peak and off-peak time of use (TOU). The time periods are set by global variables: off_peak1, off_peak2 and peak. The default settings are:

+ off_peak1: 02:00 to 05:00 - adds energy to kwh_off
+ off_peak2: 00:00 to 00:00 - adds energy to kwh_off
+ peak: 16:00 to 19:00 - adds energy to kwh_peak
+ other times: calculate from kwh - kwh_peak - kwh_off

## Report Data
Report data provides information on the energy produced by the inverter, battery charge and discharge energy, grid consumption and feed-in energy and home energy consumption:

```
f.get_report(report_type, d, v)
```
+ report_type sets the period covered by the report and is one of 'day', 'week', 'month', 'year':
+ when 'day' is selected, energy is reported each hour through the day;
+ when 'week' is selected, energy is reported for the 7 days up to and including the date;
+ when 'month' is selected, energy is reported each day through the month;
+ when 'year' is selected, energy is reported each month through the year
+ d is a text string containing a date and time in the format 'yyyy-mm-dd hh:mm:ss'. The default is yesterday
+ v is a variable, or list of variables. The default is to all report_vars

Note that reporting by 'day' does not produce accurate data so it is advised to report by month and select the day required to get an accurate report of total energy for a specific day

The list of variables that can be reported on is stored in f.report_vars. The results include the following attributes data:

+ 'variable': name of the data set
+ 'date': that was used to produce the report
+ 'count': the number of data items
+ 'total': sum of the data items
+ 'average': average of the data items

For example, this Jupyter Lab cell will report energy data by day for the month of June 2023:

```
d = '2023-06-17'
result=f.get_report('month', d=d)
```

# PV Output
These functions produce CSV data for upload to [pvoutput.org](https://pvoutput.org) including PV generation, Export, Load and Grid consumption by day in Wh. The functions use the energy estimates created from the raw power data (see above). The estimates include PV energy generation that are not otherwise available from the Fox Cloud. Typically, the energy results are within 3% of the values reported by the meters built into the inverter.

Time Of Use (TOU) is applied to the grid import and export data, splitting the energy data into off-peak, peak and shoulder categories.

```
f.date_list(s, e, limit, today)
```

+ returns a list of dates from s to e inclusive
+ dates are in the format 'YYYY-MM-DD'
+ will not return dates in the future
+ limit is optional and sets the maximum number of days. The default is 200
+ today = True is optional and sets the latest date to today instead of yesterday

## Get PV Output Data

Returns CSV upload data using the [API format](https://pvoutput.org/help/api_specification.html#csv-data-parameter):

```
f.get_pvoutput(d, tou)
```

+ d is the start date with the format 'YYYY-MM-DD'. The default is yesterday
+ tou controls time of use. Set to 0 to remove time of use from the upload data
+ copy this data to the pvoutput data CSV Loader, using the following settings:

![image](https://github.com/TonyM1958/FoxESS-Cloud/assets/63789168/21459cdc-a943-4e9d-a204-7efd45a422d8)

For example, this Jupyer Lab cell will provide a CSV data upload for June 2023:

```
for d in f.date_list('2023-06-01', '2023-06-30'):
    print(f.get_pvoutput(d, tou=1))
```
+ if you have more than 1 inverter, you will need to call get_device(sn='xxxxx') to select the correct device first.

## Set PV Output Data

Loads CSV data directly using the PV Ouput API:

```
f.set_pvoutput(d, tou, system_id, today)
```

+ d is optional and is the date to upload in the format 'YYYY-MM-DD'. For default, see today below
+ tou is optional and controls time of use calculation. Set to 0 to disable time of use in the upload data. The default is 1
+ system_id is optional and allow you to select where data is uploaded to (where you have more than 1 registered system)
+ today = True is optional and sets the default day to today. The default is False and sets the default day to yesterday 


## Charge Needed

Uses forecast PV yield data to work out if battery charging from grid is required to deliver the expected consumption for tomorrow. If charging is needed, the charge times are configured. If charging is not needed, the charge times are cleared.

```
f.charge_needed(forecast, annual_consumption, contingency, charge_power, start_at, end_by, force_charge, run_after, efficiency)
```

All the parameters for charge_needed() are optional:
+  forecast: the kWh expected tomorrow. By default, forecast data is loaded from solcast.com.au
+  annual_consumption: the kWh consumption each year, delivered via the inverter. Default is your average consumption of the last 7 days
+  contingency: adds charge to allow for variations in consumption and reduction in battery residual prior to charging. 1.0 is no variation. Default is 1.25 (+25%)
+  charge_power: the kW of charge that will be applied. By default, the power rating is derrived from the inverter model. Set this figure if you have reduced your max charge current
+  start_at: time in hours when charging will start e.g. 1:30 = 1.5 hours. The default is 2 (2am)
+  end_by: time in hours when charging will stop. The default is 5 (5am)
+  force_charge: if set to True, any remaining time between start_at and end_by has force charge set to preserve the battery. If false, force charge is not set
+  run_after: the time in hours when the charge calculation should take place. The default is 20 (8pm). If run before this time, no action will be taken
+  efficiency: conversion factor from PV power or AC power to charge power. The default is 0.95 (95%)

If annual_consumption is provided, the daily consumption is calculated by dividing by 365 and applying seasonality to decrease consumption in the summer and increase it in winter. The weighting can be adjusted using a list of 12 values for the months Jan, Feb, Mar etc. The sum of the list values should be 12.0. The default setting is:

```
f.seasonality = [1.1, 1.1, 1.0, 1.0, 0.9, 0.9, 0.9, 0.9, 1.0, 1.0, 1.1, 1.1]
```

If annual_consumption is not provided, an estimate will be calcuated from the average of the last 7 days consumption.

## Version Info

0.2.x: added charge_needed() and merged solcast forcast<br>
