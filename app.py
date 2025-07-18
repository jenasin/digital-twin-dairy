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
    "📈 Milk Production Forecast",
    "🥕 Feed Optimization",
    "♻️ Biogas & Manure",
    "🌦️ Weather & Climate",
    "🩺 Health Monitoring",
    "🌍 Sustainability Dashboard"
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


# === 1. Milk Production Forecast ===
elif view == "📈 Milk Production Forecast":
    st.title("📈 Milk Production Forecast")
    
    # === Načtení dat ===
    farm_name = st.session_state.get("farm_name")
    FOLDER = os.path.join("streamlet/farm_data", farm_name.replace(" ", "_"))
    if not os.path.exists(FOLDER):
        st.warning("Farm folder not found.")
        st.stop()

    data_files = [os.path.join(FOLDER, f) for f in os.listdir(FOLDER) if f.endswith(".csv") or f.endswith(".json")]
    if not data_files:
        st.warning("No data files found for this farm.")
        st.stop()

    attachments = []
    for path in data_files:
        with open(path, "rb") as f:
            uploaded = openai.files.create(file=f, purpose="assistants")
            attachments.append({"file_id": uploaded.id, "tools": [{"type": "code_interpreter"}]})

    prompt = """
You are a dairy farm assistant. Based on the uploaded data files (milk yield, animals, treatments, etc.),
analyze milk production trends. Return:
- Average daily yield
- Recent 7-day trend
- Forecast for the next 3 days
- Any risks or drops in production
Respond in English. Do not use markdown.
"""

    thread = openai.beta.threads.create()
    openai.beta.threads.messages.create(
        thread_id=thread.id,
        role="user",
        content=prompt,
        attachments=attachments
    )
    run = openai.beta.threads.runs.create(thread_id=thread.id, assistant_id=st.secrets["dairy_sustainability_agent"]["id"])

    with st.spinner("🔍 Analyzing milk production trends..."):
        while run.status not in ["completed", "failed"]:
            time.sleep(2)
            run = openai.beta.threads.runs.retrieve(run.id, thread_id=thread.id)

    messages = openai.beta.threads.messages.list(thread_id=thread.id)
    for msg in messages.data[::-1]:
        if msg.role == "assistant":
            st.subheader("📋 Milk Production Report")
            response = msg.content[0].text.value.strip()
            sections = response.split("\n")
            for line in sections:
                if ":" in line:
                    key, value = line.split(":", 1)
                    st.markdown(f"**{key.strip()}**: {value.strip()}")
                else:
                    st.write(line)
            break

elif view == "🥕 Feed Optimization":
    st.title("🥕 Feed Optimization for Herd Management")

    farm_name = st.session_state.get("farm_name")
    FOLDER = os.path.join("streamlet/farm_data", farm_name.replace(" ", "_"))
    report_path = os.path.join(FOLDER, "feed_optimization_report.txt")

    if not os.path.exists(FOLDER):
        st.warning("Farm folder not found.")
        st.stop()

    st.markdown("### 📋 Feed Optimization Report")

    # === Show saved report if exists ===
    if os.path.exists(report_path):
        with open(report_path, "r", encoding="utf-8") as f:
            saved_report = f.read().replace("```markdown", "").replace("```", "").replace("undefined", "").strip()

            # Rozdělit na sekce podle nadpisů
            sections = saved_report.split("## ")
            for section in sections:
                if section.strip():
                    lines = section.strip().split("\n")
                    title = lines[0]
                    content = "\n".join(lines[1:])
                    with st.expander(title.strip(), expanded=True):
                        st.markdown(content)
        st.info("📁 Loaded from saved report.")
    else:
        st.info("No saved report found. Click below to generate a new one.")

    # === Button to run analysis ===
    if st.button("🔄 Run Feed Analysis"):
        data_files = [
            os.path.join(FOLDER, f)
            for f in os.listdir(FOLDER)
            if f.endswith(".csv") or f.endswith(".json")
        ]

        if not data_files:
            st.warning("No data files found.")
            st.stop()

        attachments = []
        for path in data_files:
            with open(path, "rb") as f:
                uploaded = openai.files.create(file=f, purpose="assistants")
                attachments.append({
                    "file_id": uploaded.id,
                    "tools": [{"type": "code_interpreter"}]
                })

        prompt = """
You are a feed advisor for dairy cows.

Use the following data files (milk yield, cow info, treatments, cost) to generate a clear, structured report.

Return in plain Markdown (NO code blocks) and include only the following sections:

## 🥛 Underperforming Cows
- List cows with low milk yield and high lactation number.
- Add concrete suggestions (e.g. energy supplements).

## 🐘 Over-conditioned Cows
- List cows with low output but high age/lactation and good health.
- Suggest reducing feeding or changing rations.

## 🧪 Feed Strategy Recommendations
- Summary of changes (reduce/increase).
- Suggestions on nutrient balancing.

No introductions, no explanations. Respond only with the report in plain Markdown (no ```markdown).
        """

        thread = openai.beta.threads.create()
        openai.beta.threads.messages.create(
            thread_id=thread.id,
            role="user",
            content=prompt,
            attachments=attachments
        )

        run = openai.beta.threads.runs.create(
            thread_id=thread.id,
            assistant_id=st.secrets["dairy_sustainability_agent"]["id"]
        )

        with st.spinner("🐄 Optimizing feeding strategy..."):
            while run.status not in ["completed", "failed"]:
                time.sleep(2)
                run = openai.beta.threads.runs.retrieve(run.id, thread_id=thread.id)

        messages = openai.beta.threads.messages.list(thread_id=thread.id)
        for msg in messages.data[::-1]:
            if msg.role == "assistant":
                report = msg.content[0].text.value
                report_clean = report.replace("```markdown", "").replace("```", "").replace("undefined", "").strip()

                # Save report
                with open(report_path, "w", encoding="utf-8") as f:
                    f.write(report_clean)

                # Show report nicely
                sections = report_clean.split("## ")
                for section in sections:
                    if section.strip():
                        lines = section.strip().split("\n")
                        title = lines[0]
                        content = "\n".join(lines[1:])
                        with st.expander(title.strip(), expanded=True):
                            st.markdown(content)

                st.success("✅ New report generated and saved.")
                break

    # Tlačítko "zpět nahoru"
    st.markdown("---")
    st.markdown("<a href='#top' style='font-size:20px;'>⬆️ Back to Top</a>", unsafe_allow_html=True)

elif view == "♻️ Biogas & Manure":
    st.title("♻️ Biogas and Manure Utilization")

    farm_name = st.session_state.get("farm_name")
    FOLDER = os.path.join("streamlet/farm_data", farm_name.replace(" ", "_"))
    report_path = os.path.join(FOLDER, "biogas_manure_report.txt")

    if not os.path.exists(FOLDER):
        st.warning("Farm folder not found.")
        st.stop()

    st.markdown("### 📋 Biogas & Manure Report")

    # === Show saved report if exists ===
    if os.path.exists(report_path):
        with open(report_path, "r", encoding="utf-8") as f:
            saved_report = f.read().replace("```markdown", "").replace("```", "").replace("undefined", "").strip()

            # Split into sections
            sections = saved_report.split("## ")
            for section in sections:
                if section.strip():
                    lines = section.strip().split("\n")
                    title = lines[0]
                    content = "\n".join(lines[1:])
                    with st.expander(title.strip(), expanded=True):
                        st.markdown(content)
        st.info("📁 Loaded from saved report.")
    else:
        st.info("No saved report found. Click below to generate a new one.")

    # === Button to run analysis ===
    if st.button("🔄 Run Biogas Analysis"):
        data_files = [
            os.path.join(FOLDER, f)
            for f in os.listdir(FOLDER)
            if f.endswith(".csv") or f.endswith(".json")
        ]

        if not data_files:
            st.warning("No data files found.")
            st.stop()

        attachments = []
        for path in data_files:
            with open(path, "rb") as f:
                uploaded = openai.files.create(file=f, purpose="assistants")
                attachments.append({
                    "file_id": uploaded.id,
                    "tools": [{"type": "code_interpreter"}]
                })

        prompt = """
You are an expert in farm waste management and renewable energy.

Using the provided files (manure data, biogas capacity, cow excretion records), generate a structured Markdown report with the following:

## 💩 Manure Production Overview
- Estimate total manure output per day/month.
- Identify which cow groups produce the most manure.

## ⚡️ Biogas Capacity & Usage
- Compare manure production with biogas plant capacity.
- Identify if there's excess/insufficient manure for optimal biogas production.

## 🔧 Recommendations
- Suggest optimization of manure collection.
- Recommend strategies for improving biogas conversion efficiency.
- If applicable, suggest how to use excess manure (e.g., fertilizer, compost).

Do NOT include any explanations. Respond only with the report. Do NOT use code blocks.
        """

        thread = openai.beta.threads.create()
        openai.beta.threads.messages.create(
            thread_id=thread.id,
            role="user",
            content=prompt,
            attachments=attachments
        )

        run = openai.beta.threads.runs.create(
            thread_id=thread.id,
            assistant_id=st.secrets["dairy_sustainability_agent"]["id"]
        )

        with st.spinner("🥼 Generating biogas & manure strategy..."):
            while run.status not in ["completed", "failed"]:
                time.sleep(2)
                run = openai.beta.threads.runs.retrieve(run.id, thread_id=thread.id)

        messages = openai.beta.threads.messages.list(thread_id=thread.id)
        for msg in messages.data[::-1]:
            if msg.role == "assistant":
                report = msg.content[0].text.value
                report_clean = report.replace("```markdown", "").replace("```", "").replace("undefined", "").strip()

                with open(report_path, "w", encoding="utf-8") as f:
                    f.write(report_clean)

                sections = report_clean.split("## ")
                for section in sections:
                    if section.strip():
                        lines = section.strip().split("\n")
                        title = lines[0]
                        content = "\n".join(lines[1:])
                        with st.expander(title.strip(), expanded=True):
                            st.markdown(content)

                st.success("✅ New report generated and saved.")
                break

    st.markdown("---")
    st.markdown("<a href='#top' style='font-size:20px;'>⬆️ Back to Top</a>", unsafe_allow_html=True)

elif view == "🌦️ Weather & Climate":
    st.title("🌦️ Weather & Climate Impact")

    farm_name = st.session_state.get("farm_name")
    FOLDER = os.path.join("streamlet/farm_data", farm_name.replace(" ", "_"))
    report_path = os.path.join(FOLDER, "weather_climate_report.txt")

    if not os.path.exists(FOLDER):
        st.warning("Farm folder not found.")
        st.stop()

    st.markdown("### 📋 Weather & Climate Analysis Report")

    if os.path.exists(report_path):
        with open(report_path, "r", encoding="utf-8") as f:
            saved_report = f.read().replace("```markdown", "").replace("```", "").replace("undefined", "").strip()
            sections = saved_report.split("## ")
            for section in sections:
                if section.strip():
                    lines = section.strip().split("\n")
                    title = lines[0]
                    content = "\n".join(lines[1:])
                    with st.expander(title.strip(), expanded=True):
                        st.markdown(content)
        st.info("📁 Loaded from saved report.")
    else:
        st.info("No saved report found. Click below to generate a new one.")

    if st.button("🔄 Run Weather Analysis"):
        data_files = [
            os.path.join(FOLDER, f)
            for f in os.listdir(FOLDER)
            if f.endswith(".csv") or f.endswith(".json")
        ]

        if not data_files:
            st.warning("No data files found.")
            st.stop()

        attachments = []
        for path in data_files:
            with open(path, "rb") as f:
                uploaded = openai.files.create(file=f, purpose="assistants")
                attachments.append({
                    "file_id": uploaded.id,
                    "tools": [{"type": "code_interpreter"}]
                })

        prompt = """
You are a weather and climate impact analyst for dairy farms.

Based on the uploaded weather and farm data (precipitation, temperature, treatments, yield), generate a professional Markdown report with the following structure:

## 🌫️ Climate Trends
- Describe relevant patterns in temperature, precipitation or extreme events.
- Note any seasonal or long-term trends.

## 💧 Impact on Production
- Highlight effects on milk yield or feed needs due to weather.
- Mention possible droughts, heat stress, or wet conditions.

## 🧠 Recommendations
- Suggest actions like weather protection, irrigation, or ventilation.
- Mention adaptation strategies for upcoming climate variability.

Respond only in plain Markdown (NO code blocks).
        """

        thread = openai.beta.threads.create()
        openai.beta.threads.messages.create(
            thread_id=thread.id,
            role="user",
            content=prompt,
            attachments=attachments
        )

        run = openai.beta.threads.runs.create(
            thread_id=thread.id,
            assistant_id=st.secrets["dairy_sustainability_agent"]["id"]
        )

        with st.spinner("🌬️ Analyzing climate impact..."):
            while run.status not in ["completed", "failed"]:
                time.sleep(2)
                run = openai.beta.threads.runs.retrieve(run.id, thread_id=thread.id)

        messages = openai.beta.threads.messages.list(thread_id=thread.id)
        for msg in messages.data[::-1]:
            if msg.role == "assistant":
                report = msg.content[0].text.value
                report_clean = report.replace("```markdown", "").replace("```", "").replace("undefined", "").strip()

                with open(report_path, "w", encoding="utf-8") as f:
                    f.write(report_clean)

                sections = report_clean.split("## ")
                for section in sections:
                    if section.strip():
                        lines = section.strip().split("\n")
                        title = lines[0]
                        content = "\n".join(lines[1:])
                        with st.expander(title.strip(), expanded=True):
                            st.markdown(content)

                st.success("✅ New weather report generated and saved.")
                break

    st.markdown("---")
    st.markdown("<a href='#top' style='font-size:20px;'>⬆️ Back to Top</a>", unsafe_allow_html=True)

elif view == "🩺 Health Monitoring":
    st.title("🩺 Health Monitoring")

    farm_name = st.session_state.get("farm_name")
    FOLDER = os.path.join("streamlet/farm_data", farm_name.replace(" ", "_"))
    report_path = os.path.join(FOLDER, "health_monitoring_report.txt")

    if not os.path.exists(FOLDER):
        st.warning("Farm folder not found.")
        st.stop()

    st.markdown("### 📋 Health Status Report")

    # === Show saved report if exists ===
    if os.path.exists(report_path):
        with open(report_path, "r", encoding="utf-8") as f:
            saved_report = f.read().replace("```markdown", "").replace("```", "").replace("undefined", "").strip()
            sections = saved_report.split("## ")
            for section in sections:
                if section.strip():
                    lines = section.strip().split("\n")
                    title = lines[0]
                    content = "\n".join(lines[1:])
                    with st.expander(title.strip(), expanded=True):
                        st.markdown(content)
        st.info("📁 Loaded from saved report.")
    else:
        st.info("No saved report found. Click below to generate a new one.")

    # === Button to run analysis ===
    if st.button("🔄 Run Health Analysis"):
        data_files = [
            os.path.join(FOLDER, f)
            for f in os.listdir(FOLDER)
            if f.endswith(".csv") or f.endswith(".json")
        ]

        if not data_files:
            st.warning("No data files found.")
            st.stop()

        attachments = []
        for path in data_files:
            with open(path, "rb") as f:
                uploaded = openai.files.create(file=f, purpose="assistants")
                attachments.append({
                    "file_id": uploaded.id,
                    "tools": [{"type": "code_interpreter"}]
                })

        prompt = """
You are a veterinary health advisor for dairy farms.

Using the provided data files (diagnoses, treatments, cow health, productivity), return a structured health status report.

Return in plain Markdown (NO code blocks). Include exactly these sections:

## 🧾 Key Health Metrics
- Total number of treated cows
- Average treatment duration
- Most common diagnoses

## 🚨 High-Risk Animals
- List of animal IDs (or summaries) with repeated or severe diseases
- Suggested monitoring or preventive measures

## 💊 Recommendations
- Preventive strategies to reduce illness rate
- Suggestions for improving herd health management

Do not add introductions or explanations. Return ONLY the report.
        """

        thread = openai.beta.threads.create()
        openai.beta.threads.messages.create(
            thread_id=thread.id,
            role="user",
            content=prompt,
            attachments=attachments
        )

        run = openai.beta.threads.runs.create(
            thread_id=thread.id,
            assistant_id=st.secrets["dairy_sustainability_agent"]["id"]
        )

        with st.spinner("🩺 Analyzing herd health data..."):
            while run.status not in ["completed", "failed"]:
                time.sleep(2)
                run = openai.beta.threads.runs.retrieve(run.id, thread_id=thread.id)

        messages = openai.beta.threads.messages.list(thread_id=thread.id)
        for msg in messages.data[::-1]:
            if msg.role == "assistant":
                report = msg.content[0].text.value
                report_clean = report.replace("```markdown", "").replace("```", "").replace("undefined", "").strip()

                with open(report_path, "w", encoding="utf-8") as f:
                    f.write(report_clean)

                sections = report_clean.split("## ")
                for section in sections:
                    if section.strip():
                        lines = section.strip().split("\n")
                        title = lines[0]
                        content = "\n".join(lines[1:])
                        with st.expander(title.strip(), expanded=True):
                            st.markdown(content)

                st.success("✅ New report generated and saved.")
                break

    # Back to top link
    st.markdown("---")
    st.markdown("<a href='#top' style='font-size:20px;'>⬆️ Back to Top</a>", unsafe_allow_html=True)

elif view == "🌍 Sustainability Dashboard":
    st.title("🌍 Sustainability Dashboard")

    farm_name = st.session_state.get("farm_name")
    FOLDER = os.path.join("streamlet/farm_data", farm_name.replace(" ", "_"))
    report_path = os.path.join(FOLDER, "sustainability_dashboard_report.txt")

    if not os.path.exists(FOLDER):
        st.warning("Farm folder not found.")
        st.stop()

    st.markdown("### 📋 Sustainability Report")

    # === Show saved report if it exists ===
    if os.path.exists(report_path):
        with open(report_path, "r", encoding="utf-8") as f:
            saved_report = f.read().replace("```markdown", "").replace("```", "").replace("undefined", "").strip()
            sections = saved_report.split("## ")
            for section in sections:
                if section.strip():
                    lines = section.strip().split("\n")
                    title = lines[0]
                    content = "\n".join(lines[1:])
                    with st.expander(title.strip(), expanded=True):
                        st.markdown(content)
        st.info("📁 Loaded from saved report.")
    else:
        st.info("No saved report found. Click below to generate a new one.")

    # === Button to run analysis ===
    if st.button("🔄 Run Sustainability Analysis"):
        data_files = [
            os.path.join(FOLDER, f)
            for f in os.listdir(FOLDER)
            if f.endswith(".csv") or f.endswith(".json")
        ]

        if not data_files:
            st.warning("No data files found.")
            st.stop()

        attachments = []
        for path in data_files:
            with open(path, "rb") as f:
                uploaded = openai.files.create(file=f, purpose="assistants")
                attachments.append({
                    "file_id": uploaded.id,
                    "tools": [{"type": "code_interpreter"}]
                })

        prompt = """
You are a sustainability advisor for dairy farms.

Using the provided farm data (economy, health, environment), return a structured sustainability dashboard.

Return in plain Markdown (NO code blocks). Include exactly the following sections:

## 💰 Economic Overview
- Monthly milk income
- Total treatment and feed costs
- Profit or loss summary

## 🐄 Animal Health Status
- % of treated cows
- Average duration of treatments
- Risk profile of the herd

## 🌱 Environmental Metrics
- Antibiotic usage (if data available)
- Manure production (estimates if needed)
- Any sustainability concerns

## ✅ Recommendations
- Actionable suggestions to improve sustainability in each area

Do NOT explain what you're doing. Return ONLY the formatted report.
        """

        thread = openai.beta.threads.create()
        openai.beta.threads.messages.create(
            thread_id=thread.id,
            role="user",
            content=prompt,
            attachments=attachments
        )

        run = openai.beta.threads.runs.create(
            thread_id=thread.id,
            assistant_id=st.secrets["dairy_sustainability_agent"]["id"]
        )

        with st.spinner("🌍 Generating sustainability dashboard..."):
            while run.status not in ["completed", "failed"]:
                time.sleep(2)
                run = openai.beta.threads.runs.retrieve(run.id, thread_id=thread.id)

        messages = openai.beta.threads.messages.list(thread_id=thread.id)
        for msg in messages.data[::-1]:
            if msg.role == "assistant":
                report = msg.content[0].text.value
                report_clean = report.replace("```markdown", "").replace("```", "").replace("undefined", "").strip()

                with open(report_path, "w", encoding="utf-8") as f:
                    f.write(report_clean)

                sections = report_clean.split("## ")
                for section in sections:
                    if section.strip():
                        lines = section.strip().split("\n")
                        title = lines[0]
                        content = "\n".join(lines[1:])
                        with st.expander(title.strip(), expanded=True):
                            st.markdown(content)

                st.success("✅ New report generated and saved.")
                break

    # Back to top link
    st.markdown("---")
    st.markdown("<a href='#top' style='font-size:20px;'>⬆️ Back to Top</a>", unsafe_allow_html=True)
