import os
import gradio as gr
from langchain_core.tools import tool
from langgraph.prebuilt import create_react_agent
from langchain_openai import ChatOpenAI # Easily swapped for langchain_huggingface

# 1. Define the TEA (Techno-Economic Analysis) Tool
@tool
def calculate_net_co2(facility_name: str, flow_mgd: float, distance_miles: float) -> str:
    """
    Calculates the true net CO2 sequestered by a WWTP after subtracting 
    Scope 3 heavy-duty trucking emissions required to haul the alkaline mineral.
    """
    # Chemical & Logistics Constants
    gross_co2_per_mgd = 60          # tons CO2/yr captured per MGD
    limestone_needed_per_mgd = 138  # tons/yr rock required to hit 100mg/L dose
    truck_capacity_tons = 20        # standard dump truck capacity
    emission_factor_kg_per_mile = 1.45 # kg CO2 per loaded truck mile (EPA standard)
    
    # Gross Sequestration Math
    gross_capture = flow_mgd * gross_co2_per_mgd
    
    # Scope 3 Haul Emissions Math
    annual_limestone_tons = flow_mgd * limestone_needed_per_mgd
    annual_trips = annual_limestone_tons / truck_capacity_tons
    total_haul_miles = annual_trips * distance_miles * 2 # Round trip accounting
    
    haul_emissions_tons = (total_haul_miles * emission_factor_kg_per_mile) / 1000
    net_co2 = gross_capture - haul_emissions_tons
    efficiency = (net_co2 / gross_capture) * 100
    
    return (
        f"Facility: {facility_name}\n"
        f"Gross CO2 Sequestered: {gross_capture:.1f} t/yr\n"
        f"Scope 3 Haul Emissions: {haul_emissions_tons:.1f} t/yr (Distance: {distance_miles} mi)\n"
        f"Net CO2 Yield: {net_co2:.1f} t/yr\n"
        f"Carbon Efficiency: {efficiency:.1f}%"
    )

# 2. Initialize the LLM and Compile the LangGraph Agent
# For Hugging Face, you can use HuggingFaceEndpoint or an inference API key
llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.1) 
tools = [calculate_net_co2]

# Compiles the state graph with a system prompt setting the CREW engineer persona
system_prompt = (
    "You are a Techno-Economic Analysis Copilot for CREW Carbon. "
    "Use the calculate_net_co2 tool to evaluate the net-negative viability of wastewater facilities. "
    "Always present the final net CO2 yield clearly to the deployment engineers."
)
agent_executor = create_react_agent(llm, tools, state_modifier=system_prompt)

# 3. Gradio Interface for Hugging Face Deployment
def chat_with_crew_agent(message, history):
    """Parses Gradio inputs into the LangGraph state and returns the AI message."""
    response = agent_executor.invoke({"messages": [("user", message)]})
    return response["messages"][-1].content

# 4. Launch the UI
demo = gr.ChatInterface(
    fn=chat_with_crew_agent,
    title="CREW Carbon: Logistics & TEA Agent",
    description="Ask the agent to evaluate the net-negative CO2 yield of a target facility based on flow and haul distance.",
    examples=[
        "Calculate the net yield for Hyperion LA with 260 MGD and a quarry 84 miles away.",
        "San Jose WWTP flows at 110 MGD and the Permanente quarry is 12 miles away. What is the efficiency?"
    ]
)

if __name__ == "__main__":
    demo.launch()
