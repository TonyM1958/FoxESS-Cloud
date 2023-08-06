# FoxESS-Cloud
This site contains sample python code for accessing the Fox cloud data via the REST API used by the Fox ESS Cloud web site and app.
There is also a Jupyter Lab notebook with examples of how to run the sample code.

## Setup
Access to the cloud data requires your username and password. These are stored in the file private.py (not uploaded).
To create private.py, copy template_private.py, enter your credentials into the file and save the file as private.py so it can be loaded by the sample code.

To run the code, you will need to install the python libraries: json, datetime, requests, hashlib and random_user_agent.

## Device Information
To start, you will need to load a device:

```
get_device()
```

By default, this will load the first device in the list of devices provided by the cloud.
If there is more than 1 device, this call will show the list of devices.
To select a specific device to work with, call get_device with the index of the device e.g. get_device(1)

When a device is selected, this call returns a dictionary containing the device details.

A list of variables that can be used with the device is also loaded and stored as raw_vars

Once a device is loaded, you can make other calls to get information:

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
get_raw(time_span, d, v)
```

+ time_span determines the period covered by the data, for example, 'hour' or 'day'
+ d is a text string containing a date and time in the format 'yyyy-mm-dd hh:mm:ss'
+ v is a variable, or list of variables

The list of variables that can be queried is stored in raw_vars. There is also a pred-defined list power_vars that lists the main power values provided by the inverter.

For example, this Jupyter Lab cell will load an inverter and return power data at 5 minute intervals for the 17th June 2023:

```
import foxess as f
f.get_device()
d = '2023-06-17 00:00:00'
result=f.get_raw('day', d=d, v=f.power_vars)
```

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

## PV Output
Produces a CSV data for upload to pvoutput.org including PV generation, Export, Load and Grid consumption by day in Wh. It operates by getting the raw data for a day and integrating this to get an overall energy value for that day. This approximation is required as the Fox Cloud API does not expose the PV energy generation.

```
get_pvreport(s,n,v)
```
+ s is the start date with the format 'yyyy-mm-dd'. The default is yesterday
+ n is the number of days to report. The default is 1
+ v are the variables to report - the default variables are stored in pvoutput_vars

The results are reported in kWh.

For example, this Jupyer Lab cell will provide a CSV data upload for June 2023:

```
import foxess as f
f.get_device()
f.get_pvoutput('2023-06-01', 30)
```
