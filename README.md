# FoxESS-Cloud
This site contains sample python code for accessing the Fox cloud data via the REST API used by the Fox ESS Cloud web site and app.
There is also a Jupyter Lab notebook with examples of how to run the sample code.

**This project is not endorsed by, directly affiliated with, maintained, authorized, or sponsored by Fox ESS.**
Please refer to the [LICENCE](https://github.com/TonyM1958/FoxESS-Cloud/blob/main/LICENCE) for information on copyright, permissions and warranty.

# Cloud API

## Setup
To initialise a Jupyter Lab notebook to use the cloud API, copy the following text and edit the configuration variables needed to add your values:

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
```

You don't have to configure all of the settings. Your Fox ESS Cloud username, password and device serial number are the minimum required to access data about your inverter.

For example, replace _my.fox_username_ with the login name and _my.fox_password_ with the password you use for [foxesscloud.com](https://www.foxesscloud.com/login) and _my.device_sn_ with the serial number of your inverter. Be sure to keep the double quotes around the values you enter or you will get a syntax error.

Advanced users: use the same sequence in bash/python scripts to install modules and initialise variables in a run time enviromment.

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
f.get_raw(time_span, d, v, summary, save, load, plot)
```

+ time_span determines the period covered by the data, for example, 'hour', 'day' or 'week'. The default is 'hour'
+ d is a date and time in the format 'YYYY-MM-DD HH:MM:SS'. The default is today's date and time. d may also be a list of dates
+ v is a variable, or list of variables (see below)
+ summary is optional - see below
+ save: set to the root part of a filename to save the results
+ load: set to the full filename to load previously saved results
+ plot is optional. 1 plots the results with a chart per unit and per day. 2 plots multiple days on the same chart. Default is 0, no plots

The list of variables that can be queried is stored in raw_vars. There is also a pred-defined list power_vars that lists the main power values provided by the inverter. Data generation for the full list of raw_vars can be slow and return a lot of data, so it's best to select the vars you want from the list if you can.

For example, this Jupyter Lab cell will load an inverter and return power data at 5 minute intervals for the 17th June 2023:

```
d = '2023-06-17 00:00:00'
result=f.get_raw('day', d=d, v=f.power_vars)
```

Setting the optional parameter 'summary' when calling get_raw() provides a summary of the raw data

+ summary = 0: basic raw_data, no summary
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
+ kwh_off: the total energy consumed or generated during the off-peak time of use
+ kwh_peak: the total energy consumed or generated during the peak time of use
+ kwh_neg: the total energy from -ve power flow (all other totals are based on +ve power flow)

## Report Data
Report data provides information on the energy produced by the inverter, battery charge and discharge energy, grid consumption and feed-in energy and home energy consumption:

```
f.get_report(report_type, d, v, summary, save, load, plot)
```
+ report_type sets the period covered by the report and is one of 'day', 'week', 'month', 'year':
+ when 'day' is selected, energy is reported each hour through the day
+ when 'week' is selected, energy is reported for the 7 days up to and including the date
+ when 'month' is selected, energy is reported each day through the month
+ when 'year' is selected, energy is reported each month through the year
+ d is a date and time in the format 'YYYY-MM-DD HH:MM:SS'. The default is yesterday. d may also be a list of dates
+ v is a variable, or list of variables. The default is to use report_vars
+ summary is optional - see below
+ save: set to the root part of a filename to save the results
+ load: set to the full filename to load previously saved results
+ plot is optional. 1 to plot results

The list of variables that can be reported on is stored in f.report_vars.

Note that reporting by 'day' produces inaccurate hourly data, where the sum does not reconcile with the daily total given in the monthly report. To correct this, reporting by day also gets the monthly data and uses the daily total to correctly report the total.

Setting the optional parameter 'summary' when calling get_report() provides a summary of the report data:

+ summary = 0: basic report data, no summary. report_type cannot be 'week'
+ summary = 1: summary is calculated
+ summary = 2: corrected total only is reported to save time / space. report_type must be 'day'

The result data for each variable includes the following attributes when summary=2
+ 'variable': name of the data set
+ 'total': corrected total of the data items

When summary=1, the following items are also added:

+ 'data': 'index' and 'value' of each data point
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
f.charge_needed(forecast, annual_consumption, contingency, force_charge, charge_current, discharge_power, export_limit, run_after, update_setings)
```

All the parameters are optional:
+ forecast: the kWh expected tomorrow (optional, see below)
+ annual_consumption: your kWh consumption each year (optional, see below)
+ contingency: allows for variations in your consumption. 0% is no variation. Default is 20%
+ force_charge: if set to 1, any remaining time in a charge time period has force charge set to preserve the battery. If 0, force charge is not set
+ charge_current: the maximum charge current that will be applied. By default, this is worked out from your inverter model. Set this if have changed your maximum charge current
+ discharge_power: the maximum battery discharge power. By default, this is worked out from your inverter model
+ export_limit: set this if the inverter has an export limit. By default, this is set to the power rating of the inverter model
+ run_after: the time in hours when the charge calculation should take place. The default is 22 (10pm). You can set run_after=0 to force forecast to be fetched
+ update_settings: 1 allows charge_needed to update inverter settings. The default is 0
+ show_data: 1 show battery SoC data, 2 show battery Residual data. The default is 1.
+ show_plot: 1 plot battery SoC data. 2 plot battery Residual, Generation and Consumption. 3 plot 2 + Charge and Discharge The default is 0.

### Modelling

charge_needed() uses a number of models to better estimate the state of the battery.

**Manual Consumption:** You can provide your 'annual_consumption' in kWh e.g. 5500. This figure is factored down to a daily consumption by dividing by 365 and applying **f.seasonality**. This normally decreases consumption in the summer and increases it in winter. Seasonality is a list of weightings by month for Jan, Feb, Mar, Apr etc. Preset lists are 'f.high_seasonality' (recommend where electric heating is ued), 'f.medium_seasonality' (default) amd 'f.no_seasonality' (all months the same). The daily consumption is profiled by hour using **f.daily_consumption**. This maps your consumption for a day to the hours when more or less energy is consumed. It is a list of 24 values for the times 00, 01, 02, 03 .. 23. Preset lists are 'f.high_profile' (larger peaks at 8am and 6pm), 'f.medium_profile' (default, more balanced) and 'f.no_profile' (flat).

**Historic Consumption:** If annual_consumption is not provided, your consumption history is used. By default, this looks at your average consumption for the last 3 days using the load power reported by your inverter. For systems with multiple inverters where CT2 is not connected, the load power may not be correct. For this and other cases where you want to set your consumption, provide your annual_consumption.

**Manual Forecast:** You can provide a specific 'forecast' in kWh e.g. 20. This is profiled using **f.seasonal_sun** to map solar generation to the time of day. The mapping is broken down into 4 seasons: winter, spring, summer and autumn (winter is Dec, Jan, Feb, spring is Mar, Apr, May etc). There are 4 preset lists: 'f.winter_sun', 'f.spring_sun', 'f.summer_sun' and 'f.autumn_sun'. Seasonal_sun is used for manual and historic forecasts

**Solcast:** If you provide an API key for Solcast, your forecast will be downloaded after 9pm each day and used as the basis for your next days generation (see below).

**Solar:** if you configure one or more **f.solar_array**, forecast.solar will be called to provide a forrecast for your next days generation (see below).

**Historic Generation:** If 'forecast' is not provided and Solcast and Solar forecasts are not available, your generation history is used. By default, this looks at your average solar generation for the last 3 days and applies the **f.seasonal_sun** profile.

Note: if using Solcast or forecast.solar, calls to the API are very limited so repeated calls to charge_needed can exhaust the calls available, resulting in failure to get a forecast. It is recommended that charge_needed is scheduled to run once between 8pm and midnight to update the charging schedule. Running at this time gives a better view of the residual charge in the battery after charging from solar has finished for the day and peak early evening consumption is tailing off.


Given the data available, the modelling works as follows:
+ gets current information on your battery
+ estimates your consumption (including contigency)
+ gets forecast data from Solcast or forecast.solar (if configured)
+ gets your generation history
+ uses the charge available now and the expected charging or discharging of the battery to forecast the battery state
+ works out if there is a deficit (i.e. when the battery would be discharged below your min_soc)
+ reports the charge needed (deficit) or the minimum expected battery level
+ updates your battery charge settings (if update_settings=1)

## Date Ranges

```
f.date_list(s, e, limit, span, today)
```

Returns a list of dates in the format 'YYYY-MM-DD'. This function will not return dates in the future. The last date will be yesterday or today (if today is True). All parameters are optional:

+ s: start date
+ e: end date
+ limit: maximum number of days. The default is 200
+ span: the range of dates. One of 'day', 'week', 'month' or 'year', '2days' or 'weekday'
+ today: 1 allows today to be included, 2 allows future dates to be included. Default is 0, date list will stop at yesterday

You can use 'span' as follows:
+ 'day' provides a single day
+ 'week' will provide the dates of 7 consequetive days
+ 'month' will provide the dates of the days up to the same date in the preceeding (or follwing) month
+ '2days' will provide the dates of yesterday and today
+ 'weekday' will provide the dates of the same day of the week, going backwards (or forwards) up to 7 weeks

## Tariffs

Tariffs configure when your battery can be charged and provide time of use (TOU) periods to split your grid import and export into peak, off-peak and shoulder times when data is uploaded to PV Ouptut.

There are a number of different pre-configured tariffs:
+ f.octous_flux: charging from 02:00 to 05:00, off-peak from 02:00 to 05:00, peak from 16:00 to 19:00
+ f.intelligent_octopus: charging from 23:30 to 05:00. off-peak from 23:30 to 05:30
+ f.octopus_cosy: charging from 04:00 to 07:00, off-peak from 04:00 to 07:00 and 13:00 to 16:00, peak from 16:00 to 19:00
+ f.octopus_go: charging from 00:30 to 04:30, off peak from 00:30 to 04:30

Custom periods can be configured for specific times if required:
+ f.custom_periods: charging from 02:00 to 05:00, no off-peak or peak times

A list of the tariffs is held in f.tariff_list

The active tariff in configured in 'f.tariff'. The default setting is:

```
f.tariff = f.octopus_flux
```

Note: when TOU is applied, energy values uploaded to PV Output are estimated using the Riemann sum of the 5 minute power values over a day. This means the results vary by up to 10% from the daily totals reported without time of use.

Time period settings are held as decimal hours. Functions are available to convert time strings with the format 'HH:MM:SS' to decimal hours and back are:

```
f.time_hours(s, d)                          # convert time to decimal hours. d is the default value if s is None
f.hours_time(h, ss)                         # convert decimal hours to time
f.hours_in(h, {'start': a, 'end': b})       # True if decimal hour h is in the time period a -> b
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

# Solar Forecasting

# Solcast

Get and display solar data from your solcast.com account using your API key:

```
f.solcast_api_key = "my.solcast_api_key"
fcast = f.Solcast()
print(fcast)
fcast.plot_daily()
fcast.plot_hourly()
```

Returns a 7 day forecast. Optional parameters are:
+ days: number of days to get. The default is 7
+ estimated: whether to get history / estimated data. 1 = yes, 0 = no. Default is 0.
+ reload: cached data handling. 0 = use saved data, 1 = fetch new data, 2 = use saved data for today (default)
+ quiet: True to stop Solcast producing progress messages

Forecast data is saved to f.solcast_save. The default is 'solcast.txt'.

# Forecast.solar

Get and display solar data from forecast.solar:

```
f.solar_array('South', lat=51.1789, lon=-1.8262, kwp=6.4)
fcast = f.Solar()
print(fcast)
fcast.plot_daily()
fcast.plot_hourly()
```

Returns a forecast for today and tomorrow. Optional parameters are:
+ reload: cached data handling. 0 = use saved data, 1 = fetch new data, 2 = use saved data for today (default)
+ quiet: set to True to stop Solar producing progress messages

Forecast data is saved to f.solar_save. The default is 'solar.txt'.

You need to configure your solar arrays by calling f.solar_array(). This takes the following parameters:
+ name: the name of each of your arrays
+ lat: the latitude where the array is located. The default is Stonehenge.
+ lon: the longitude where the array is located. The default is Stonehenge.
+ dec: the declination of the array - 0 is lying flat and 90 is vertical. Default is 30
+ az: azimuth of the array. 0 is pointing due South, -90 is pointing East, 90 is pointing West. The default is 0
+ kwp: the size of the array in kWp. The default is 5kWp
+ dam: damping factor. Default is None
+ inv: inverter power limit (when the array will clip). The default is None
+ hor: a list of values describing obstructions on the horizon

Add one array for each string attached to your inverter. If your solar production is limited by clipping, set the inverter power so the forecast better matches your generation..

See the [API documentation](https://doc.forecast.solar/api) for more information on parameter values.


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

0.5.1: Added discharge limit. Correction of load values from Fox after data errors<br>
0.5.0: update charge_needed to profile consumption based on weekly or week-day history<br>
0.4.9: Update get_raw() and get_report() to accept date list and to plot results data via plot_raw() and plot_report().<br>
       Modify get_token() to save and reload token to avoid being rate limited on logins<br>
0.4.8: Fix coding error getting Solcast forecast in charge_needed()
0.4.7: Updated to use forecast data from today / tomorrow and to provide charge_current instead of charge_power<br>
       Charge power is now calculated from the batery voltage.<br>
0.4.6: Updated plot_hourly() to plot all days. Add today=2 to date_list(). Moved charge_needed configuration to charge_config[]<br>
0.4.5: Added more info around charge time, charge added and target SoC. Added min_charge to tariff.<br>
       Added plot_hourly() to forecasts. Added plot for battery SoC and energy<br>
0.4.4: Updated forecasts to provide hourly profile and to use this in charge_needed()<br>
0.4.3: Updated charge_needed to better model battery charge state<br>
0.4.0: Tidy up code around use of CT2 for solar generation with -ve = generation<br>
0.3.9: Updated forecast 'daily' to date/value format. Fixed errors when called from charge_needed<br>
0.3.8: Added max_pv_power check in get_pvoutput of 100kW. Removed checks in get_raw().<br>
       Changed Solcast to load rids instead of manually entering them. Added Solar (forecast.solar)<br>
0.3.7: Updated get_raw() and get_report() to allow save and load of result for diagnostics. Fix max power check in get_raw()<br>
0.3.6: Added max_power_kw check in get_raw() and check exported > generation in get_pvoutput(). Some updates to charge_needed()<br>
0.3.4: updated report_data for quick totals. Boolean parameters accept 0/1 or True/False<br>
0.3.3: Updated Jupyter notebooks and default parameter values. Added preset tariffs and tariff settings for Octopus Flux, Intelligent, Cosy and Go<br>
0.3.2: Added time input in 'HH:MM'. Added get_access(). More information output when running charge_needed and set_pvoutput<br>
0.3.1: Added ability to flip polarity of CT2. Improved data reporting for charge_needed<br>
0.3.0: Added time_span 'week' to raw_data. Added max and max_time to energy reporting. Added max, max_index, min, min_index to report_data.<br>
       Added 7 days average generation and consumption to charge_needed, printing of parameters and general update of progress reporting<br>
0.2.8: Added max and min to get_report(). Adjusted parsing for inverter charge power. Changed run_after to 10pm. Fixed solcast print/ plot<br>
0.2.3: Added charge_needed() and solcast forcast<br>
