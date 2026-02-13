# MaxStorage

A Python application for processing depot inventory reports, calculating storage billing prices, and determining maximum values per protocol.

## Overview

MaxStorage automates the processing of depot stock reports by:

- Reading Excel inventory reports from depot folders
- Matching protocols to service configurations using fuzzy matching
- Calculating storage billing based on position types (Pallet, Shelf, Bin)
- Applying currency exchange rates for price conversions
- Computing maximum billing values per protocol across multiple reports
- Identifying and reporting protocols with configuration errors

## Features

- **GUI & Console modes**: Run with a graphical interface or command line
- **Fuzzy Protocol Matching**: Automatically matches inventory protocols to service configurations
- **Position Type Conversion**: Converts between Pallet, Shelf, and Bin storage types
- **Exchange Rate Support**: Handles multi-currency price calculations
- **Error Reporting**: Generates detailed reports of protocols with configuration issues
- **Maximum Value Calculation**: Tracks highest billing totals per protocol

## Installation

### Prerequisites

- Python 3.10+
- pip

### Setup

```bash
# Clone the repository
git clone https://github.com/Rigoberte/MaxStorage.git
cd MaxStorage

# Create virtual environment
python -m venv .venv

# Activate virtual environment
# Windows
.venv\Scripts\activate
# Linux/macOS
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

## Usage

### GUI Mode (Default)

```bash
python src/main.py
```

### Console Mode

Edit `src/main.py` and uncomment `run_console()`:

```python
def main():
    run_console()
    # run_gui()
```

Then run:

```bash
python src/main.py
```

## Project Structure

```
MaxStorage/
├── data/
│   ├── configs/                 # Configuration files
│   │   ├── exchanges_rate.xlsx  # Currency exchange rates
│   │   ├── Services - Configuration.xlsx
│   │   └── protocols_renaming.xlsx
│   ├── depot_reports/           # Input: Stock reports
│   └── processed_reports/       # Output: Processed billing reports
├── src/
│   ├── core/                    # Business logic
│   │   ├── max_calculator.py    # Maximum value calculations
│   │   ├── price_calculator.py  # Storage billing calculations
│   │   └── storage_service.py   # Main processing orchestrator
│   ├── gui/                     # Graphical interface
│   │   └── gui.py
│   ├── readers/                 # Excel file readers
│   │   ├── excel_reader.py
│   │   ├── exchanges_rate_excel_reader.py
│   │   ├── PERI_excel_reader.py
│   │   └── service_configuration_excel_reader.py
│   ├── config.py                # Paths and configuration
│   └── main.py                  # Application entry point
└── docs/                        # Documentation
```

## Configuration

### Required Files

Place these files in `data/configs/`:

| File | Description |
|------|-------------|
| `exchanges_rate.xlsx` | Currency exchange rates |
| `Services - Configuration.xlsx` | Service definitions with protocols and pricing |
| `protocols_renaming.xlsx` | Protocol name mappings |

### Input Files

Place depot reports in `data/depot_reports/`. Files must match the pattern:
```
StockThermoFisher_ST_*.xls
```

## Output

The application generates:

- **`data/max_values.xlsx`**: Maximum billing values per protocol
- **`data/protocols_with_errors.xlsx`**: Protocols with configuration issues
- **`data/processed_reports/`**: Individual processed billing reports