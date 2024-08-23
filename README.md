# Agroforestry

Welcome to the Github repository of the Agroforestry Dashboard

## Installation

Clone the repository to your local machine:

```bash
git clone git@github.com:Anto1n/Agroforestry.git
```

Ensure you have Python installed on your machine. The version used is detailed in `runtime.txt`. The Python dependecies for this project are listed in `requirements.txt` for `virtualenv`-based package managers. Create a virtual environment (venv or conda) and install them.

<details>
  <summary>Virtualenv/venv</summary>


Create your virtual environment (make sure it ends with `..venv`, e.g. `agroforestry_venv` for git to ignore it). 
```
python3 -m venv agroforestry_venv
```
Activate it
```
source agroforestry_venv/bin/activate
```
Install the dependencies using the `requirements.txt` file
```
pip3 install -r requirements.txt
```
-------------
  
</details>

### Shiny for Python

In order to launch the app locally and be able to use as expected, you should install the shiny app of your IDE.


## Running the Application

With the environment set up and active, launch the app directly on the top right of your window. You should see in the launch options :
```Run Shiny App```

You should see something similar to the following output:

```
INFO:     Uvicorn running on http://127.0.0.1:63101 (Press CTRL+C to quit)
INFO:     Started reloader process [15928] using WatchFiles
INFO:     Started server process [28932]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     127.0.0.1:61812 - "GET /?vscodeBrowserReqId=1724454833017 HTTP/1.1" 200 OK
INFO:     127.0.0.1:61812 - "GET /ui.css HTTP/1.1" 304 Not Modified
INFO:     ('127.0.0.1', 61817) - "WebSocket /websocket/" [accepted]
INFO:     connection open
```

## Structure

- **Custom_UI**: Frontend functions for each tab, prefixed with `tabs_`.
- **Custom_Server**: Backend server functions, prefixed with `serv_`.
- **App**: Core application function managing imports and integrating the components into Shiny Apps.

## Features

- **Custom UI**: Each tab is managed by a unique function, suffixed with `_tabs` for identification (ex: climate_tabs).
- **Custom Server**: Two functions, `agroforestry_server` is a function dealing with the import of data from the first datasource. Then, `server_app` is the backend of the app. It deals with the different output of the dashboard.

The connection between the UI and the Server is done by the IDs of the differents input. For example :

```
    ui.input_text(
          "longitude",
          "Longitude :",
          '0'
      )
```
In this example "longitude" is the id, and if it changes, it should change also in the `server_app`, but the "Longitude :" appears on top of the text input. If you want to change the appearance of such an input, then you should change the second one.
Changing the first one might be a risk to break some functions.

## Contributing

Contributions are welcome. Please open an issue to propose changes or submit a pull request directly.
