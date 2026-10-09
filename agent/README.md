---
title: CDR Siting Copilot
emoji: 🌊
colorFrom: blue
colorTo: green
sdk: gradio
sdk_version: 6.30.0
app_file: app.py
pinned: false
short_description: Agent for siting wastewater alkalinity CDR in California
---

# CDR Siting Copilot

A [smolagents](https://github.com/huggingface/smolagents) tool-calling agent for the
[wastewater-cdr-optimizer](https://github.com/kothawadegs/wastewater-cdr-optimizer) pipeline.

[![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/kothawadegs/wastewater-cdr-optimizer/blob/main/agent/cdr_agent_colab.ipynb)

## Tools

| Tool | What it does |
| --- | --- |
| `list_ranked_facilities` | Top WWTPs by Viability Index from `ca_wwtp_cdr_viability.geojson` |
| `get_facility_profile` | Flow, nearest quarry, haul distance, gross CO₂ and rank for one plant |
| `find_nearest_quarry` | Closest USGS MRDS limestone quarry to any lat/lon |
| `calculate_net_co2` | Net CO₂ after Scope 3 round-trip trucking emissions |

## Configuration

| Setting | Kind | Purpose |
| --- | --- | --- |
| `HF_TOKEN` | Secret (required) | Hugging Face token with the *Make calls to Inference Providers* permission |
| `MODEL_ID` | Variable (optional) | Override the default smolagents model, e.g. `Qwen/Qwen2.5-Coder-32B-Instruct` |

## Run locally

```bash
pip install -r agent/requirements.txt
HF_TOKEN=hf_xxx python agent/app.py
```

## Run in Google Colab

Open [`cdr_agent_colab.ipynb`](https://colab.research.google.com/github/kothawadegs/wastewater-cdr-optimizer/blob/main/agent/cdr_agent_colab.ipynb) in Colab, choose **Runtime → Run all**, paste your token when asked (or store it as a Colab secret named `HF_TOKEN`), then open the `gradio.live` link it prints.

## Deploy to Hugging Face Spaces

> Gradio Spaces currently require a paid Hugging Face plan; free accounts can only create Static Spaces.

From the repository root:

```bash
pip install huggingface_hub
hf auth login                      # token needs write access
python agent/deploy_space.py <your-hf-username>/cdr-siting-copilot
```

The script creates the Space if needed and uploads `agent/` together with the
GeoJSON and `data/` files the agent reads. Then add `HF_TOKEN` under the Space's
**Settings → Variables and secrets**.
