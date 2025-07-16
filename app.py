import streamlit as st
import openai
import pandas as pd
import time
import os
import json
import ast

# === NAČTENÍ API KLÍČE ===
openai.api_key = st.secrets["OPENAI_API_KEY"]

# === BEZPEČNÁ INICIALIZACE session_state ===
for key in ["controller_id", "farm_id", "cow_id", "uploaded_data"]:
    if key not in st.session_state:
        st.session_state[key] = None if key != "uploaded_data" else {}

# === NAČTENÍ agent ID ze souboru ===
agent_path = "agents.json"
if os.path.exists(agent_path):
    with open(agent_path, "r") as f:
        ids = json.load(f)
        st.session_state.controller_id = ids.get("controller_id")
        st.session_state.farm_id = ids.get("farm_id")
        st.session_state.cow_id = ids.get("cow_id")

# === MENU ===
st.sidebar.title("🔧 Menu")
section = st.sidebar.radio("Select section:", [
    "Overview",
    "Create Agents",
    "Upload CSV Data",
    "Farm Data",
    "Analyze Farm Data",
    "Simulate Digital Twin",   # 🧠 nová sekce
    "RAG to Agents",
    "Run Digital Twin Analysis",
    "Ask the Assistant",
    "📈 AI Competition Insights",
    "📤 Export Insights (JSON)"
])


# === SEKCE: Upload CSV ===
if section == "Upload CSV Data":
    st.title("📂 Upload and Store Farm CSV Files")
    uploaded_files = st.file_uploader("Upload multiple farm-related CSV files", accept_multiple_files=True)

    if uploaded_files:
        os.makedirs("farm_data", exist_ok=True)  # vytvoř složku, pokud neexistuje

        for f in uploaded_files:
            df = pd.read_csv(f)
            st.session_state.uploaded_data[f.name] = df
            df.to_csv(os.path.join("farm_data", f.name), index=False)  # uložit lokálně do složky
            st.success(f"✅ Uploaded and saved `{f.name}` to farm_data/")
            st.dataframe(df.head())

if section == "Farm Data":
    st.title("📊 Farm Data Viewer and Editor")

    # načti soubory ze složky farm_data/
    folder_path = "farm_data"
    if not st.session_state.uploaded_data and os.path.exists(folder_path):
        for file in os.listdir(folder_path):
            if file.endswith(".csv"):
                file_path = os.path.join(folder_path, file)
                df = pd.read_csv(file_path)
                st.session_state.uploaded_data[file] = df

    if not st.session_state.uploaded_data:
        st.info("ℹ️ No data uploaded yet. Go to 'Upload CSV Data' section.")
    else:
        selected_file = st.selectbox("Choose a file:", options=list(st.session_state.uploaded_data.keys()))
        df = st.session_state.uploaded_data[selected_file]
        st.markdown(f"### ✏️ Edit `{selected_file}`")
        edited_df = st.data_editor(df, num_rows="dynamic", use_container_width=True)

        if st.button("💾 Save changes"):
            st.session_state.uploaded_data[selected_file] = edited_df
            edited_df.to_csv(os.path.join("farm_data", selected_file), index=False)
            st.success(f"✅ Changes saved for `{selected_file}`.")

        st.download_button(
            label="⬇️ Download CSV",
            data=edited_df.to_csv(index=False),
            file_name=selected_file,
            mime="text/csv"
        )

        if st.button("🗑️ Delete file"):
            del st.session_state.uploaded_data[selected_file]
            os.remove(os.path.join("farm_data", selected_file))
            st.success(f"❌ `{selected_file}` removed.")
            st.experimental_rerun()


# === SEKCE: Agent Overview ===
if section == "Overview":
    st.title("📋 Agent Overview")
    try:
        agents = openai.beta.assistants.list().data
        if not agents:
            st.warning("⚠️ No agents found.")
        else:
            df = pd.DataFrame([{
                "Name": agent.name,
                "ID": agent.id,
                "Model": agent.model,
                "Tools": [t.type for t in agent.tools] if agent.tools else [],
            } for agent in agents])
            st.success(f"🧠 Found {len(agents)} agent(s).")
            st.dataframe(df)

            controller = st.selectbox("🧠 Controller Agent", options=[a.name for a in agents], key="controller")
            farm = st.selectbox("🐄 Farm Agent", options=[a.name for a in agents], key="farm")
            cow = st.selectbox("🐮 Cow Agent", options=[a.name for a in agents], key="cow")

            if st.button("💾 Save selection"):
                get_id = lambda name: next((a.id for a in agents if a.name == name), None)
                agent_ids = {
                    "controller_id": get_id(controller),
                    "farm_id": get_id(farm),
                    "cow_id": get_id(cow)
                }
                with open("agents.json", "w") as f:
                    json.dump(agent_ids, f)
                st.success("✅ Saved agents.json!")

    except Exception as e:
        st.error(f"Error fetching agents: {str(e)}")

# === SEKCE: Create Agents ===
if section == "Create Agents":
    st.title("🤖 Agent Creator – Digital Twin Dairy Farm")

    if st.button("🛠️ Create Agents"):
        with st.spinner("Creating agents..."):
            controller = openai.beta.assistants.create(
                name="ControllerAgent",
                instructions="""
                    You are the ControllerAgent.
                    Your job is NOT to answer directly.
                    You receive the user question and decide:
                    - If it's about total milk, farm costs, or average yield → send to FarmAgent.
                    - If it's about cow health, treatment, or milk yield per animal → send to CowAgent.
                    Always answer clearly in this format:
                    'Route to: CowAgent' or 'Route to: FarmAgent'
                """,
                model="gpt-4o"
            )

            farm = openai.beta.assistants.create(
                name="FarmAgent",
                instructions="Analyze farm-level CSV data (milk yield, treatment costs, finances).",
                model="gpt-4o",
                tools=[{"type": "code_interpreter"}]
            )

            cow = openai.beta.assistants.create(
                name="CowAgent",
                instructions="Analyze individual cow records: milk yield, health risk, and treatment data.",
                model="gpt-4o",
                tools=[{"type": "code_interpreter"}]
            )

            agent_ids = {
                "controller_id": controller.id,
                "farm_id": farm.id,
                "cow_id": cow.id
            }

            with open("agents.json", "w") as f:
                json.dump(agent_ids, f)

            st.session_state.controller_id = controller.id
            st.session_state.farm_id = farm.id
            st.session_state.cow_id = cow.id

            st.success("✅ Agents created and saved!")
            st.code(f"Controller ID: {controller.id}")
            st.code(f"FarmAgent ID: {farm.id}")
            st.code(f"CowAgent ID:  {cow.id}")

elif section == "Simulate Digital Twin":
    st.title("🧠 Simulate Digital Twin of Your Dairy Farm")

    st.markdown("This simulation will run:")
    st.markdown("- 🧠 ControllerAgent: understand and assign tasks")
    st.markdown("- 🐄 FarmAgent: analyze economic and yield data")
    st.markdown("- 🐮 CowAgent: analyze cow health and performance")

    if st.button("🚀 Run Simulation"):
        file_ids = []
        thread = openai.beta.threads.create()

        # nahraj CSV soubory z farm_data/
        folder = "farm_data"
        if os.path.exists(folder):
            for name in os.listdir(folder):
                if name.endswith(".csv"):
                    path = os.path.join(folder, name)
                    uploaded = openai.files.create(file=open(path, "rb"), purpose="assistants")
                    file_ids.append(uploaded.id)

        # vytvoř controller prompt
        controller_prompt = (
            "You are the ControllerAgent of a digital twin dairy farm.\n"
            "You are now simulating farm operations based on the provided CSV data.\n"
            "1. Identify farm-level vs per-animal data.\n"
            "2. Assign appropriate data to FarmAgent or CowAgent.\n"
            "3. Summarize what each agent is doing."
        )

        # vlož zprávu s přílohami
        openai.beta.threads.messages.create(
            thread_id=thread.id,
            role="user",
            content=controller_prompt,
            attachments=[
                {"file_id": fid, "tools": [{"type": "code_interpreter"}]} for fid in file_ids
            ]
        )

        # spusť controller
        run = openai.beta.threads.runs.create(
            thread_id=thread.id,
            assistant_id=st.session_state.controller_id
        )

        with st.spinner("🧠 ControllerAgent is assigning tasks..."):
            while run.status not in ["completed", "failed"]:
                time.sleep(1)
                run = openai.beta.threads.runs.retrieve(run.id, thread_id=thread.id)

        messages = openai.beta.threads.messages.list(thread_id=thread.id)
        for msg in messages.data[::-1]:
            if msg.role == "assistant":
                st.markdown("### 🤖 Controller Summary:")
                st.markdown(msg.content[0].text.value)
                break

        # ➕ volitelně můžeš přidat automatické spuštění Cow a Farm Agentů zde

elif section == "Analyze Farm Data":
    st.title("📈 Load CSV from farm_data/ and analyze with Agents")

    if not os.path.exists("farm_data") or not os.listdir("farm_data"):
        st.warning("⚠️ No CSV files found in `farm_data/` directory.")
    else:
        files = [f for f in os.listdir("farm_data") if f.endswith(".csv")]
        st.markdown("### 📂 Files found:")
        st.write(files)

        if st.button("📤 Upload & Analyze via Controller"):
            file_ids = []
            thread = openai.beta.threads.create()

            for f_name in files:
                file_path = os.path.join("farm_data", f_name)
                uploaded = openai.files.create(file=open(file_path, "rb"), purpose="assistants")
                file_ids.append(uploaded.id)

            controller_prompt = (
                "You are the ControllerAgent of a digital twin dairy farm.\n"
                "You receive CSV files related to:\n"
                "- milk yield\n"
                "- treatment\n"
                "- cow info or animal status\n"
                "Your job:\n"
                "- Identify what data is relevant to FarmAgent (aggregates, costs)\n"
                "- Identify what data is per-animal (CowAgent)\n"
                "- Forward relevant information accordingly\n"
                "Finally, summarize your actions in the reply."
            )

            openai.beta.threads.messages.create(
                thread_id=thread.id,
                role="user",
                content=controller_prompt,
                attachments=[
                    {
                        "file_id": fid,
                        "tools": [{"type": "code_interpreter"}]
                    } for fid in file_ids
                ]
            )

            run = openai.beta.threads.runs.create(
                thread_id=thread.id,
                assistant_id=st.session_state.controller_id
            )

            with st.spinner("🧠 Controller is analyzing..."):
                while run.status not in ["completed", "failed"]:
                    time.sleep(1)
                    run = openai.beta.threads.runs.retrieve(run.id, thread_id=thread.id)

            messages = openai.beta.threads.messages.list(thread_id=thread.id)
            for msg in messages.data[::-1]:
                if msg.role == "assistant":
                    st.markdown("### 🤖 Controller Response:")
                    st.markdown(msg.content[0].text.value)
                    break

        # === Spusť FarmAgent ===
        if st.button("📊 Analyze with FarmAgent"):
            run_farm = openai.beta.threads.runs.create(
                thread_id=thread.id,
                assistant_id=st.session_state.farm_id
            )

            with st.spinner("FarmAgent is analyzing..."):
                while run_farm.status not in ["completed", "failed"]:
                    time.sleep(1)
                    run_farm = openai.beta.threads.runs.retrieve(run_farm.id, thread_id=thread.id)

            messages_farm = openai.beta.threads.messages.list(thread_id=thread.id)
            for m in messages_farm.data[::-1]:
                if m.role == "assistant":
                    st.markdown("### 🐄 FarmAgent Summary:")
                    st.markdown(m.content[0].text.value)
                    break

        # === Spusť CowAgent ===
        if st.button("🐮 Analyze with CowAgent"):
            run_cow = openai.beta.threads.runs.create(
                thread_id=thread.id,
                assistant_id=st.session_state.cow_id
            )

            with st.spinner("CowAgent is analyzing..."):
                while run_cow.status not in ["completed", "failed"]:
                    time.sleep(1)
                    run_cow = openai.beta.threads.runs.retrieve(run_cow.id, thread_id=thread.id)

            messages_cow = openai.beta.threads.messages.list(thread_id=thread.id)
            for m in messages_cow.data[::-1]:
                if m.role == "assistant":
                    st.markdown("### 🐮 CowAgent Summary:")
                    st.markdown(m.content[0].text.value)
                    break

elif section == "RAG to Agents":
    st.title("📚 RAG: Analyze CSV and Route to Agents")

    import re  # pro bezpečné zpracování řádků

    folder_path = "farm_data"
    if not os.path.exists(folder_path) or not os.listdir(folder_path):
        st.warning("⚠️ No CSV files found in farm_data/")
    else:
        files = [f for f in os.listdir(folder_path) if f.endswith(".csv")]
        st.markdown("### 📂 Files found:")
        st.write(files)

        if st.button("📥 Analyze and Route"):
            thread = openai.beta.threads.create()
            file_id_map = {}

            for f_name in files:
                path = os.path.join(folder_path, f_name)
                uploaded = openai.files.create(file=open(path, "rb"), purpose="assistants")
                file_id_map[uploaded.id] = f_name  # ukládáme file_id → původní název

            # prompt pro controller
            controller_prompt = (
                "You are the ControllerAgent in a digital twin dairy farm system.\n"
                "Each uploaded file has a technical name like 'file-XYZ.csv'.\n"
                "For each file, respond with this format:\n"
                "file-XYZ.csv → CowAgent: short summary\n"
                "file-ABC.csv → FarmAgent: short summary\n"
                "Do NOT generate JSON. Do NOT process data. Only classify and describe."
            )

            openai.beta.threads.messages.create(
                thread_id=thread.id,
                role="user",
                content=controller_prompt,
                attachments=[
                    {"file_id": file_id, "tools": [{"type": "code_interpreter"}]}
                    for file_id in file_id_map.keys()
                ]
            )

            run = openai.beta.threads.runs.create(
                thread_id=thread.id,
                assistant_id=st.session_state.controller_id
            )

            with st.spinner("🧠 ControllerAgent is analyzing..."):
                while run.status not in ["completed", "failed"]:
                    time.sleep(1)
                    run = openai.beta.threads.runs.retrieve(run.id, thread_id=thread.id)

            messages = openai.beta.threads.messages.list(thread_id=thread.id)
            response_text = ""
            for msg in messages.data[::-1]:
                if msg.role == "assistant":
                    response_text = msg.content[0].text.value
                    st.markdown("### 🤖 Controller Response:")
                    st.markdown(response_text)
                    break

            # extrakce podle vzoru: file-XYZ.csv → Agent: summary
            for line in response_text.strip().splitlines():
                match = re.match(r"(file-[a-zA-Z0-9]+\.csv)\s*→\s*(CowAgent|FarmAgent):\s*(.+)", line)
                if match:
                    file_id_label, agent, summary = match.groups()
                    file_id = file_id_label.replace(".csv", "")

                    # vytvoř zprávu pro agenta
                    content = f"""
You are receiving file `{file_id_label}`
Summary: {summary}

Please store the file, confirm understanding, and prepare for future analysis.
"""

                    target_id = st.session_state.farm_id if agent.lower() == "farmagent" else st.session_state.cow_id

                    openai.beta.threads.messages.create(
                        thread_id=thread.id,
                        role="user",
                        content=content,
                        attachments=[{"file_id": file_id, "tools": [{"type": "code_interpreter"}]}]
                    )

                    run2 = openai.beta.threads.runs.create(
                        thread_id=thread.id,
                        assistant_id=target_id
                    )

                    with st.spinner(f"📤 Sending `{file_id_label}` to {agent}..."):
                        while run2.status not in ["completed", "failed"]:
                            time.sleep(1)
                            run2 = openai.beta.threads.runs.retrieve(run2.id, thread_id=thread.id)

                    messages2 = openai.beta.threads.messages.list(thread_id=thread.id)
                    for m in messages2.data[::-1]:
                        if m.role == "assistant":
                            st.markdown(f"### ✅ {agent} Response for `{file_id_label}`:")
                            st.markdown(m.content[0].text.value)
                            break

# === SEKCE: Run Digital Twin Analysis ===
elif section == "Run Digital Twin Analysis":
    st.title("🚀 Run Digital Twin Final Analysis")

    thread = openai.beta.threads.create()
    file_ids = []
    folder_path = "farm_data"

    if os.path.exists(folder_path):
        for fname in os.listdir(folder_path):
            if fname.endswith(".csv"):
                path = os.path.join(folder_path, fname)
                uploaded = openai.files.create(file=open(path, "rb"), purpose="assistants")
                file_ids.append(uploaded.id)

    # === zpráva pro FarmAgent ===
    openai.beta.threads.messages.create(
        thread_id=thread.id,
        role="user",
        content="""
You are FarmAgent of a digital twin dairy farm.

Your tasks:
1. Use the code interpreter to read the attached CSV files.
2. Identify farm-level data: milk production, cost data, farm summaries.
3. Analyze:
   - Monthly milk production totals
   - Farm-level cost analysis
   - Profit/loss and economic trends
4. Store and understand the data.
5. Return summary of insights.
""",
        attachments=[{"file_id": fid, "tools": [{"type": "code_interpreter"}]} for fid in file_ids]
    )

    # === zpráva pro CowAgent ===
    openai.beta.threads.messages.create(
        thread_id=thread.id,
        role="user",
        content="""
You are CowAgent of a digital twin dairy farm.

Your tasks:
1. Use the code interpreter to read the attached CSV files.
2. Identify cow-level data: treatments, milk yield per cow, health status.
3. Analyze:
   - Average and deviation of milk yield per cow
   - Identify sick, underperforming, or high-risk cows
4. Store and understand the data.
5. Return a summary with insights.
""",
        attachments=[{"file_id": fid, "tools": [{"type": "code_interpreter"}]} for fid in file_ids]
    )

    # === spusť analýzu pro oba agenty ===
    for agent_id, label in [
        (st.session_state.farm_id, "FarmAgent"),
        (st.session_state.cow_id, "CowAgent")
    ]:
        run = openai.beta.threads.runs.create(
            thread_id=thread.id,
            assistant_id=agent_id
        )

        with st.spinner(f"🔍 {label} is analyzing data..."):
            while run.status not in ["completed", "failed"]:
                time.sleep(1)
                run = openai.beta.threads.runs.retrieve(run.id, thread_id=thread.id)

        messages = openai.beta.threads.messages.list(thread_id=thread.id)
        for m in messages.data[::-1]:
            if m.role == "assistant":
                st.markdown(f"### 📊 {label} Final Report:")
                st.markdown(m.content[0].text.value)
                break

elif section == "📤 Export Insights (JSON)":
    st.title("📤 Export Final Insights from Agents")

    thread = openai.beta.threads.create()
    folder_path = "farm_data"
    file_ids = []

    if os.path.exists(folder_path):
        for fname in os.listdir(folder_path):
            if fname.endswith(".csv"):
                path = os.path.join(folder_path, fname)
                uploaded = openai.files.create(file=open(path, "rb"), purpose="assistants")
                file_ids.append(uploaded.id)

    for agent_id, label in [
        (st.session_state.farm_id, "FarmAgent"),
        (st.session_state.cow_id, "CowAgent")
    ]:
        openai.beta.threads.messages.create(
            thread_id=thread.id,
            role="user",
            content=f"""
You are the {label} of a digital twin dairy farm.

Return ONLY valid JSON, nothing else. Format:
{{
  "summary": "...",
  "metrics": {{
    "total_milk": 0,
    "avg_milk_per_cow": 0,
    "high_risk_animals": [],
    "monthly_costs": []
  }},
  "conclusion": "..."
}}
""",
            attachments=[{"file_id": fid, "tools": [{"type": "code_interpreter"}]} for fid in file_ids]
        )

        run = openai.beta.threads.runs.create(
            thread_id=thread.id,
            assistant_id=agent_id
        )

        with st.spinner(f"🧠 {label} is compiling final JSON report..."):
            while run.status not in ["completed", "failed"]:
                time.sleep(1)
                run = openai.beta.threads.runs.retrieve(run.id, thread_id=thread.id)

        messages = openai.beta.threads.messages.list(thread_id=thread.id)
        for msg in messages.data[::-1]:
            if msg.role == "assistant":
                st.markdown(f"### 📦 JSON Output from {label}:")
                import re
                raw = msg.content[0].text.value
                match = re.search(r"\{[\s\S]*\}", raw)
                if match:
                    try:
                        st.json(json.loads(match.group(0)))
                    except Exception as e:
                        st.error(f"❌ JSON parsing error: {e}")
                        st.code(match.group(0))
                else:
                    st.error("❌ No JSON found in response.")
                    st.markdown(raw)
                break
