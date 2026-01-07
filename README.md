# DiversiPlant Dashboard

[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0) [![Python 3.11](https://img.shields.io/badge/python-3.11.9-blue.svg)](https://www.python.org/downloads/) [![Shiny for Python](https://img.shields.io/badge/Shiny-for%20Python-green.svg)](https://shiny.posit.co/py/)

An interactive dashboard for discovering compatible plant species for agroforestry, ecological restoration, and sustainable agriculture projects.

## Overview

DiversiPlant Dashboard helps practitioners, researchers, and farmers identify plant species that thrive together in specific locations and climates. The application integrates botanical databases with interactive visualizations to support decision-making for polyculture and agroforestry systems.

### Key Features

- **Location-Based Species Filtering** - Find species native, endemic, or naturalized to your region using GPS coordinates
- **Interactive World Map** - Visualize and select project locations with OpenStreetMap and satellite imagery
- **Climate Zone Integration** - Filter species based on climate compatibility
- **Species Compatibility Analysis** - Visualize species coexistence based on growth forms, light requirements, and vertical stratification
- **Growth Visualization** - See how selected species develop over time with adjustable stratum resolution
- **GIFT Database Integration** - Access the Global Inventory of Floras and Traits for comprehensive botanical data
- **Exportable Results** - Download filtered species lists for further analysis

### Use Cases

- Agroforestry system design
- Forest restoration planning
- Polyculture garden design
- Native species identification
- Biodiversity conservation projects

## Prerequisites

### System Requirements

- **Operating System**: macOS, Linux, or Windows
- **Python**: 3.11.9
- **R**: 3.2.3 or later

### System Dependencies

Install required geospatial libraries for your operating system:

**Ubuntu/Debian:**

```bash
sudo apt-get install -y libgdal-dev libproj-dev libgeos-dev libudunits2-dev
```

**macOS (Homebrew):**

```bash
brew install gdal proj geos udunits
```

**RHEL/CentOS/Fedora:**

```bash
sudo dnf install -y gdal-devel proj-devel geos-devel udunits2-devel
```

### R Setup

Install R and the required GIFT package:

```r
install.packages("GIFT")
```

Ensure R is on your system PATH so Python can access it via rpy2.

## Installation

### 1. Clone the Repository

```bash
git clone https://github.com/ilyas-siddique/DiversiPlantDashboard.git
cd DiversiPlantDashboard
```

### 2. Create Virtual Environment

**Using venv:**

```bash
python3 -m venv diversiplant_venv
source diversiplant_venv/bin/activate  # Windows: diversiplant_venv\Scripts\activate
```

**Using Conda:**

```bash
conda env create -f environment.yml
conda activate agroforestry_env
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Verify R Integration

```bash
python -c "import rpy2.robjects as ro; print(ro.r('R.version.string'))"
```

## Running the Application

### Development Mode

**Using IDE (VS Code/PyCharm):**

1. Install the Shiny extension for your IDE
2. Open `app.py`
3. Click "Run Shiny App"

**Using command line:**

```bash
uvicorn app:app --host 127.0.0.1 --port 8001 --reload
```

### Production Mode

```bash
uvicorn app:app --host 0.0.0.0 --port 8001 --workers 16
```

Access the dashboard at: **http://127.0.0.1:8001/diversiplant**

## Project Structure

```text
DiversiPlantDashboard/
├── app.py                  # Main application entry point
├── requirements.txt        # Python dependencies
├── environment.yml         # Conda environment specification
├── runtime.txt             # Runtime version specifications
│
├── custom_ui/              # Frontend UI components
│   ├── tab_00_start.py            # Homepage tab
│   ├── tab_01_location.py         # Location selection tab
│   ├── tab_02_climate.py          # Climate filtering tab
│   ├── tab_03_species.py          # Species selection tab
│   ├── tab_04_results.py          # Results display tab
│   └── tab_details_tabs.py        # Additional details tab
│
├── custom_server/          # Backend server logic
│   ├── server_app.py       # Main server functions
│   ├── server_homepage.py  # Homepage server logic
│   └── agroforestry_server.py  # Data processing utilities
│
├── data/                   # Data files and assets
│   ├── MgmtTraitData_updated.csv  # Plant management traits
│   ├── practitioners.csv          # Practitioner data
│   ├── ui.css                     # Custom styles
│   └── img/                       # Image assets
│
└── R_code/                 # R scripts for GIFT integration
    └── Growth form GIFT.R
```

## Architecture

### UI Components

Each tab is managed by a dedicated function suffixed with `_tabs` (e.g., `climate_tabs`). UI elements use unique IDs that connect to server functions.

### Server Components

- `agroforestry_server.py` - Handles data import from CSV sources
- `server_app.py` - Main backend logic managing dashboard outputs and reactivity

### Data Flow

1. User inputs location/climate/species preferences
2. Server processes inputs using Python and R (GIFT database)
3. Returns interactive visualizations (Plotly charts, Folium maps)
4. Results displayed in dynamic DataTables

## Data Sources

| Source                                        | Description                                            |
| --------------------------------------------- | ------------------------------------------------------ |
| Management Traits Database                    | Local CSV with plant management information            |
| [GIFT Database](https://gift.uni-goettingen.de/) | Global Inventory of Floras and Traits - accessed via R |

## Technology Stack

| Category                  | Technologies                                                                             |
| ------------------------- | ---------------------------------------------------------------------------------------- |
| **Frontend**        | [Shiny for Python](https://shiny.posit.co/py/), Custom CSS                                  |
| **Backend**         | [Starlette](https://www.starlette.io/), [Uvicorn](https://www.uvicorn.org/)                    |
| **Data Processing** | [Pandas](https://pandas.pydata.org/), [GeoPandas](https://geopandas.org/)                      |
| **Visualization**   | [Plotly](https://plotly.com/python/), [Folium](https://python-visualization.github.io/folium/) |
| **R Integration**   | [rpy2](https://rpy2.github.io/)                                                             |

## Contributing

Contributions are welcome! To contribute:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/your-feature`)
3. Make your changes following the existing code style
4. Test your changes locally
5. Commit with clear messages (`git commit -m "Add: description"`)
6. Push to your fork (`git push origin feature/your-feature`)
7. Open a Pull Request

### Development Guidelines

- **UI functions**: Suffix with `_tabs` (e.g., `climate_tabs`)
- **Server functions**: Prefix with `serv_` (e.g., `serv_climate`)
- **IDs**: Use descriptive, consistent IDs that match between UI and server

## License

This project is licensed under the GNU General Public License v3.0 - see the [LICENSE](LICENSE) file for details.

## Acknowledgments

- [GIFT Database](https://gift.uni-goettingen.de/) - Global Inventory of Floras and Traits
- All contributors and the open-source community

---

*DiversiPlant Dashboard - Supporting biodiversity in sustainable agriculture*
