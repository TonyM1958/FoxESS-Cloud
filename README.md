# FoxESS-Cloud
This site contains sample python code for accessing the Fox cloud data via the REST API used by the Fox ESS Cloud web site and app.
There is also a Jupyter Lab notebook with examples of how to run the sample code.

## Setup
Access to the cloud data requires your username and password. These are stored in the file private.py (not uploaded).
To create private.py, copy template_private.py, enter your credentials into the file and save the file as private.py so it can be loaded by the sample code.

To run the code, you will need to install the python libraries: json, datetime, requests, hashlib and random_user_agent.

## Site, Logger and Device Information
Load information about a site, data logger or inverter (device):

```
get_site()
get_logger()
get_device()
```

By default, this will load the first item in the list provided by the cloud.

If there is more than 1 item, the call will show the list of items. To select a specific item to work with, call a qualifier:
+ Site: full or partial name of the site
+ Logger: full or partial serial number
+ Inverter: full or partial serial number

When an item is selected, the functions returns a dictionary containing item details. For an inverter, a list of variables that can be used with the device is also loaded and stored as raw_vars

Once an inverter is selected, you can make other calls to get information:

```
get_firmware()
get_battery()
get_settings()
get_charge()
get_min()
get_work_mode()
get_earnings()

```
Each of these calls will return a dictionary containing the relevant information.

get_firmware() returns the current inverter firmware versions. The result is stored as firmware.

get_battery() returns the current battery status, including soc, voltage, current, power, temperature and residual energy. The result is stored as battery.

get_settings() will return the battery settings and is equivalent to get_charge() and get_min(). The results are stored in battery_settings. The settings include minSoc, minGridSoc, enable charge from grid and the time periods.

get_work_mode() returns the current work mode. The result is stored in work_mode.

get_earnings() returns the power generated and earning data that is displayed on the Fox web site and in the app.

## Inverter Settings
You can change inverter settings using:

```
set_min()
set_charge()
set_work_mode(mode)
```

set_min() takes the min_soc settings from battery_settings and applies these to the inverter.

set_charge() takes the charge times from the battery_settings and applies these to the inverter.

set_work_mode(mode) takes a work mode as a parameter and sets the inverter to this work mode. Valid work modes are held in work_modes. The new mode is stored in work_mode.

## Raw Data
Raw data reports inverter variables, collected every 5 minutes, on a given date / time and period:

```
get_raw(time_span, d, v, energy)
```

+ time_span determines the period covered by the data, for example, 'hour' or 'day'
+ d is a text string containing a date and time in the format 'yyyy-mm-dd hh:mm:ss'
+ v is a variable, or list of variables
+ energy is optional - see following section.

The list of variables that can be queried is stored in raw_vars. There is also a pred-defined list power_vars that lists the main power values provided by the inverter.

For example, this Jupyter Lab cell will load an inverter and return power data at 5 minute intervals for the 17th June 2023:

```
import foxess as f
f.get_device()
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
get_report(report_type, d, v)
```
+ report_type sets the period covered by the report and is one of 'day', 'month', 'year'. When 'day' is selected, energy is reported each hour through the day; when 'month' is selected, energy is reported each day through the month; when 'year' is selected, energy is reported each month through the year. Note that reporting by 'day' does not produce accurate data so it is advised to report by month and select the day required to get an accurate report of total energy for a specific day
+ d is a text string containing a date and time in the format 'yyyy-mm-dd hh:mm:ss'
+ v is a variable, or list of variables. The default is to all report_vars

The list of variables that can be reported on is stored in report_vars.

For example, this Jupyter Lab cell will report energy data by day for the month of June 2023:

```
import foxess as f
f.get_device()
d = '2023-06-17 00:00:00'
result=f.get_report('month', d=d)
```

# PV Output
These functions produce CSV data for upload to [pvoutput.org](https://pvoutput.org) including PV generation, Export, Load and Grid consumption by day in Wh. They operate by getting the raw power data for a day (5 minute samples, or 288 values per variable, per day) and integrating kW to get an overall kWh energy value for that day. This approximation is required as the Fox Cloud API does not expose the PV energy generation. Typically, the results are within 4% of the values reported by the energy meters built into the inverter.

You can also apply Time Of Use (TOU) to the grid import and export data - this splits the data into time periods: off-peak is 02:00 to 05:00, peak is 16:00 to 19:00. Energy use outside these periods are allocated as to the 'shoulder' category.

```
date_list(s,e)
```

+ returns a list of dates from s to e inclusive
+ dates are in the format 'YYYY-MM-DD'
+ will not return dates in the future
+ limits the overall number of days to 200

## Get PV Output Data

Returns CSV upload data using the [API format](https://pvoutput.org/help/api_specification.html#csv-data-parameter):

```
get_pvoutput(d, tou)
```

+ d is the start date with the format 'YYYY-MM-DD'. The default is yesterday
+ tou controls time of use. Set to 0 to remove time of use from the upload data
+ copy this data to the pvoutput data CSV Loader, using the following settings:

![image](https://github.com/TonyM1958/FoxESS-Cloud/assets/63789168/21459cdc-a943-4e9d-a204-7efd45a422d8)

For example, this Jupyer Lab cell will provide a CSV data upload for June 2023:

```
import foxess as f
for d in f.date_list('2023-06-01', '2023-06-30'):
    print(f.get_pvoutput(d, tou=1))
```
+ if you have more than 1 inverter, you will need to call get_device(sn='xxxxx') to select the correct device first.

## Set PV Output Data

Loads CSV data directly using the PV Ouput API:

```
set_pvoutput(d, tou, system_id)
```

+ d is the start date with the format 'YYYY-MM-DD'. The default is yesterday
+ tou controls time of use. Set to 0 to remove time of use from the upload data
+ system_id is optional and allows you to select the system data is uploaded to (where you have more than 1 registered system)

