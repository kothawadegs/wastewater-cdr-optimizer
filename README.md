# Alkaline CDR Spatial Siting Index

**Live Dashboard:** [https://kothawadegs.github.io/wastewater-cdr-optimizer](https://kothawadegs.github.io/wastewater-cdr-optimizer)

## Project Overview
A spatial decision-support pipeline designed to evaluate the scalability and logistics of Wastewater Alkalinity Enhancement (WAE) for Carbon Dioxide Removal (CDR). 

While introducing alkaline minerals into municipal wastewater biological treatment processes presents a significant carbon removal opportunity, the unit economics and net-negative carbon footprint are heavily constrained by logistics. Transporting heavy crushed limestone over long distances generates haul emissions that degrade the net CO₂ capture. 

This project solves for that constraint by building a spatial optimization model for the state of California, ranking wastewater facilities based on high flow capacities and immediate proximity to active mineral supply chains.

## Methodology & Data Pipeline
The pipeline integrates public environmental and geological datasets to generate a deployment **Viability Index**:

1. **The Demand Side (EPA ECHO):** Ingests National Pollutant Discharge Elimination System (NPDES) flow data for California municipal wastewater treatment plants. It applies a stoichiometric baseline (100 mg/L CaCO₃ equivalent dose) to translate raw flow (MGD) into a theoretical annual CO₂ yield (~60 tons of CO₂ per MGD/year).
2. **The Supply Side (USGS MRDS):** Ingests the Mineral Resources Data System to isolate active alkaline mineral extraction sources (e.g., limestone quarries) in California.
3. **Spatial Optimization:** Projects coordinate data into a localized flat plane (`EPSG:3310` California Albers) and utilizes vectorized nearest-neighbor spatial joins to calculate the exact haul distance between every WWTP and its closest mineral feedstock. 
4. **Viability Scoring:** Facilities are ranked by dividing their flow capacity by a distance penalty, heavily prioritizing plants that offer massive volume without requiring long-haul trucking.

## Tech Stack
* **Data Engineering:** Python, Pandas, GeoPandas, Shapely
* **Spatial Projection:** Coordinate Reference System (CRS) transformations (`EPSG:4326` to `EPSG:3310`)
* **Front-End Visualization:** HTML5, JavaScript, Tailwind CSS, Leaflet.js
* **Basemap Integration:** Esri World Dark Gray Base (ArcGIS)
* **Deployment:** GitHub Pages (Serverless)

## Repository Structure
This repository separates the backend data engineering logic from the frontend web deployment:

* `data/` - Contains the mock EPA and USGS CSV datasets used for pipeline execution.
* `src/spatial_ops.py` - The production-grade, object-oriented Python module handling CRS projections and vectorized spatial joins.
* `notebooks/` 
  * `01_exploratory_pipeline.ipynb` - Initial data wrangling, EDA, and logic formulation.
  * `02_production_execution.ipynb` - Clean execution notebook orchestrating the `spatial_ops` module.
* `ca_wwtp_cdr_viability.geojson` - The fully processed spatial artifact exported by the pipeline.
* `index.html` - The static frontend web application that ingests the GeoJSON and renders the interactive map.
* `agent/` - CDR Siting Copilot, a smolagents tool-calling agent (Colab notebook, local run, or Hugging Face Space; see `agent/README.md`).
* `copilot.js` - Browser version of the Copilot embedded in the live dashboard.

## AI Copilot
An LLM agent that answers questions about the ranking, finds the nearest limestone source for any coordinates, and computes net CO₂ after Scope 3 trucking emissions. Both versions need a free [Hugging Face token](https://huggingface.co/settings/tokens) with the *Make calls to Inference Providers* permission.

* **On the dashboard:** open the [live dashboard](https://kothawadegs.github.io/wastewater-cdr-optimizer), click **Ask the Copilot**, and paste your token under *Settings*. The token stays in your browser.
* **In Google Colab:** [![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/kothawadegs/wastewater-cdr-optimizer/blob/main/agent/cdr_agent_colab.ipynb) Run all cells to get a temporary public chat link.

## Pipeline Execution
To run the spatial data pipeline locally:
```bash
git clone [https://github.com/kothawadegs/wastewater-cdr-optimizer.git](https://github.com/kothawadegs/wastewater-cdr-optimizer.git)
cd wastewater-cdr-optimizer
pip install pandas geopandas shapely
