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

## Information
Load information about the user, site or device:

```
f.get_info()
f.get_status(station)
```

f.get_info() sets the variable f.info and returns a dictionary containing user information.

f.get_status() sets the variable f.status and returns a dictionary containing status information for devices (station=0) or sites (station=1).

## Site, Logger and Device Information
Load information about a site, data logger or inverter (device):

```
f.get_site()
f.get_logger()
f.get_device()
```

By default, this will load the first item in the list provided by the cloud. If there is more than 1 item, the call will show the list of items. To select a specific item to work with, call a qualifier:
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
f.get_schedule()
f.get_earnings()

```
Each of these calls will return a dictionary containing the relevant information.

get_firmware() returns the current inverter firmware versions. The result is stored as f.firmware.

get_battery() returns the current battery status, including soc, voltage, current, power, temperature and residual energy. The result is stored as f.battery.

get_settings() will return the battery settings and is equivalent to get_charge() and get_min(). The results are stored in f.battery_settings. The settings include minSoc, minGridSoc, enable charge from grid and the time periods.

get_work_mode() returns the current work mode. The result is stored in f.work_mode.

get_schedule() returns the current work mode / soc schedule settings. The result is stored in f.schedule.

get_earnings() returns the power generated and earning data that is displayed on the Fox web site and in the app.

## Inverter Settings
You can change inverter settings using:

```
f.set_min(minGridSoc, minSoc)
f.set_charge(ch1, st1, en1, ch2, st2, en2)
f.set_work_mode(mode)
f.set_schedule(enable, pollcy)
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

set_schedule() configures a list of scheduled work mode / soc changes with enable=1. If called with enable=0, any existing schedules are disabled.
+ pollcy: a list of schedules with start (H/M) and end (H/M) times, work mode and soc values. f.pollcy_item provides an example / template for the structure.

## Raw Data
Raw data reports inverter variables, collected every 5 minutes, on a given date / time and period:

```
f.get_raw(time_span, d, v, summary, save, load, plot, station)
```

+ time_span determines the period covered by the data, for example, 'hour', 'day' or 'week'. The default is 'hour'
+ d is a date and time in the format 'YYYY-MM-DD HH:MM:SS'. The default is today's date and time. d may also be a list of dates
+ v is a variable, or list of variables (see below)
+ summary is optional - see below
+ save: set to the root part of a filename to save the results
+ load: set to the full filename to load previously saved results
+ plot is optional. 1 plots the results with a chart per unit and per day. 2 plots multiple days on the same chart. Default is 0, no plots
+ station is optional. 1 gets data for a site (using f.station_id), 0 gets data for a device (using f.device_id). The default is 0.

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
f.get_report(report_type, d, v, summary, save, load, plot, station)
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
+ station is optional. 1 gets data for a site (using f.station_id), 0 gets data for a device (using f.device_id). The default is 0.

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
f.charge_needed(forecast, force_charge, forecast_selection, forecast_times, update_setings, show_data, show_plot)
```

All the parameters are optional:
+ forecast: the kWh expected tomorrow (optional, see below)
+ force_charge: if set to 1, any remaining time in a charge time period has force charge set to preserve the battery. If 0, force charge is not set
+ forecast_selection: if set to 1, settings are only updated if there is a forecast. Default is 0, generation is used when forecasts are not available
+ forecast_times: a list of hours when forecasts can be obtained
+ update_settings: 0 no changes, 1 update charge time, 2 update work mode, 3 update charge time and work mode. The default is 0
+ show_data: 1 show battery SoC data, 2 show battery Residual data. The default is 1.
+ show_plot: 1 plot battery SoC data. 2 plot battery Residual, Generation and Consumption. 3 plot 2 + Charge and Discharge The default is 3

### Modelling

charge_needed() uses a number of models to better estimate the state of the battery.

**Manual Consumption:** You can provide your 'annual_consumption' in kWh e.g. 5500. This figure is factored down to a daily consumption by dividing by 365 and applying **f.seasonality**. This normally decreases consumption in the summer and increases it in winter. Seasonality is a list of weightings by month for Jan, Feb, Mar, Apr etc. Preset lists are 'f.high_seasonality' (recommend where electric heating is ued), 'f.medium_seasonality' (default) amd 'f.no_seasonality' (all months the same). The daily consumption is profiled by hour using **f.daily_consumption**. This maps your consumption for a day to the hours when more or less energy is consumed. It is a list of 24 values for the times 00, 01, 02, 03 .. 23. Preset lists are 'f.high_profile' (larger peaks at 8am and 6pm), 'f.medium_profile' (default, more balanced) and 'f.no_profile' (flat).

**Historic Consumption:** If annual_consumption is not provided, your consumption history is used. By default, this looks at your average consumption for the last 3 days using the load power reported by your inverter. For systems with multiple inverters where CT2 is not connected, the load power may not be correct. For this and other cases where you want to set your consumption, provide your annual_consumption.

**Manual Forecast:** You can provide a specific 'forecast' in kWh e.g. 20. This is profiled using **f.seasonal_sun** to map solar generation to the time of day. The mapping is broken down into 4 seasons: winter, spring, summer and autumn (winter is Dec, Jan, Feb, spring is Mar, Apr, May etc). There are 4 preset lists: 'f.winter_sun', 'f.spring_sun', 'f.summer_sun' and 'f.autumn_sun'. Seasonal_sun is used for manual and historic forecasts

**Solcast:** If you provide an API key for Solcast, your forecast will be downloaded after 9pm each day and used as the basis for your next days generation (see below).

**Solar:** if you configure one or more **f.solar_array**, forecast.solar will be called to provide a forrecast for your next days generation (see below).

**Historic Generation:** If 'forecast' is not provided and Solcast and Solar forecasts are not available, your generation history is used. By default, this looks at your average solar generation for the last 3 days and applies the **f.seasonal_sun** profile.

Note: if using Solcast or forecast.solar, calls to the API are very limited so repeated calls to charge_needed can exhaust the calls available, resulting in failure to get a forecast. The tariff forecast_times set the hours when forecast data is fetched (see tariffs).

Given the data available, the modelling works as follows:
+ gets current information on your battery
+ estimates your consumption (including contigency)
+ gets forecast data from Solcast or forecast.solar (if configured)
+ gets your generation history
+ uses the charge available now and the expected charging or discharging of the battery to forecast the battery state
+ works out if there is a deficit (i.e. when the battery would be discharged below your min_soc)
+ reports the charge needed (deficit) or the minimum expected battery level
+ updates your battery charge settings (if update_settings is not 0)
+ gets the current work mode and updates this if timed work mode changes are configured

### Configuration Parameters

The following parameters and default values are used to configure charge_needed and may be updated if required using name=value:
+ contingency: 20               # % of consumption to allow as contingency
+ charge_current: None          # max battery charge current setting in A. None uses a value derrived from the inverter model
+ discharge_current: None       # max battery discharge current setting in A. None uses a value derrived from the inverter model
+ export_limit: None            # maximum export power. None uses the inverter power rating
+ discharge_loss: 0.98,         # loss converting battery discharge power to AC
+ pv_charge_loss: 0.95,         # loss converting PV power to battery charge power
+ grid_charge_loss: 0.96,       # loss converting grid AC to battery charge DC
+ battery_loss: 0.95,           # loss converting battery charge into residual
+ operation_loss: 0.07,         # inverter / bms static power consumption kW
+ volt_swing: 4                 # battery voltage % swing from 0% to 100% SoC when discharging
+ volt_overdrive: 1.01          # increase in battery volt when charging (compared with discharging)
+ generation_days: 3            # number of days to use for average generation (1-7)
+ consumption_days: 3           # number of days to use for average consumption (1-7)
+ consumption_span: 'week'      # 'week' = last 7 days or 'weekday' = last 7 weekdays e.g. Saturdays
+ use_today: 21.0               # hour when today's generation and consumption data will be used
+ min_hours: 0.25               # minimum charge time to set (in decimal hours)
+ min_kwh: 1.0                  # minimum charge to add in kwh
+ solcast_adjust: 100           # % adjustment to make to Solcast forecast
+ solar_adjust:  100            # % adjustment to make to Solar forecast
+ forecast_selection: 0         # 1 = only update charge times if forecast is available, 0 = use best available data. Default is 0.
+ annual_consumption: None      # optional annual consumption in kWh. If set, this replaces consumption history
+ time_shift: None              # offset local time by x hours. When None, 1 hour is added in British Summer Time, 0 otherwise
+ force_charge: 0               # 1 = apply force charge for any remaining charge time
+ special_contingency: 40       # contingency for special days when consumption might be higher
+ special_days: ['11-23', '12-25', '12-26', '01-01']
+ full_charge: None             # day of month (1-28) to do full charge or 'daily' or day of week: 'Mon', 'Tue' etc

These values are stored / available in f.charge_config.

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

```
f.british_summer_time(d)                         # 1 if d is in Britsh Summer Time, 0 if not
```

## Time Periods

Times and time period settings are held as decimal hours. Functions for working with time strings with the format 'HH:MM:SS' and decimal hours include:

```
f.time_hours(t, d=None)                          # convert time to decimal hours. t is a time string ('HH:MM' or 'HH:MM:SS'), d is optional and is the default time if s is None
f.hours_time(h, mm=True, ss=False, day=False)    # convert decimal hours to time (HH:MM:SS). mm = include minutes, ss = include seconds, day = include /n for day when hours > 24
f.hours_in(h, {'start': a, 'end': b})            # True if decimal hour h is in the time period a -> b
```

## Tariffs

Tariffs configure when your battery can be charged and provide time of use (TOU) periods to split your grid import and export into peak, off-peak and shoulder times when data is uploaded to PV Ouptut.

There are a number of different pre-configured tariffs:
+ f.octous_flux: off-peak from 02:00 to 05:00, peak from 16:00 to 19:00, forecasts from 22:00 to 23:59
+ f.intelligent_octopus: off-peak from 23:30 to 05:30, forecasts from 22:00 to 23:59
+ f.octopus_cosy: off-peak from 04:00 to 07:00 and 13:00 to 16:00, peak from 16:00 to 19:00, forecasts from 02:00 to 03:59 and 12:00 to 12:59
+ f.octopus_go: off peak from 00:30 to 04:30, forecasts from 22:00 to 23:59
+ f.agile_octopus: off-peak from 02:30 to 05:00 and 12:30 to 14:30, peak from 16:00 to 19:00, forecasts from 12:00 to 12:59 and 22:00 to 23:59

Custom periods can be configured for specific times if required:
+ f.custom_periods: charging from 02:00 to 05:00, no off-peak or peak times, forecasts from 22:00 to 23:59

A list of the tariffs is held in f.tariff_list

The active tariff in configured in 'f.tariff'. The default setting is:

```
f.tariff = f.octopus_flux
```

Note: when TOU is applied, energy values uploaded to PV Output are estimated using the Riemann sum of the 5 minute power values over a day. This means the results vary by up to 10% from the daily totals reported without time of use.

In addition to energy tariffs, the tariff can contain timed work mode changes using the start, end and min_soc to use when changing work mode.


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

0.7.2:<br>
Dynamic battery_loss calculation added.
Updated daylight_saving for change in clocks.
Added calibration variables to get_pvoutput() and adjusted calibration to match HA.
Updated losses from calibration data, reducing battery discharge at night.
Fixed time shifting of date and time e.g. GMT 23:00 today is BST 00:00 tomorrow.
Fixed 'weekday' to use tomorrow instead of today for weekday history.

0.6.9<br>
Fixed problem when Solcast or Solar ran out of API calls and forecast data wasn't handled correctly.
Updated so manual forecast input disables calls to Solcast and Solar to preserve API calls.
Fixed problem with run_after incorrectly enabling forecasts calls when not set to 0.
Added 'forecast_times' as parameter for charge_needed().
Fixed problems with charging window when it does not start on the hour. Updated default contingency to 10%.
Changed update_settings so 1 updates charge times, 2 updates work mode, 3 updates both
Changed charge_needed so it does not update charge settings when forecast_selection=1 and no forecast is available.
Added 'forecast_times' to tariff as a list of hours when a forecast can be fetched that replaces 'solcast_start' / 'solar_start'
Changed 'run_after' so run_after=1 over-rides 'forecast_times' and any other value does not.
Changed 'timed_mode' so it uses 'default_mode' in f.tariff to automatically enable work mode changes.
Added the tariff 'agile_octopus'
Added test_time, test_soc, test_residual and test_charge parameters for simulation of specific scenarios. 
Updated changing work mode so SoC is only checked when changing modes. Updated text output to provide more information.
Updated charge_needed so it will not run less than 15 minutes before during a charge period starts or until it ends. Reworked SoC and residual at end of charging to improve accuracy.
Added test_charge and grid consumption when charing and updated calculations for battery residuals.
Updated data and plots in charge_needed to show residuals with charge added. Removed rounding of internal data but added format to print values.
Added timed work mode changes and automated work mode changes.
Added full_charge setting and check for valid parameter names.
Added special_contingency and special_dates to f.charge_config.
Added station parameter to get_raw() and get_report() to get data for site instead of device

0.5.9:<br>
Tweak calibration for charge time, add battery power / charging indicator to charge_needed().
Added time_shift and daylight_saving to correct time now when running in the cloud
Adjustment and average of forecast / generation. Check for battery temperature. Updated plots for get_report(). Update set_pvoutput exception handling. Changed show_plot to 3 by default.
Updated error handling. Fix default charge current. Improve charge setting message.
Updated handling of settings / contingency for charge_needed(). Added get_schedule / set_schedule.
Handle error when strategy period is active. Fix tou=1 for PV Output.
Added discharge limit. Correction of load values from Fox after data errors.
update charge_needed to profile consumption based on weekly or week-day history.

0.4.9:<br>
Update get_raw() and get_report() to accept date list and to plot results data via plot_raw() and plot_report().
Modify get_token() to save and reload token to avoid being rate limited on logins.
Updated to use forecast data from today / tomorrow and to provide charge_current instead of charge_power.
Charge power is now calculated from the batery voltage.
Updated plot_hourly() to plot all days.
Add today=2 to date_list().
Moved charge_needed configuration to charge_config[].
Added more info around charge time, charge added and target SoC.
Added min_charge to tariff. Added plot_hourly() to forecasts.
Added plot for battery SoC and energy. Updated forecasts to provide hourly profile and to use this in charge_needed().
Updated charge_needed to better model battery charge state. Tidy up code around use of CT2 for solar generation with -ve = generation

0.3.9:<br>
Updated forecast 'daily' to date/value format. Fixed errors when called from charge_needed.
Added max_pv_power check in get_pvoutput of 100kW. Removed checks in get_raw().
Changed Solcast to load rids instead of manually entering them. Added Solar (forecast.solar).
Updated get_raw() and get_report() to allow save and load of result for diagnostics. Fix max power check in get_raw().
Added max_power_kw check in get_raw() and check exported > generation in get_pvoutput(). Some updates to charge_needed().
Updated report_data for quick totals. Boolean parameters accept 0/1 or True/False.
Updated Jupyter notebooks and default parameter values. Added preset tariffs and tariff settings for Octopus Flux, Intelligent, Cosy and Go.
Added time input in 'HH:MM'. Added get_access(). More information output when running charge_needed and set_pvoutput.
Added time_span 'week' to raw_data. Added max and max_time to energy reporting. Added max, max_index, min, min_index to report_data.
Added 7 days average generation and consumption to charge_needed, printing of parameters and general update of progress reporting.

0.2.8:<br>
Added max and min to get_report(). Adjusted parsing for inverter charge power. Changed run_after to 10pm. Fixed solcast print/ plot.
Added charge_needed() and solcast forcast.
