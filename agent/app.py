"""
CDR Siting Copilot: a Hugging Face Space agent for the wastewater-cdr-optimizer pipeline.

The agent (smolagents ToolCallingAgent) answers questions about the California
WWTP viability ranking produced by `src/spatial_ops.py`, finds the nearest
limestone feedstock for arbitrary coordinates, and runs a net-CO2 techno-economic
check that subtracts Scope 3 trucking emissions from gross sequestration.

The LLM runs on Hugging Face Inference Providers, authenticated with the
`HF_TOKEN` secret of the Space. Override the model with the `MODEL_ID` variable.
"""

import json
import math
import os
from pathlib import Path

import pandas as pd
from smolagents import GradioUI, InferenceClientModel, ToolCallingAgent, tool

# --- Data loading -------------------------------------------------------------
# On the Space the data sits next to app.py; in the GitHub repo it sits one level up.
HERE = Path(__file__).resolve().parent
DATA_ROOT = HERE if (HERE / "ca_wwtp_cdr_viability.geojson").exists() else HERE.parent

with open(DATA_ROOT / "ca_wwtp_cdr_viability.geojson") as f:
    _features = json.load(f)["features"]

FACILITIES = pd.DataFrame(
    [
        {
            "facility_name": p["facility_name"],
            "flow_mgd": p["flow_mgd"],
            "latitude": p["Latitude_left"],
            "longitude": p["Longitude_left"],
            "nearest_quarry": p["site_name"],
            "haul_distance_miles": round(p["haul_distance_miles"], 2),
            "est_co2_t_yr": p["est_co2_t_yr"],
            "viability_index": round(p["viability_index"], 3),
        }
        for p in (feat["properties"] for feat in _features)
    ]
).sort_values("viability_index", ascending=False, ignore_index=True)
FACILITIES.insert(0, "rank", FACILITIES.index + 1)

QUARRIES = pd.read_csv(DATA_ROOT / "data" / "california_usgs_mrds_limestone.csv")

# --- Model constants (mirrors src/spatial_ops.py and the TEA assumptions) ------
GROSS_CO2_PER_MGD = 60              # t CO2/yr captured per MGD at 100 mg/L CaCO3 dose
LIMESTONE_PER_MGD = 138             # t/yr rock required per MGD at 100 mg/L dose
TRUCK_CAPACITY_TONS = 20            # standard dump truck payload
EMISSION_FACTOR_KG_PER_MILE = 1.45  # kg CO2 per heavy-duty truck mile
EARTH_RADIUS_MILES = 3958.8


def _haversine_miles(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * EARTH_RADIUS_MILES * math.asin(math.sqrt(a))


# --- Tools --------------------------------------------------------------------
@tool
def list_ranked_facilities(top_n: int = 10) -> str:
    """
    Returns the California wastewater treatment plants ranked by the pipeline's
    Viability Index (flow_mgd / (haul_distance_miles + 0.1)), highest first.

    Args:
        top_n: Maximum number of facilities to return.
    """
    return FACILITIES.head(max(1, top_n)).to_string(index=False)


@tool
def get_facility_profile(facility_name: str) -> str:
    """
    Looks up one wastewater treatment plant from the viability dataset and returns
    its flow, coordinates, nearest limestone quarry, haul distance, estimated gross
    CO2 yield, Viability Index and rank. Matching is case-insensitive and partial.

    Args:
        facility_name: Full or partial facility name, e.g. "Hyperion" or "San Jose WWTP".
    """
    matches = FACILITIES[FACILITIES["facility_name"].str.contains(facility_name, case=False, regex=False)]
    if matches.empty:
        known = ", ".join(FACILITIES["facility_name"])
        return f"No facility matching '{facility_name}'. Known facilities: {known}"
    return matches.to_string(index=False)


@tool
def find_nearest_quarry(latitude: float, longitude: float) -> str:
    """
    Finds the closest limestone quarry (USGS MRDS) to a point and returns its
    great-circle distance in miles. Use this for sites that are not in the dataset.

    Args:
        latitude: Latitude of the site in decimal degrees (WGS84).
        longitude: Longitude of the site in decimal degrees (WGS84).
    """
    distances = QUARRIES.apply(
        lambda q: _haversine_miles(latitude, longitude, q["Latitude"], q["Longitude"]), axis=1
    )
    q = QUARRIES.loc[distances.idxmin()]
    return f"Nearest quarry: {q['site_name']} ({q['Latitude']}, {q['Longitude']}), {distances.min():.2f} miles away"


@tool
def calculate_net_co2(facility_name: str, flow_mgd: float, distance_miles: float) -> str:
    """
    Calculates the true net CO2 sequestered by a WWTP after subtracting the
    Scope 3 heavy-duty trucking emissions required to haul the alkaline mineral
    (round trip, 20 t trucks, 1.45 kg CO2 per mile).

    Args:
        facility_name: Name of the facility, used only to label the result.
        flow_mgd: Average plant flow in million gallons per day (MGD).
        distance_miles: One-way haul distance from the quarry to the plant in miles.
    """
    gross_capture = flow_mgd * GROSS_CO2_PER_MGD

    annual_limestone_tons = flow_mgd * LIMESTONE_PER_MGD
    annual_trips = annual_limestone_tons / TRUCK_CAPACITY_TONS
    total_haul_miles = annual_trips * distance_miles * 2
    haul_emissions_tons = total_haul_miles * EMISSION_FACTOR_KG_PER_MILE / 1000

    net_co2 = gross_capture - haul_emissions_tons
    efficiency = (net_co2 / gross_capture) * 100 if gross_capture else 0.0

    return (
        f"Facility: {facility_name}\n"
        f"Limestone required: {annual_limestone_tons:,.0f} t/yr ({annual_trips:,.0f} truck trips)\n"
        f"Gross CO2 sequestered: {gross_capture:,.1f} t/yr\n"
        f"Scope 3 haul emissions: {haul_emissions_tons:,.1f} t/yr (distance: {distance_miles} mi one-way)\n"
        f"Net CO2 yield: {net_co2:,.1f} t/yr\n"
        f"Carbon efficiency: {efficiency:.1f}%"
    )


# --- Agent --------------------------------------------------------------------
INSTRUCTIONS = (
    "You are the CDR Siting Copilot, a techno-economic analysis assistant for "
    "Wastewater Alkalinity Enhancement (WAE) in California. Ground every answer in "
    "the tools: use list_ranked_facilities and get_facility_profile for plants in "
    "the dataset, find_nearest_quarry for new coordinates, and calculate_net_co2 "
    "to report net-negative viability. Always state the net CO2 yield and carbon "
    "efficiency clearly, and note that the dataset is a demonstration sample."
)

model_kwargs = {"token": os.getenv("HF_TOKEN")}
if os.getenv("MODEL_ID"):
    model_kwargs["model_id"] = os.environ["MODEL_ID"]
model = InferenceClientModel(**model_kwargs)

agent = ToolCallingAgent(
    tools=[list_ranked_facilities, get_facility_profile, find_nearest_quarry, calculate_net_co2],
    model=model,
    instructions=INSTRUCTIONS,
    max_steps=8,
    name="cdr_siting_copilot",
    description="Ranks California WWTPs for alkaline CDR and computes net CO2 after haul emissions.",
)

if __name__ == "__main__":
    GradioUI(agent).launch(share=False)
