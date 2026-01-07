# Contributing to DiversiPlant Dashboard

Thank you for your interest in contributing to DiversiPlant Dashboard! This project helps users discover compatible plant species for agroforestry, restoration, and agricultural projects.

## Table of Contents

-   [Code of Conduct](#code-of-conduct)
-   [Getting Started](#getting-started)
-   [How to Contribute](#how-to-contribute)
-   [Development Setup](#development-setup)
-   [Coding Standards](#coding-standards)
-   [Pull Request Process](#pull-request-process)
-   [Reporting Issues](#reporting-issues)

## Code of Conduct {#code-of-conduct}

By participating in this project, you agree to maintain a respectful and inclusive environment. Please be considerate of others and focus on constructive feedback.

## Getting Started {#getting-started}

1.  Fork the repository
2.  Clone your fork locally
3.  Set up the development environment (see [Development Setup](#development-setup))
4.  Create a new branch for your feature or fix

## How to Contribute {#how-to-contribute}

### Types of Contributions Welcome

-   **Bug fixes** - Found a bug? Submit a fix!
-   **Feature enhancements** - New features that improve the dashboard
-   **Documentation** - Improvements to README, code comments, or this guide
-   **Data contributions** - Additional plant species data or regional datasets
-   **UI/UX improvements** - Better visualizations or user interface enhancements
-   **R package integration** - Improvements to GIFT package integration
-   **Translations** - Help internationalize the dashboard

### Areas Needing Contributions

-   Expanding the plant species database and enabling adaption of the new database
-   Improving climate zone detection
-   Adding new visualization types
-   Performance optimizations
-   Mobile responsiveness
-   Accessibility improvements

## Development Setup {#development-setup}

### Prerequisites

-   Python 3.11.9
-   R 3.2.3 or later
-   System libraries for geospatial processing (GDAL, PROJ, GEOS)

### Installation

1.  **Clone the repository:**

    ``` bash
    git clone https://github.com/ilyas-siddique/DiversiPlantDashboard.git
    cd DiversiPlantDashboard
    ```

2.  **Create and activate a virtual environment:**

    ``` bash
    python3 -m venv diversiplant_venv
    source diversiplant_venv/bin/activate  # Windows: diversiplant_venv\Scripts\activate
    ```

3.  **Install Python dependencies:**

    ``` bash
    pip install -r requirements.txt
    ```

4.  **Install R and the GIFT package:**

    ``` r
    install.packages("GIFT")
    ```

5.  **Run the application:**

    ``` bash
    uvicorn app:app --port 8001 --reload
    ```

## Coding Standards {#coding-standards}

### Python

-   Follow PEP 8 style guidelines
-   Use meaningful variable and function names
-   Add docstrings to functions and classes
-   Keep functions focused and modular

### Shiny for Python

-   Suffix UI tab functions with `_tabs` (e.g., `climate_tabs`)
-   Prefix server functions with `serv_` (e.g., `serv_climate`)
-   Use descriptive IDs for inputs and outputs

### File Organization

-   UI components go in `custom_ui/`
-   Server logic goes in `custom_server/`
-   Data files go in `data/`
-   Static assets go in `data/img/`

## Pull Request Process {#pull-request-process}

1.  **Create a feature branch** from `main`:

    ``` bash
    git checkout -b feature/your-feature-name
    ```

2.  **Make your changes** and commit with clear messages:

    ``` bash
    git commit -m "Add: Description of what you added"
    git commit -m "Fix: Description of what you fixed"
    ```

3.  **Test your changes** locally to ensure they work

4.  **Push to your fork:**

    ``` bash
    git push origin feature/your-feature-name
    ```

5.  **Open a Pull Request** with:

    -   Clear title describing the change
    -   Description of what was changed and why
    -   Screenshots if UI changes are involved
    -   Reference to any related issues

6.  **Address review feedback** if requested

## Reporting Issues {#reporting-issues}

When reporting issues, please include:

-   **Description** - Clear description of the problem
-   **Steps to Reproduce** - How to trigger the issue
-   **Expected Behavior** - What should happen
-   **Actual Behavior** - What actually happens
-   **Environment** - OS, Python version, R version
-   **Screenshots** - If applicable

### Issue Labels

-   `bug` - Something isn't working
-   `enhancement` - New feature or improvement
-   `documentation` - Documentation improvements
-   `good first issue` - Good for newcomers
-   `help wanted` - Extra attention needed

## Questions?

If you have questions, feel free to open an issue with the `question` label.

Thank you for contributing to sustainable agriculture and biodiversity!