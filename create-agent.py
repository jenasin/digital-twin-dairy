import streamlit as st
import openai
import pandas as pd
import os
import json
import time
import re

openai.api_key = st.secrets["OPENAI_API_KEY"]

assistant = openai.beta.assistants.create(
    name="DairySustainabilityAgent",
    instructions="""
You are a dairy sustainability AI analyst.

You receive multiple CSV files related to:
- milk yield
- treatment and medicine usage
- cow data (birth, sickness, reproduction)
- general farm performance

Your job:
1. Load and understand all uploaded CSV files.
2. Identify indicators across 3 areas:
   - ECONOMIC: total milk income, treatment costs, monthly profit/loss.
   - ENVIRONMENTAL: antibiotic usage frequency, treatment intensity.
   - ANIMAL WELFARE: % of sick cows, avg treatment duration, high-risk animals.

Respond only in this format:
{
  "summary": "...",
  "sustainability": {
    "economic": { ... },
    "environmental": { ... },
    "animal_welfare": { ... }
  },
  "recommendations": ["...", "..."]
}
Do NOT refer to other agents. Perform all calculations yourself.
""",
    model="gpt-4o",
    tools=[{"type": "code_interpreter"}]
)

# Ulož ID agenta
with open("dairy_sustainability_agent.json", "w") as f:
    json.dump({"id": assistant.id}, f)

print("✅ Created agent:", assistant.id)
