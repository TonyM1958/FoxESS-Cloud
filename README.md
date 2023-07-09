# FoxESS-Cloud
This site contains sample python code for accessing the Fox cloud data via the REST API used by the Fox ESS Cloud web site and app. There is also a Jupyter Lab notebook used to run the sample code.

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

When a device is selected, this call returns a dictionary containing the device details
