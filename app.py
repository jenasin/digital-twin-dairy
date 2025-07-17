import streamlit as st
import openai
import os
import pandas as pd
import time
import json
import re

# === API Key ===
openai.api_key = st.secrets["OPENAI_API_KEY"]

# === Load agent ID ===
with open("dairy_sustainability_agent.json", "r") as f:
    agent_id = json.load(f)["id"]

# === Create storage folder ===
FOLDER = "streamlet/farm_data"
os.makedirs(FOLDER, exist_ok=True)

st.title("🐄 Dairy Sustainability AI Agent")

# === 1. Upload CSV files ===
uploaded_files = st.file_uploader("📂 Upload CSV files related to your dairy farm", type="csv", accept_multiple_files=True)

file_ids = []

if uploaded_files:
    st.subheader("📥 Uploaded data preview:")
    for file in uploaded_files:
        df = pd.read_csv(file)
        st.dataframe(df.head())
        # Save locally
        path = os.path.join(FOLDER, file.name)
        df.to_csv(path, index=False)
        # Upload to OpenAI
        uploaded = openai.files.create(file=open(path, "rb"), purpose="assistants")
        file_ids.append(uploaded.id)

# === 2. Analyze sustainability ===
if file_ids and st.button("🚀 Run Sustainability Analysis"):
    thread = openai.beta.threads.create()

    openai.beta.threads.messages.create(
        thread_id=thread.id,
        role="user",
        content="""
Please analyze all uploaded dairy farm CSVs and return sustainability metrics as compact JSON only.

Respond strictly in this format:
{
  "summary": "...",
  "sustainability": {
    "economic": {
      "total_milk_income": float,
      "total_treatment_costs": float,
      "monthly_profit_loss": float
    },
    "environmental": {
      "antibiotic_usage_frequency": int,
      "treatment_intensity": float
    },
    "animal_welfare": {
      "percentage_sick_cows": float,
      "avg_treatment_duration": float,
      "high_risk_animals_percentage": float
    }
  },
  "recommendations": [
    "First short recommendation.",
    "Second one.",
    "Third one."
  ]
}
Do not include any explanation or markdown. Just return valid JSON.
""",
        attachments=[{"file_id": fid, "tools": [{"type": "code_interpreter"}]} for fid in file_ids]
    )

    run = openai.beta.threads.runs.create(thread_id=thread.id, assistant_id=agent_id)

    with st.spinner("♻️ Running AI sustainability analysis..."):
        while run.status not in ["completed", "failed"]:
            time.sleep(2)
            run = openai.beta.threads.runs.retrieve(run.id, thread_id=thread.id)

    # === Process result ===
    messages = openai.beta.threads.messages.list(thread_id=thread.id)
    for msg in messages.data[::-1]:
        if msg.role == "assistant":
            raw = msg.content[0].text.value
            match = re.search(r"\{[\s\S]*\}", raw)
            if match:
                try:
                    result = json.loads(match.group(0))

                    # === Nicely formatted output ===
                    st.subheader("📋 Sustainability Analysis Summary")
                    st.write(result.get("summary", "No summary provided."))

                    st.markdown("### 💰 Economic Sustainability")
                    col1, col2, col3 = st.columns(3)
                    col1.metric("Total Milk Income", f"{result['sustainability']['economic']['total_milk_income']:.2f} CZK")
                    col2.metric("Treatment Costs", f"{result['sustainability']['economic']['total_treatment_costs']:.2f} CZK")
                    col3.metric("Monthly Profit/Loss", f"{result['sustainability']['economic']['monthly_profit_loss']:.2f} CZK")

                    st.markdown("### 🌱 Environmental Sustainability")
                    col4, col5 = st.columns(2)
                    col4.metric("Antibiotic Usage Frequency", result['sustainability']['environmental']['antibiotic_usage_frequency'])
                    col5.metric("Treatment Intensity", f"{result['sustainability']['environmental']['treatment_intensity']:.2f}")

                    st.markdown("### 🐄 Animal Welfare")
                    col6, col7, col8 = st.columns(3)
                    col6.metric("Sick Cows (%)", f"{result['sustainability']['animal_welfare']['percentage_sick_cows']:.1f} %")
                    col7.metric("Avg. Treatment Duration", f"{result['sustainability']['animal_welfare']['avg_treatment_duration']:.2f} days")
                    col8.metric("High-Risk Animals (%)", f"{result['sustainability']['animal_welfare']['high_risk_animals_percentage']:.1f} %")

                    st.markdown("### 💡 Recommendations")
                    for rec in result.get("recommendations", []):
                        st.markdown(f"- {rec}")

                except Exception as e:
                    st.error(f"❌ JSON parsing error: {e}")
                    st.code(match.group(0))
            else:
                st.warning("⚠️ AI agent did not return JSON:")
                st.markdown(raw)
            break
