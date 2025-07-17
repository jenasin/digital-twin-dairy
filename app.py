import streamlit as st
import openai
import os
import pandas as pd
import time
import json
import re

# === OpenAI API Key ===
openai.api_key = st.secrets["OPENAI_API_KEY"]

# === Load assistant ID ===
agent_id = st.secrets["dairy_sustainability_agent"]["id"]

# === Base folder for all farms ===
FOLDER_BASE = "streamlet/farm_data"
os.makedirs(FOLDER_BASE, exist_ok=True)

# === Farm selection or creation ===
st.sidebar.title("🐄 Dairy Twin AI")

mode = st.sidebar.radio("🔄 Select Mode", ["🔍 Select existing farm", "➕ Create new farm"])
existing_farms = [d for d in os.listdir(FOLDER_BASE) if os.path.isdir(os.path.join(FOLDER_BASE, d))]

farm_name = None
if mode == "🔍 Select existing farm":
    if not existing_farms:
        st.sidebar.warning("No farms found.")
        st.stop()
    farm_name = st.sidebar.selectbox("🧑‍🌾 Choose a farm", existing_farms)
elif mode == "➕ Create new farm":
    farm_name = st.sidebar.text_input("✍️ Enter new farm name")

if not farm_name:
    st.warning("Please select or enter a farm name.")
    st.stop()

st.session_state["farm_name"] = farm_name

# === Folder for selected farm ===
FOLDER = os.path.join(FOLDER_BASE, farm_name.replace(" ", "_"))
os.makedirs(FOLDER, exist_ok=True)

# === Sidebar menu ===
view = st.sidebar.radio("📋 Menu", [
    "🧪 Run Sustainability Analysis",
    "📂 Farm Files Overview",
    "📊 View Last Report",
    "📈 Trends & Visual Insights",
    "🌍 Farm Location & Profile"
])

st.title(f"🐄 Dairy Sustainability AI – `{farm_name}`")

# === 1. Run analysis ===
if view == "🧪 Run Sustainability Analysis":
    uploaded_files = st.file_uploader("📂 Upload your farm CSV files", type="csv", accept_multiple_files=True)
    file_ids = []

    if uploaded_files:
        st.subheader("📥 Uploaded Data Preview")
        for file in uploaded_files:
            df = pd.read_csv(file)
            st.dataframe(df.head())
            path = os.path.join(FOLDER, file.name)
            df.to_csv(path, index=False)
            uploaded = openai.files.create(file=open(path, "rb"), purpose="assistants")
            file_ids.append(uploaded.id)

    if file_ids and st.button("🚀 Run Sustainability Analysis"):
        thread = openai.beta.threads.create()

        openai.beta.threads.messages.create(
            thread_id=thread.id,
            role="user",
            content="""
You are an AI agent analyzing dairy farm sustainability.

Strictly return your output as valid JSON in this format:

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
    "Recommendation 1",
    "Recommendation 2",
    "Recommendation 3"
  ]
}

Do NOT include explanations. Only return valid JSON.
""",
            attachments=[{"file_id": fid, "tools": [{"type": "code_interpreter"}]} for fid in file_ids]
        )

        run = openai.beta.threads.runs.create(thread_id=thread.id, assistant_id=agent_id)

        with st.spinner("♻️ Running sustainability analysis..."):
            while run.status not in ["completed", "failed"]:
                time.sleep(2)
                run = openai.beta.threads.runs.retrieve(run.id, thread_id=thread.id)

        messages = openai.beta.threads.messages.list(thread_id=thread.id)
        for msg in messages.data[::-1]:
            if msg.role == "assistant":
                raw = msg.content[0].text.value
                match = re.search(r"\{[\s\S]*\}", raw)
                if match:
                    try:
                        result = json.loads(match.group(0))
                        with open(os.path.join(FOLDER, "sustainability_report.json"), "w") as f:
                            json.dump(result, f, indent=2)

                        st.success("✅ Analysis completed and saved.")
                        st.experimental_rerun()

                    except Exception as e:
                        st.error(f"❌ JSON parsing error: {e}")
                        st.code(match.group(0))
                else:
                    st.warning("⚠️ AI did not return valid JSON.")
                    st.markdown(raw)
                break

# === 2. View last result ===
elif view == "📊 View Last Report":
    report_path = os.path.join(FOLDER, "sustainability_report.json")
    if not os.path.exists(report_path):
        st.warning("No analysis report found. Run analysis first.")
    else:
        with open(report_path, "r") as f:
            result = json.load(f)

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
            st.success(f"• {rec}")

elif view == "📂 Farm Files Overview":
    st.title(f"📂 Uploaded Files for Farm: {farm_name}")

    files = os.listdir(FOLDER)
    if not files:
        st.warning("No files found for this farm.")
    else:
        for file in sorted(files):
            file_path = os.path.join(FOLDER, file)
            st.markdown(f"---\n### 📄 {file}")

            # Náhled obsahu souboru (jen CSV/JSON)
            if file.endswith(".csv"):
                try:
                    df = pd.read_csv(file_path)
                    st.dataframe(df)
                except Exception as e:
                    st.error(f"Unable to read CSV: {e}")
            elif file.endswith(".json"):
                try:
                    with open(file_path, "r") as f:
                        data = json.load(f)
                        st.json(data)
                except Exception as e:
                    st.error(f"Unable to read JSON: {e}")

            # Tlačítko pro stažení
            with open(file_path, "rb") as f:
                st.download_button(f"⬇️ Download {file}", f.read(), file_name=file)


# === 3. Graphs ===
elif view == "📈 Trends & Visual Insights":
    st.title("📈 Trends & Visual Insights")

    milk_df = None
    treatment_df = None

    for file in os.listdir(FOLDER):
        if "milk" in file.lower():
            milk_df = pd.read_csv(os.path.join(FOLDER, file))
        elif "treat" in file.lower():
            treatment_df = pd.read_csv(os.path.join(FOLDER, file))

    if milk_df is None or treatment_df is None:
        st.warning("Missing 'milk_yield' or 'treatment' CSV files.")
    else:
        st.subheader("📊 Sick Cows Over Time")
        if 'treatment_date' in treatment_df.columns:
            treatment_df['treatment_date'] = pd.to_datetime(treatment_df['treatment_date'])
            sick_counts = treatment_df.groupby('treatment_date').size().reset_index(name='sick_cows')
            st.line_chart(sick_counts.set_index('treatment_date'))

        st.subheader("🧪 Milk Yield vs. Treatments per Cow")
        if 'animal_id' in milk_df.columns and 'milk_yield' in milk_df.columns:
            yield_per_cow = milk_df.groupby('animal_id')['milk_yield'].sum()
            treatments_per_cow = treatment_df.groupby('animal_id').size()
            merged = pd.DataFrame({
                'milk_yield': yield_per_cow,
                'treatments': treatments_per_cow
            }).dropna()
            st.scatter_chart(merged)
            correlation = merged.corr().iloc[0,1]
            st.info(f"📉 Correlation between treatments and milk yield: **{correlation:.2f}**")

        st.subheader("⏱️ Avg. Treatment Duration (if available)")
        if 'duration' in treatment_df.columns:
            st.bar_chart(treatment_df['duration'])

elif view == "🌍 Farm Location & Profile":
    import farm_profile_view  # spustí se přes streamlit