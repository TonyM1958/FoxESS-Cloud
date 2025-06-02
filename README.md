# FoxESS-Cloud

<a href="https://www.buymeacoffee.com/tonym1958" target="_blank"><img src="https://cdn.buymeacoffee.com/buttons/default-orange.png" alt="Buy Me A Coffee" height="41" width="174" align="right"></a>
This site contains sample python code for accessing the Fox cloud data via the REST API.

There is also a number of Jupyter Lab notebooks with examples of how to run the sample code.

This project is not endorsed by, directly affiliated with, maintained, authorized, or sponsored by Fox ESS.

Please refer to the [LICENCE](https://github.com/TonyM1958/FoxESS-Cloud/blob/main/LICENCE) for information on copyright, permissions and warranty.


# Open API

This module builds on the Fox Open API to provide a sample code and utilities that can be used with your inverter and batteries.

+ Information on the API can be found here: [Open API Documentation](https://www.foxesscloud.com/public/i18n/en/OpenApiDocument.html)
+ A list of the error codes used by the API is available here: [Wiki/Error-Codes](https://github.com/TonyM1958/FoxESS-Cloud/wiki/Error-Codes).


## Setup
To initialise a Jupyter Lab notebook to use the open API, copy the following text and edit the configuration variables needed to add your values:

```
!pip install foxesscloud --root-user-action=ignore --quiet
import foxesscloud.openapi as f

# add your info here
f.api_key = "my.fox_api_key"
f.device_sn = "my.fox_device_sn"
f.time_zone = "Europe/London"
f.residual_handling = 1

f.pv_api_key = "my.pv_api_key"
f.pv_system_id = "my.pv_system_id"

f.solcast_api_key = "my.solcast_api_key"

f.plot_file = "plot###.png"
f.pushover_user_key = "my.pushover_user_key"
```

Advanced users: use the same sequence in bash/python scripts to install modules and initialise variables in a run time enviromment.

You don't have to configure all of the settings. Your Fox ESS Cloud api key is the minimum required to access data about your inverter. Your Fox API key is obtained from [foxesscloud.com](https://www.foxesscloud.com/login). Login, go to User Profile, API Management, click Generate API key. Take a copy of the key and save it so you add it to your scripts and notebooks.

For example, replace _my.fox_api_key_ with the API key. Add you inverter serial number if you have more than 1 inverter linked to your account. Be sure to keep the double quotes around the values you enter or you will get a syntax error.

Residual handling configures how battery residual energy reported by Fox is handled:
+ 1: Fox returns the current battery residual energy and battery capacity is calculated using soc
+ 2: Fox returns the current battery capacity and battery residual is calculated using soc

If a value is set for f.plot_file, any charts created will also be saved to an image file:
+ f.plot_file: the file name to use. The file extension determines the format - .png, .pdf or .svg. If you provide just a filename, each chart will over-write the file. The default is None and disables saving.
+ f.plot_no: if the file name contains ###, this will be replaced by 3 digit plot number that increases for each chart created. The default is 0.
+ f.plot_dpi: sets the image resolution. The default is 150. Reducing this value produces smaller, lower resolution images. Increasing this value produces larger, highe resolution images

If you set f.pushover_user_key to your user_key for pushover.net, a summary from set_tariff(), charge_needed(), set_pvoutput() and battery_info() will be sent to your pushover app.

You can set 'f.storage' to a path to save files to a different location such as cloud storage. The default is to use the current working directory.


## User info
Return information about the current user:

```
f.get_access_count()
```

Returns the 'total' number of API accesses allowed per day and the number of API accesses 'remaining' today.


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

When an item is selected, the functions returns a dictionary containing item details and saves these to a global variable (f.site, f.logger, f.device respectively)

Once an inverter is selected, you can make other calls to get information:

```
f.get_generation()
f.get_battery(info, rated, count)
f.get_batteries(info, rated, count)
f.get_settings()
f.get_charge()
f.get_min()
f.get_flag()
f.get_schedule()
f.get_named_settings(name)

```
Each of these calls will return a dictionary or list containing the relevant information.

get_generation() will return the latest generation information for the device. The results are also stored in f.device as 'generationToday', 'generationMonth' and 'generationTotal'.

get_battery() / get_batteries() returns the current battery status, including 'soc', 'volt', 'current', 'power', 'temperature' and 'residual'. The result also updates f.battery / f.batteries.
get_batteries() returns multiple batteries (if available) as a list. get_battery() returns the first battery. Parameters:
+ 'info': get battery serial number info, if available. Default 0 (not available via Open API)
+ 'rated': optional rated capacity for the battery in Wh to work out SoH. If not provided, it will try to work this out.
+ 'count': optional battery count. If not provided, it will try to work this out.

Additional battery attributes provided include:
+ 'capacity': the estimated battery capacity, derrived from 'residual' and 'soc'
+ 'charge_rate': the estimated BMS charge rate available, based on the current 'temperature' of the BMS
+ 'charge_loss': the ratio of the kWh added to the battery for each kWh applied during charging
+ 'discharge_loss': the ratio of the kWh available for each kWh removed from the battery during during discharging

get_settings() will return the battery settings and is equivalent to get_charge() and get_min(). The results are stored in f.battery_settings. The settings include minSoc, minSocOnGrid, enable charge from grid and the charge times.

get_flag() returns the current scheduler enable / support / maxsoc flags. By default support for Max Soc is set to False.

get_schedule() returns the current work mode / soc schedule settings. The result is stored in f.schedule.
+ if the schedule returned contains any values for 'maxSoc', the f.schedule['maxsoc'] is set to True to indicate that the current inverter supports setting Max Soc in schedules and Max Soc values are set by set_schedule().

get_named_settings() returns the value of a named setting. If 'name' is a list, it returns a list of values.
+ f.named_settings is updated. This is dictionary of information and current value, indexed by 'name'.
+ named_settings current supported include: ExportLimit, MinSoc, MinSocOnGrid, MaxSoc, GridCode


## Inverter Settings
You can change inverter settings using:

```
f.set_min(minSocOnGrid, minSoc)
f.set_charge(ch1, st1, en1, ch2, st2, en2, enable)
f.set_period(start, end, mode, min_soc, max_soc, fdsoc, fdpwr, price, segment)
f.charge_periods(st0, en0, st1, en1, st2, en2, min_soc, target_soc, start_soc)
f.set_schedule(periods, enable)
f.set_named_settings(name, value, force)
```

set_min() applies new SoC settings to the inverter. The parameters update battery_settings:
+ minSocOnGrid: min Soc on Grid setting e.g. 15 = 15%
+ minSoc: min Soc setting e.g. 10 = 10%

set_charge() takes the charge times from the battery_settings and applies these to the inverter. The parameters are optional and will update battery_settings. You should specify all 3 parameter for a time period:
+ ch1: enable charge from grid for period 1 (default True)
+ st1: the start time for period 1 (default 0)
+ en1: the end time for period 1 (default 0)
+ ch2: enable charge from grid for period 2 (default True)
+ st2: the start time for period 2 (default 0)
+ en2: the end time for period 2 (default 0)
+ enable: set to 0 to show settings but stop inverter settings being updated. Default is 1.

set_period() returns a period structure that can be used to build a list for set_schedule()
+ start, end, mode: required parameters. end time is exclusive e.g. end at '07:00' will set a period end time of '06:59'
+ min_soc: optional, default is 10
+ max_soc: optional, default is 100
+ fdsoc: optional, default is 10. Used when setting a period with ForceDischarge mode
+ fdpwr: optional, default is 0. Used when setting a period with ForceDischarge mode
+ price: optional, default None. Used to display plunge pricing for time period.
+ enable: sets whether this time segment is enable (1) or disabled (0). The default is enabled.
+ segment: optional, allows the parameters for the period to be passed as a dictionary instead of individual values.

charge_periods(): returns a list of periods that describe the strategy for the current tariff and adds the periods required for charging:
+ st0: the start time for period 0 when you don't want the battery to discharge before charging
+ en0: the end time for period 0
+ st1: the start time for the period when the battery charges from the grid
+ en1: the end time for period 1
+ st2: the start time for period 2 when you don't want the batteru to discharge after charging
+ en2: the end time for period 2
+ min_soc: the min_soc to use when building the strategy
+ start_soc: the min_soc to use for period 0
+ target_soc: the max_soc to set during period 1 and min_soc to use for period 2

set_schedule() configures a list of scheduled work mode / soc changes with enable=1. If called with enable=0, any existing schedules are disabled. To enable a schedule, you must provide a list of time segments
+ periods: a time segment or list of time segments created using f.set_period().
+ enable: 1 to enable schedules, 0 to disable schedules. The default is 1.

set_named_settings() sets the 'name' setting to 'value'.
+ 'name' may also be a list of (name, value) pairs.
+ 'force': setting to 1 will disable Mode Scheduler, if enabled. Default is 0.
+ a return value of 1 is success. 0 means setting failed. None is another error e.g. device not found, invalid name or value.
+ named_settings current supported include: ExportLimit, MinSoc, MinSocOnGrid, MaxSoc, GridCode


## Real Time Data
Real time data reports the latest values for inverter variables, collected every 5 minutes:

```
f.invert_ct2 = 1
f.get_vars()
f.get_real(v)
```

f.invert_ct2 determines how the meterPower2 data is handled. When invert_ct2 = 0, meterPower2 produces +ve power values during secondary generation. If meterPower2 produces -ve power values during secondary generation, setting invert_ct2 = 1 will flip the values so they are +ve when generating. The default setting is 1 (invert).

f.get_vars() returns the list of variables that can be queried. This also stores the information:
+ f.var_table: a table, indexed by variable that contains information such as the name and unit.
++ f.var_list: a list of all the variables that are available

There are also pre-defined lists:
+ power_vars lists the main power variables provided by the inverter
+ battery_vars lists the main variables relevant to the battery / BMS

f.get_real returns the latest values for a list of variables.
+ v is a variable, or list of variables. The default is to return the latest value for all available variables


## History Data
History data reports inverter variables, collected every 5 minutes, on a given date / time and period:

```
f.get_history(time_span, d, v, summary, save, load, plot)
```

+ time_span determines the period covered by the data, for example, 'hour', 'day' or 'week'. The default is 'hour'
+ d is a date and time in the format 'YYYY-MM-DD HH:MM:SS'. The default is today's date and time. d may also be a list of dates
+ v is a variable, or list of variables (see above)
+ summary is optional - see below
+ save: set to the root part of a filename to save the results
+ load: set to the full filename to load previously saved results
+ plot is optional. 1 plots the results with a chart per unit and per day. 2 plots multiple days on the same chart. Default is 0, no plots

The setting for invert_ct2 is applied to history data for meterPower2, so +ve values are returned for secondary generation.

f.sample_time is set to the sample time in minutes for the data processed, rounded to f.sample_rounding samples per minute.

Data generation for the full list of raw_vars can be slow and return a lot of data, so it's best to select the vars you want from the list if you can.

For example, this Jupyter Lab cell will load an inverter and return power data at 5 minute intervals for the 17th June 2023:

```
d = '2023-06-17 00:00:00'
result=f.get_history('day', d=d, v=f.power_vars)
```

Setting the optional parameter 'summary' when calling get_raw() provides a summary of the raw data

+ summary = 0: basic history data, no summary
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

For power values (unit = kW), the summary performs a Riemann sum of the data, integrating kW over the day to estimate energy in kWh. In this case, the following attributes are also added:
+ kwh: the total energy generated or consumed
+ kwh_off: the total energy consumed or generated during the off-peak time of use (off_peak1, off_peak2, off_peak3, off_peak4)
+ kwh_peak: the total energy consumed or generated during the peak time of use (peak1, peak2)
+ kwh_neg: the total energy from -ve power flow (all other totals are based on +ve power flow)

This example shows power graphs for today and yesterday:

![image](https://github.com/TonyM1958/FoxESS-Cloud/assets/63789168/d84c55c9-4f4c-431d-bc55-d7796b7e4fea)


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

This example plots weekly data:

![image](https://github.com/TonyM1958/FoxESS-Cloud/assets/63789168/f408a010-9600-4b2f-979f-83e32d960586)


# Built-in Utilities and Operations

The previous section provides functions that can be used to access and control your inverter. This section covers utilities and operations that build upon these functions.

## Charge Needed

Uses forecast PV yield for tomorrow to work out if charging from grid is needed tonight to deliver the expected consumption for tomorrow. If charging is needed, the charge times are configured. If charging is not needed, the charge times are cleared. The results are sent to the inverter.

```
f.charge_needed(forecast, force_charge, forecast_selection, forecast_times, update_setings, show_data, show_plot, timed_mode)
```

All the parameters are optional:
+ forecast: the kWh expected tomorrow (optional, see below)
+ force_charge: 1 any remaining time in a charge period has force charge / min_soc set, 2 charging uses the entire charge period, 0 None (default)
+ forecast_selection: if set to 1, settings are only updated if there is a forecast. Default is 0, generation is used when forecasts are not available
+ forecast_times: a list of hours when forecasts can be obtained. By default, the forecast times for the selected tariff are used (see below)
+ update_settings: 0 no changes, 1 update charge settings. The default is 0
+ show_data: 1 show battery SoC data, 2 show battery Residual data, 3 show timed data. The default is 1.
+ show_plot: 1 plot battery SoC data. 2 plot battery Residual, Generation and Consumption. 3 plot 2 + Charge and Discharge The default is 3
+ timed_mode: 0 use charge times, 1 use charge times and follow strategy, 2 use Mode Scheduler

### Modelling

charge_needed() uses a number of models to better estimate the state of the battery.

**Manual Consumption:** You can provide your expected 'consumption' in kWh e.g. 15. This figure is used directly.

**Annual Consumption:** You can provide your 'annual_consumption' in kWh e.g. 5500. This figure is factored down to a daily consumption by dividing by 365 and applying **f.seasonality**. This normally decreases consumption in the summer and increases it in winter. Seasonality is a list of weightings by month for Jan, Feb, Mar, Apr etc. Preset lists are 'f.high_seasonality' (recommend where electric heating is ued), 'f.medium_seasonality' (default) amd 'f.no_seasonality' (all months the same). The daily consumption is profiled by hour using **f.daily_consumption**. This maps your consumption for a day to the hours when more or less energy is consumed. It is a list of 24 values for the times 00, 01, 02, 03 .. 23. Preset lists are 'f.high_profile' (larger peaks at 8am and 6pm), 'f.medium_profile' (default, more balanced) and 'f.no_profile' (flat).

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
```
contingency: [20,10,5,10]      # % of consumption. Single or [winter, spring, summer, autumn] values
capacity: None                 # Battery capacity in kWh (over-rides generated value if set)
charge_current: None           # max battery charge current setting in A. None uses a value derrived from the inverter model
discharge_current: None        # max battery discharge current setting in A. None uses a value derrived from the inverter model
export_limit: None             # maximum export power in kW. None uses the inverter power rating
dc_ac_loss: 0.970              # loss converting battery DC power to AC grid power
pv_loss: 0.950                 # loss converting PV power to DC battery charge power
ac_dc_loss: 0.960              # loss converting AC grid power to DC battery charge power
charge_loss: None              # loss converting charge energy to stored energy
discharge_loss: None           # loss converting stored energy to discharge energy
inverter_power: None           # inverter power consumption in W (dynamically set)
bms_power: 50                  # BMS power consumption in W
force_charge_power: 5.00       # power used when Force Charge is scheduled
allowed_drain: 4,              # % tolerance below min_soc before float charge starts
float_current: 4,              # BMS float charge current in A
bat_resistance: 0.070          # internal resistance of a battery in ohms
volt_curve: lifepo4_curve      # battery OCV from 0% to 100% SoC
nominal_soc: 55                # SoC for nominal open circuit voltage
generation_days: 3             # number of days to use for average generation (1-7)
consumption_days: 3            # number of days to use for average consumption (1-7)
consumption_span: 'week'       # 'week' = last 7 days or 'weekday' = last 7 weekdays e.g. Saturdays
use_today: 21.0                # hour when today's generation and consumption data will be used
min_hours: 0.25                # minimum charge time to set (in decimal hours)
min_kwh: 0.5                   # minimum charge to add in kwh
solcast_adjust: 100            # % adjustment to make to Solcast forecast
solar_adjust:  100             # % adjustment to make to Solar forecast
forecast_selection: 1          # 1 = only update charge times if forecast is available, 0 = use best available data. Default is 1.
annual_consumption: None       # optional annual consumption in kWh. If set, this replaces consumption history
timed_mode: 0                  # 0 = None, 1 = use timed work mode, 2 = strategy mode
special_contingency: 30        # contingency for special days when consumption might be higher
special_days: ['12-25', '12-26', '01-01']
full_charge: None              # day of month (1-28) to do full charge or 'daily' or day of week: 'Mon', 'Tue' etc
force: 1                       # 1 = disable strategy periods when setting charge. 0 = fail if strategy period has been set.
data_wrap: 6                   # data items to show per line
target_soc: None               # target soc for charging (over-rides calculated value)
shading: {}                    # effect of shading on Solcast / Solar (see below)
save: 'charge_needed.txt'      # where to save calculation data for charge_compare(). '###' gets replaced with todays date.
```

These values are stored / available in f.charge_config.

The default battery open circuit voltage curve versus SoC from 0% to 100% is:
```
lifepo4_curve = [51.30, 52.00, 52.30, 52.40, 52.50, 52.60, 52.70, 52.80, 52.9, 53.1, 53.50]
```

When operating in strategy mode (timed_mode=2), charge_needed will create a schedule that includes the strategy for the tariff with additional time segments added to charge from grid and (optionall) to stop the battery discharging. In other modes, charge_needed() will disable any schedules and set the battery charge times.

This example shows the results reported by charge needed:

![image](https://github.com/TonyM1958/FoxESS-Cloud/assets/63789168/8b77956b-c326-43cd-b165-20d806b1e7e8)


## Charge Compare

Provides a comparison of a prediction, saved by charge_needed(), with the actuals

```
f.charge_compare(save, v, show_data, show_plot)
```

Produces a plot of the saved data from charge_needed() overlaid with data from get_history():
+ 'save': the name of the file to load
+ 'v': the variables to plot. The default is 'pvPower', 'loadsPower' and 'SoC'
+ show_data: 1 show battery SoC data by hour (default)
+ show_plot: 1 plot battery SoC data. 2 plot battery Residual, Generation and Consumption. 3 plot 2 + Charge and Discharge The default is 3


## Battery Info

Provides detailed information on the current state of the batteries:

```
f.battery_info(count, plot, log)
f.battery_monitor(interval, run, log, save, count)
```

battery_info() prints information on the battery and cells:
+ count: optional over-ride. The default is based on factorising the number of cells reported by 16 or 18 to work out the number of batteries.
+ plot: 1 plot the cell voltages for each battery, 2 plot the cell temperatueres, 0 don't plot. The default is 1
+ log: see below. Default is 0

battery_monitor() runs battery_info() in log mode on a schedule to provide information on the battery status over a period of time:
+ interval: the time in minutes between log entries. The default is 30 minutes
+ run: the number of log entries to create. The default is 48 i.e. every 30 minues for 24 hours in total
+ log: 0 = display, 1 = log battery info, 2 = add cell volts, 3 = add cell temps. The default is 1
+ save: name of a CSV file to write log data to
+ count: optional over-ride for the number of batteries

This is an example of the output from battery_info():

![image](https://github.com/TonyM1958/FoxESS-Cloud/assets/63789168/a8eb52b6-ce3f-4b58-bb76-5483d5e40fa7)


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
+ Octopus Flux: off-peak from 02:00 to 05:00, peak from 16:00 to 19:00, forecasts from 22:00 to 23:59. Timed work mode changes to Self Use at 5am and Feed In First at 4pm.
+ Intelligent Octopus: off-peak from 23:30 to 05:30, forecasts from 22:00 to 23:59
+ Octopus Cosy: off-peak from 04:00 to 07:00, 13:00 to 16:00 and 22:00 to 24:00, peak from 16:00 to 19:00, forecasts from 01:00 to 02:59 and 10:00 to 11:59
+ Octopus Go: off peak from 00:30 to 04:30, forecasts from 22:00 to 23:59
+ Agile Octopus: off-peak from 00:00 to 06:00 and 12:00 to 16:00, peak from 16:00 to 19:00, forecasts from 10:00 to 11:59 and 22:00 to 23:59
+ British Gas Electric Driver: off-peak from 00:00 to 05:00, forecasts from 22:00 to 23:59
+ EON Next Drive: off-peak from 00:00 to 07:00, forecasts from 22:00 to 23:59
+ Eco 7: Economy 7: off-peak from 00:30 to 07:30 GMT (01:30 to 08:30 during BST)

Custom periods can be configured for specific times if required:
+ Custom: off-peak from 02:00 to 05:00, peak from 16:00 to 18:59, forecasts from 22:00 to 23:59

The active tariff is configured by calling 'f.set_tariff() with the name of the tariff to use:

```
f.set_tariff('flux')
```

When Agile Octopus is selected, a price based charging period is configured using the 30 minute price forecast. For example:

```
f.set_tariff('agile', product, region, times, forecast_times, strategy, update, weighting, time_shift)
```

This gets the latest 30 minute pricing and uses this to work out the best off peak charging period.
+ product: optional Agile Octopus product code (see below). The default is "AGILE-24-04-03"
+ region: optional region to use for prices (se below). The default is 'H' (Southern England)
+ times: a list of charge periods that can be used instead of start_at, end_by and duration (see below)
+ forecast_times: a list of times when a forecast can be obtained from Solcast / forecast.solar, aligned with the host system time
+ strategy: an optional list of times and work modes (see below)
+ update: optional, 1 (the default) sets the current tariff to Agile Octopus. Setting to 0 does not change the current tariff
+ weighting: optional, default is None / flat (see below)
+ time_shift: optional system time shift in hours. The default is for system time to be UTC and to apply the current day light saving time (e.g. GMT/BST)
+ plunge_price: list of prices in p/kWh when plunge pricing is used (see below). The default is [0, 5].
+ plunge_slots: the number of 30 minute slots to use for plunge pricing. The default is 6, allowing up to 3 hours.
+ show_data: show 30 minute Agile pricing data. Default is 1.
+ show_plot: plot 30 minute Agile pricing data. Default is 1.

Product codes include: 
+ 'AGILE-18-02-21' = The original version capped at 35p per unit
+ 'AGILE-22-07-22' = The cap rose to 55p
+ 'AGILE-22-08-31' = The cap was increased to 78p
+ 'AGILE-VAR-22-10-19' = This version raised the cap to £1 per unit and also introduced a new formula.
+ 'AGILE-FLEX-22-11-25' = Cap stays at £1 per unit but new formula only deducts 17.9p from higher unit prices
+ 'AGILE-24-04-30' = Latest Agile tariff (default)

Region codes include:
+ 'A' = Eastern England
+ 'B' = East Midlands
+ 'C' = London
+ 'D' = Merseyside and Northern Wales
+ 'E' = West Midlands
+ 'F' = North Eastern England
+ 'G' = North Western England
+ 'H' = Southern England (default)
+ 'J' = South Eastern England
+ 'K' = Southern Wales
+ 'L' = South Western England
+ 'M' = Yorkshire
+ 'N' = Southern Scotland
+ 'P' = Northern Scotland

Pricing for tomorrow is updated around 5pm each day. If run before this time, prices from yesterday are used. By default, prices for tomorrow are fetched after 5pm. The setting for this is:
+ f.agile_update_time = 17

The best charging period is determined based on the weighted average of the 30 minute prices over the duration. The default is flat (all prices are weighted equally, except the last slot, which is pro rata to the charge duration used). You can over-ride the default weighting by providing a list of 30 minute values to apply.

set_tariff() can configure multiple off-peak and peak periods for any tariff using the 'times' parameter. Times is a list of tuples:
+ containing values for key, 'start', 'end' and optional 'force'.
+ recongnised keys are: 'off_peak1', 'off_peak2', 'off_peak3', 'off_peak4', 'peak1', 'peak2'
+ a tuple containing a key with no values will remove the time period from the tariff.

For example, this parameter configures an AM charging period between 11pm and 8am and a PM charging period between 12 noon and 4pm and removes the time period 'peak2':
+ times=[("off_peak1", "23:00", "8:00"), ("off_peak2", "12:00", "16:00"), ("peak2")]

'strategy' allows you to configure times when work modes will be changed. The format is a list of dictionary items, containing:
+ 'start', 'end': times in decimal hours or time format. The end time is exclusive so setting an end time of '07:00' will set a schedule that ends at '06:59'
+ 'mode': the work mode to be used from 'SelfUse', 'Feedin', 'Backup', 'ForceCharge', 'ForceDischarge'
+ 'min_soc, 'fdsoc', 'fdpwr' and 'max_soc': optional values for each work mode. The defaults are 10, 10, 0 and 100 respectively.

Alternatively, if you set strategy='load', the current inverter schedule will be loaded and used.

Any strategy time segments that overlap the charge time periods for the tariff will be dropped.

```
f.get_strategy()
```

get_strategy() creates a list of time segments from the strategy. If strategy is not provided, it uses the strategy for the current tariff. If a strategy includes settings for the AM/PM charge times for the tariff, the times will be moved so they do not conflict with the charge time used by charge_needed().

Plunge pricing allows for the automatic configuration of charging periods when Agile prices are low:
+ 'plunge_pricing is a list of prices. If the price for a 30 minute period is below this price, a plunge charging period is added to the schedule. 'plunge_pricing' is a value or list of values. When a list is used, the values are spread over 24 hours starting with the first value at 7am. So, for example, if 2 prices are provided, the first applies between 7am and 7pm and the second applies between 7pm and 7am. This allows different prices to be applied for day-time and night-time. If 3 prices are provided, each covers 8 hours so the time slots are 7am-3pm, 3pm-11pm and 11pm-7am. With 4 prices, each covers 6 hours so the time periods are 7am-1pm, 1pm-7pm, 7pm-1am, 1am-7am etc.
+ 'plunge_slots' sets the maximum number of 30 minute plunge charging slots to use. The default is 6.

# PV Output
These functions produce CSV data for upload to [pvoutput.org](https://pvoutput.org) including PV generation, Export, Load and Grid consumption by day in Wh. The functions use the energy estimates created from the raw power data (see above). The estimates include PV energy generation that are not otherwise available from the Fox Cloud. Typically, the energy results are within 3% of the values reported by the meters built into the inverter.

## Calibration
PV generation data is created using the Riemann sum of the PV power and CT2 power as the history of the stats provided by the Fox cloud can be unreliable. You can change the calibration factors used:

```
f.pv_calibration = 0.98
f.ct2_calibration = 0.92
```
* pv_calibration is a DC calibration factor and is multiplied by the Riemann sum. The default calibration factor of 0.98 was derrived by comparing the total solar production calculated against the inverter generation data provided via Modbus over 12 months

* ct2_calibration is an AC calibration factor and is the divisor for the Riemann sum. CT2 measures the AC power output by the inverter and this factor converts this back to the DC power coming from the solar panels into the inverter, assuming an MPPT efficiency of 95% and DC-AC conversion efficiency of 97%. This aligns the solar panel generation with PV power, allowing the total solar generation from both primary (connected to the hybrid inverter) and secondary (connected via a separate solar inverter) panels to be combined correctly.


## Get PV Output Data

Returns CSV upload data using the [API format](https://pvoutput.org/help/api_specification.html#csv-data-parameter):

```
f.integrate_load_power=0
f.get_pvoutput(d, tou)
```

+ d is the date or a list of dates, to get data for. The default is yesterday.
+ tou: the default, tou=0, does not split data and is more accurate. Setting tou=1 uploads data with time of use. Setting tou=2 integrates all values and allows set_pvoutput() to work with pv inverters that do not provide energy stats.
+ setting integrate_load_power to 1 will calculate load energy by integrating the load power instead of using data from Fox. This tries to overcome the limitation where the inverter does not track load power / energy correctly when there is secondary generation. When set to 0 (default), the  Fox load energy is used.

You can copy and paste the output data to the pvoutput data CSV Loader, using the following settings:

![image](https://github.com/TonyM1958/FoxESS-Cloud/assets/63789168/21459cdc-a943-4e9d-a204-7efd45a422d8)

For example, this Jupyer Lab cell will provide a CSV data upload for June 2023:

```
f.get_pvoutput(f.date_list('2023-06-01', '2023-06-30'))
```

## Set PV Output Data

Loads CSV data directly using the PV Ouput API:

```
f.set_pvoutput(d, system_id, tou, push, run_after)
```

+ d is optional and is the date, or a list of dates, to upload
+ system_id is optional and allow you to select where data is uploaded to (where you have more than 1 registered system)
+ tou: the default, tou=0, does not split data and is more accurate. Setting tou=1 uploads data with time of use. Setting tou=2 integrates all values and allows set_pvoutput() to work with pv inverters that do not provide energy stats.
+ push: optional. 0 = do not sent to pushover, 1 = send summary to pushover, 2 = send first day summary only
+ run_after: optional. Only generate data on or after this hour. Default 0.

# Solar Forecasting

## Solcast

Get and display solar data from your solcast.com account using your API key:

```
f.solcast_api_key = "my.solcast_api_key"
fcast = f.Solcast()
print(fcast)
```

Returns a 7 day forecast. Optional parameters are:
+ days: number of days to get. The default is 7
+ estimated: whether to get history / estimated data. 1 = yes, 0 = no. Default is 0.
+ reload: cached data handling. 0 = use saved data, 1 = fetch new data, 2 = use saved data for today (default)
+ quiet: True to stop Solcast producing progress messages
+ shading: parameters to control shading at the start and end of the day (see Solar Forecasts)

Forecast data is saved to f.solcast_save. The default is 'solcast.txt'.

```
fcast.plot_daily()
fcast.plot_hourly(day)
fcast.plot_pt30(day)
fcast.compare(day, raw, v)
```

Plots the estimate / forecast data. plot_daily() plots the daily yield. plot_hourly() plots each day separately by hour. plot_pt30() plots 30 minute slots.
+ day: optional. 'today', 'tomorrow', 'all' or a specific list of dates. The default is to plot today and tomorrow

compare() will get actual data from your inverter and plot this against the forecast:
+ 'day' is the date to plot (YYYY-MM-DD). The default is today.
+ 'raw' 1 will also plot the raw forecast array (rid) data. Default is 0 (don't plot)
+ 'v' is a list of inverter variables to plot. The default is 'pvPower'

## Forecast.solar

Get and display solar data from forecast.solar for today and tomorrow:

```
f.solar_array('South', lat=51.1789, lon=-1.8262, kwp=6.4)
```

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

Add one array for each string attached to your inverter. If your solar production is limited by clipping, set the inverter power so the forecast better matches your generation.

See the [API documentation](https://doc.forecast.solar/api) for more information on parameter values.

```
fcast = f.Solar()
print(fcast)
```

Returns a forecast for today and tomorrow. Optional parameters are:
+ reload: cached data handling. 0 = use saved data, 1 = fetch new data, 2 = use saved data for today (default)
+ quiet: set to True to stop Solar producing progress messages
+ shading: parameters to control shading at the start and end of the day

Forecast data is saved to f.solar_save. The default is 'solar.txt'.

```
fcast.plot_daily()
fcast.plot_hourly(day)
fcast.plot_pt30(day)
fcast.compare(day, raw, v)
```

Plots the estimate / forecast data. plot_daily() plots the daily yield. plot_hourly() plots each day separately by hour. plot_pt30() plots 30 minute slots.
+ day: optional. 'today', 'tomorrow', 'all' or a specific list of dates. The default is to plot today and tomorrow

compare() will get actual data from your inverter and plot this against the forecast:
+ 'day' is the date to plot (YYYY-MM-DD). The default is today.
+ 'raw' 1 will also plot the raw forecast array (rid) data. Default is 0 (don't plot)
+ 'v' is a list of inverter variables to plot. The default is 'pvPower'

## Sun Times and Shading

Shading reduces the outut of the solar panels due to shadows covering the sun. The forecasts use a simple shading model that allows for reduced generation due to obstacles that obstruct the panels as the sun rise and sets. This is based on 2 structures:

'f.suntimes' is a list of UTC sunrise and sunset times for the 1st day of each month of the year (12 x value pairs). 'f.suntimes' to values that are specific to you. The default values are based on central England:

```
sun_times = [
    ('08:13', '16:07'), ('07:46', '16:55'), ('06:51', '17:48'),     # Jan, Feb, Mar
    ('05:41', '18:41'), ('04:37', '19:31'), ('03:55', '20:15'),     # Apr. May, Jun
    ('03:54', '20:27'), ('04:31', '19:54'), ('05:20', '18:51'),     # Jul, Aug, Sep
    ('06:09', '17:43'), ('07:01', '16:38'), ('07:51', '16:00')]     # Oct, Nov, Dec

f.get_suntimes(date, utc)

'shading': {
        'solcast': {'adjust': 0.95, 'am_delay': 1.0, 'am_loss': 0.2, 'pm_delay': 1.0, 'pm_loss': 0.2},
        'solar':   {'adjust': 1.20, 'am_delay': 1.0, 'am_loss': 0.2, 'pm_delay': 1.0, 'pm_loss': 0.2}
        },
```

'f.get_suntimes' returns the sunrise and sunset times as a tuple for the date provided by interpolating from 'f.sun_times':
+ date: 'YYYY-MM-DD'
+ utc: 1 = return time in UTC. 0 = return local time (default)

'shading' adjusts the forecast and sets delays and losses caused as the sun rise and set for Solcast and Solar. The forecast is multiplied by 'adjust'. The (AM/PM) delay is the time after sunrise or before sunset that is applied and 'loss' is the amount that the solar forecast is reduced. The default structure above is used by Solcast and Solar when called from charge_needed() or they can be passed directly as parameters when forecasts are being created using 'f.Solcast()' and 'f.Solar()'. If the delays are presented as a list, they are values for winter, spring, summer and autumn.


# Pushover

Send messages to a pushover user account:

```
f.output_spool(app_key, h)
f.output(s)
f.output_close(plot, file)
f.output_message(app_key, message, plot)
```

Calling f.output_spool() with an app key will start the system spooling output to send to pushover. h is an optional header to add as the first line of the message. H may include \<time\>, \<date\> or \<datetime\> and these will be set to current system time and date respectively.

When spooling is active, any calls to f.output() add lines to the spooled message. If appending to the message would exceed 1024 characters, the existing spooled message is sent and a new message spool is started.

Calling f.output_close() will send the spooled message and optionally attach a binary image file. You can set plot=1 to attach the last plot file created (when f.plot_file is set) or specify a file.

f.output_message() is a shorcut to send a message without spooling output.


# Troubleshooting

If needed, you can add the following setting to increase the level of information reported by the foxesscloud module:

```
f.debug_setting = 2
```

This setting can be:
+ 0: silent mode (minimal output)
+ 1: information reporting (default)
+ 2: more debug information, updating of inverter settings is disabled
+ 3: internal variables and values are displayed (verbose)


# Version Info

2.8.4<br>
Fix exception when calling pvoutput with tou=1 but no tariff set.

2.8.3<br>
Update to support setting Max Soc in schedules now this is supported by Fox using Open API.

2.8.2<br>
Fix forecast.solar (after change to start parameter processing).
Change logic around battery status so 0 is offline and others values are online.

2.8.1<br>
Update from v0 to v1 for scheduler API.
PVEnergyTotal added to report variables.
Fix residual if capacity is specified for charge_needed().

2.7.9<br>
Add 'consumption' input for charge_needed().
Avoid throwing exception in battery_info() if there is no capacity info.

2.7.8<br>
Update the battery_params charge rate table to 2025 values.

2.7.7<br>
Updates to get_pvoutput() to support solar inverters that don't provide grid energy by setting tou=2.
Default tariff changed to None.

2.7.6<br>
Updates to support F, G, R and S series inverters.
Updates to set_named_settings() to load metadata if not already done and save new value.
Fix divide by zero error when using pvoutput with solar only inverters.

2.7.5<br>
Update to support T series inverters.

2.7.3<br>
Fix divide by zero error if get_report() returns no data.

2.7.2<br>
Fix to get_battery() to return error and flag status=0 in f.battery when the cloud is not returning valid data.
Fix exception calculating SoH if ratedCapacity is returned as 0 when cloud is not returning valid data.
Update charge_rate in charge_needed() to use a blended charge rate based on battery warming up during charging.
Fix exception in set_charge() caused by incorrect default parameter values.
Update charge_needed() to only show forecast that is in use.

2.7.1<br>
Update charge_needed() so it only gets generation history if there is no forecast to reduce API calls and save time.
Update default parameter values for set_charge() so the other time period is cleared if you only set 1 time.
Fix problem where a full charge was being set when charge_needed() is called with force_charge=1.
Move charging to the end of the charge time when force_charge=1 so the charge time completes with the required charge.
Update battery predictions to more accurately reflect what happens when SoC gets to min_soc or fd_soc.
Correct model to use inverter operating losses instead of BMS losses when the battery is above min_soc.
Correct exception in Solcast and Solar when a forecast is not available.

2.7.0<br>
Allow charge_loss / discharge_loss to be configured for charge_needed().
Change 'Force Charge' to 'Battery Hold' in charge times to avoid confusion with Force Charge work mode.
Correct problem with missing periods of actual data in forecast.compare()

2.6.9<br>
Add get and set_named_settings() (for WorkMode and ExportLimit).
If a list of named settings is provided, the return value is a list indicating which settings succeeded (1) or failed (0).
Updates to get_battery() / get_batteries() to add optional rated and count parameters.
Updates to charge_needed() to end prediction at start of next charge period.
Correct charge time for Octopus Go tariff.
Update charge_needed() to show contingency achieved rather than requested.

2.6.8<br>
Add residual_handling=3 for Mira BMS with firmware 1.014 or later that returns residual capacity per battery.
Calculate 'ratedCapacity' in get_battery() and 'soh' for HV2600 and Mira.
Allow unlimited periods in strategy, including overlap with charge periods but warn and limit if the periods sent to inverter would be more than 8.
Improve behaviour prediction for schedules when clocks change due to day light saving.
Improve schedule generation and prediction when Min Soc changes.
Cache Solcast RIDS to reduce API usage (run with reload=1 if arrays are edited and cached RIDs need to be updated).
Remove spurious error message when (failing) to get inverter work mode.

2.6.5<br>
Add get_named_settings() and set_named_settings().
Update get_work_mode() and set_work_mode() to use named settings (still doesn't work though as blocked by Fox)
Updated get_history() and get_report() saved filenames to use _history_ and _report_ for consistency.
Update calibration of 'charge_loss' and 'discharge_loss'.

2.6.4<br>
Increase default plungs_slots from 6 to 8.
Correct battery capacity in get_batteries().

2.6.2<br>
Update battery calibration for charge_needed() when residual_handling is 2.
Update get_battery() and get_batteries() to include states for ratedCapacity, soh, residual_handling and soh_supported.
Update charge_compare(), Solcast() and Solar() so date (d) parameter is more flexible.

2.6.1<br>
Fix problem where battery discharges below min_soc while waiting for charging to start.
Update calibration for Force Charge with BMS 1.014 and later.
Add get_batteries() to return a list of BMS and batteries where inverters support more than 1 BMS.
Update battery_info() to support multiple BMS.
Add rated capacity and SoH to battery info if available.

2.6.0<br>
Rework charge de-rating with temperature, losses and other info provided by get_battery() to take new BMS behaviour into account.

2.5.9<br>
Change loss parameters to separate AC/DC, DC/AC conversion losses and battery charge / discharge losses.
Update charge calibration for new BMS firmware.
Increase de-rating temperature from 21C to 28C for new BMS firmware.

2.5.8<br>
Fix incorrect charging setup when force_charge=1.
Rework charge_periods() to consolidate charge periods to reduce number of time segments when timed_mode=2.
Add 'enable' parameter to set_charge().
Change 'force' to 'hold' in preset tariffs.
Stop plunge slots being used when timed_mode is 0 or 1.
Change default plunge_price to [3,3] and plunge_slots to 6.

2.5.7<br>
Fix problem with schedules being set for plunge periods that are more than 24 hours in the future.
Add date to plunge period display.

2.5.6<br>
Change plunge slots to 8 and plungs pricing to [3,10].
Change min_hours setting in charge_needed to 0.5 (30 minutes) and round up charge times to increments of this.
Show data and plot starting at t=0.

2.5.5<br>
Improve validation of plunge price periods so they don't repeat across days.
Correct start and end soc times and values when charging using best Agile time periods.
Extend charge times when charge needed exceeds battery capacity.

2.5.4<br>
Remove preset 'weighting' that were not used.
Update weighting to apply the requested charge duration correctly.
Reformat price and SoC tables to reduce wrapping and make them easier to read on small screens.
Change default for set_tariff() to show Agile 30 minute prices.

2.5.3<br>
Reverted change to allow updates during a charge period to avoid removing charge in progress.
Update contingency and show how this relates to battery SoC.
Add PV cover, the ratio of PV generation to consumption.
Add f.storage path so files can be saved to different locations if needed.
Allow delays in 'shading' to be a seaonal list of 4 values (winter, spring, summer, autumn).

2.5.2<br>
Updates to allow charge_needed() to run during a charge period.
Add suport for 'off_peak4' charge period.
Change Solcast forecast in charge_needed() so it does not get todays estimate to save API calls.
Include contingency and reserve when checking minimum battery level.

2.5.1<br>
Fix anomaly in scheduler support when get_device and get_flag return different results.
Add 'show_data' to charge_compare() and display run time and starting SoC.
Fix incorrect SoC actual data in charge_compare().

2.5.0<br>
Fix duration_in() to work with more steps per hour.
Improve charge calibrationn when using Force Charge.
Add 'save' to charge_needed() to save calculation data.
Add charge_compare() to compare predicted and actual battery state.

2.4.9<br>
Correct charge power during Force Charge.
Correct expiration of plunge charge slots.
Correct duplication of forecast and actual for current time period.
Add fcast.yesterday as attribute to forecasts.
Dropped settings for forecast adjust.

2.4.8<br>
Added shading to Solcast and Solar forecasts based on delay to generation around sunrise and sunset.
Added compare() to Solcast and Solar to compare and plot a forecast against actual generation.
Added sunrise / sunset times based on location in central England.
Updated plunge pricing to [1, 10] for day / night charging.
Fixed invalid key in set_tariff() when plunge pricing is available.
Fixed incorrect fdpwr when strategy includes Force Discharge.

2.4.7<br>
Correct times in Agile pricing for changes in daylght saving.
Update plunge pricing to allow a list of prices to be used.

2.4.6<br>
Implementation of Agile 'plunge_price', replaces 'trigger_price' and adds plunge time periods to current strategy.
Update set_tariff() to fetch Agile price from current hour instead of 11pm.

2.4.5<br>
Update charge period processing so charge_needed() will use the end time of the off_peak1 period as the end time.
Update charge period schedules to correct min_soc after charging with force_charge.
Flip charge periods to use second time period for charging and first for battery hold.
Add 'run_after' to set_pvoutput() for runtime control in scheduled jobs.

2.4.4<br>
Updated Solcast and Solar to include 30 minute forecast data and plotting.
Re-work charge_needed() to support steps_per_hour to set battery processing resolution.

2.4.3<br>
Change forecast_times to use system time for consistency with schedules when using Saturn Cloud.
Change default Agile product to AGILE-24-04-03.
Add options to plot Agile price data in set_tariff() with show_data and show_plot parameters.
Added trigger_price and trigger_mode to set_tariff() to increase grid use when Agile prices are lower than trigger_price.
Added data_wrap to set_tariff().
Set inverer power to 101W.
Fixed charge power being limited when device_power was less than 6.0kW.
Ameded seasonal changes so they use the forecast day instead of today.

2.4.1<br>
Reduce number of time periods used by stratgies for Octopus Flux and Agile.
Revise calculation of charge power to include inverter losses and reduce grid loss.
Update so charge times display correctly when clocks change.
Update set_tariff 'times' to include option to set 'force'.


2.4.0<br>
**breaking changes**
Implement best charging times for Agile tariff, based on best price for charge time required.
Re-write tariff handling with major charnges to set_tariff() and the way Agile prices are stored and processed.
Drop parameters 'start_at', 'end_by' and 'duration' from set_tariff().
Update 'times' parameter for set_tariff() to allow time periods to be added and remove using a list of tuples.
Add period 0 to charge_periods() to support force_charge before Agile charge period and update min_soc settings.
Add 'off_peak3' period for Octopus Cosy and include this in Time Of Use.
Change tariff 'peak' period key to 'peak1' to align with 'peak2'.
Update modelling of charge power when using schedules.
Update Octopus Cosy to correct TOU.
Update Agile to allow charging between 00:00-06:00 and 12:00-16:00.


2.3.9<br>
Add checking of number of periods in a schedule. Error if more than 8.
Show min and max soc correctly during charge periods.
Update default strategy for Flux to include period for charging from 01:00 to 01:59.
Sort periods into ascending time order to make them easier to follow.
Rework charge / discharge to improve prediction when charging from grid when solar is available.
Drop show_data=4 option in charge_needed().

2.3.8<br>
Revert inverter losses to BMS losses in charge_needed().

2.3.7<br>
Adjust inverter losses in charge_needed().

2.3.6<br>
Correct timing of Solcast forecast when timezone is not GMT.
Update get_flag() to return 'maxsoc' (True/False) if max soc is a supported field.
Update processing of max_soc in schedules.

2.3.5<br>
Adjust losses for battery discharge in charge_needed().
Fix data_wrap in charge_needed().
Fix set_period() handling of max_soc.

2.3.4<br>
Add processing of Max SoC when set in Force Charge schedule.
Correct timing of battery prediction so it doesn't lag actual by 1 hour.
Process Min SoC when force_charge=1 and timed_mode=2.

2.3.3<br>
Added f.residual_handling to cater for changes in the way Fox reports Capacity inplace of Residual.
Added h117__ protocol keys for battery info on H series Manager firmware 1.74.
Note: schedules do not work with firmwre 1.74. Fox reports "Parameter does not meet expectations". No fix currently available for this.

2.3.2<br>
Fix error when get_history() returns values that are strings.
Force file encoding to UTF-8 when saving results in get_history().
Reduced API call time out from 60 to 55 seconds to stop invalid timestamp error.
Load strategy from inverter in set_tariff().
Added support for setting max_soc in a schedule (not tested)
Added integrate_load_power setting to get_pvoutput.
Fix typo in charge_periods() that caused error with timed_mode=2

2.2.9<br>
** breaking change ** rename 'groups' to 'periods' for consistency between foxesscloud and openapi.
Updated management of battery reserve and float charging in charge_needed().
Added Reserve level to charts in charge_needed().
Changed bms_power setting to 50W.
Updated contingency to allow seasonal values for winter, spring, summer and autumn.
Update strategy mode to support ForceCharge and ForceDischarge work modes.
Update so min_soc setting in charge_needed() over-rides min_soc in the tariff strategy.
Fix force charge strategy mode in charge_neded() to set min_soc correctly.
Implement 2 second delay between calls that change inverter settings.
Added strategy mode (timed_mode=2) to charge_needed().
Added set_strategy() and charge_strategy() to manage charging schedules and work mode changes.
Refactor debug messaging.
Simplify charge_needed() output.
Added 'target_soc' to charge_needed() settings
Fix bat_info() giving incorrect temperatures when API returns 0 instead of -50 where there is no battery
Fix key error when accessing cell volts and temps using an agent / installer account.
Ensure output is generated if get_battery() fails using battery_info().
Update f.avg() to include calculation of averages in lists containng None values.
Added 'data_wrap' to charge_config.


2.1.9<br>
Update get_history() to use GMT or BST when plotting instead of mixed time zones.
Added 'economy_7' tariff that charges using GMT when clocks change.
Updated charge / discharge profiles for charge_needed() to show power flow in relation to work mode.
Better reporting of reason for http error code.
Template code for get_named_settings() added - not functional in this version due to Open API limitations.
Update set_pvoutput() to allow push=2.
Fix problem in set_pvoutput() sending summary to pushover when tou=1.
Improve accuracy of time of use data in get_pvoutput().
Improve handling of date / time for queries.
Comments added to pvoutput data when exported exceeds generated.
Fixed charge times being set incorrectly in set_tariff() when tariff is not Agile or Flux.
Show inverter model info and flag error in charge_needed() if residual is less than 0.1 kWh.
Updated output text to work better with pushover limit of 1024 bytes.
Fixed incorrect pushover app key for battery info.
Added pushover summary to set_pvoutout().
Added support for pushover notifications in set_tariff(), charge_needed() and battery_info().
Added saving plots to an image file.
Fix problem setting charge times if values are not read before writing.
Debug information added for HTTP timeout.
Fixed a problem where erratic sample times resulted in incorrect energy calculation.

2.0.9<br>
Added HTTP request reponse_time monitoring.
Added 60 second time-out and retry for http requests.
Fix to handle history and report values returned by Fox that are null.
Added invert_ct2 setting so the values for secondary generation can be configured so they are always +ve for secondary generation.
Updated condition where charge needed exceeds battery capacity.
Revised battery LiFePO4 calibration.
Updated battery_info() to show more derrived battery data.
Fix battery_monitor() logging to file.
Improvements to determine number of batteries.
Updated battery_info() and battery_monitor() to include mre log information and save to file.
Updated library that uses the Fox Open API. Information on the API can be found here: [Open API Documentation](https://www.foxesscloud.com/public/i18n/en/OpenApiDocument.html)
