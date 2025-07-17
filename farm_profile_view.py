import streamlit as st
import json
import os
import openai

# Zjisti aktivní farmu z hlavní aplikace
farm_name = st.session_state.get("farm_name")
FOLDER_BASE = "streamlet/farm_data"

if not farm_name:
    st.warning("No farm selected. Please select a farm from the main menu.")
    st.stop()

FOLDER = os.path.join(FOLDER_BASE, farm_name.replace(" ", "_"))
profile_path = os.path.join(FOLDER, "profile.json")
weather_path = os.path.join(FOLDER, "weather_summary.txt")

st.title("🌍 Farm Profile & Weather Info")

# === Vytvoř profil přes agenta, pokud chybí ===
if not os.path.exists(profile_path):
    st.info("No profile.json found. Generating profile from agent...")
    thread = openai.beta.threads.create()

    # pošli dotaz, ať agent vytvoří profil z farmářských dat
    openai.beta.threads.messages.create(
        thread_id=thread.id,
        role="user",
        content=f"""
You are a dairy farm assistant. Generate a JSON farm profile with the following structure based on available CSV files in the folder:

{{
  "location": "...",
  "farm_size_ha": float,
  "num_animals": int,
  "owner": "..."
}}
Return valid JSON only.
""",
        attachments=[{
            "file_id": openai.files.create(
                file=open(os.path.join(FOLDER, f), "rb"), purpose="assistants"
            ).id,
            "tools": [{"type": "code_interpreter"}]
        } for f in os.listdir(FOLDER) if f.endswith(".csv")]
    )

    run = openai.beta.threads.runs.create(
        thread_id=thread.id,
        assistant_id=st.secrets["dairy_sustainability_agent"]["id"]
    )

    with st.spinner("📄 Creating profile.json from uploaded farm data via agent..."):
        import time
        while run.status not in ["completed", "failed"]:
            time.sleep(1)
            run = openai.beta.threads.runs.retrieve(run.id, thread_id=thread.id)

    messages = openai.beta.threads.messages.list(thread_id=thread.id)
    for msg in messages.data[::-1]:
        if msg.role == "assistant":
            import re, json
            match = re.search(r"\{[\s\S]*\}", msg.content[0].text.value)
            if match:
                try:
                    profile = json.loads(match.group(0))
                    with open(profile_path, "w") as f:
                        json.dump(profile, f, indent=2)
                    st.success("✅ Farm profile created successfully.")
                except Exception as e:
                    st.error(f"❌ Failed to parse profile JSON: {e}")
            break

# === Načti a zobraz profil ===
if not os.path.exists(profile_path):
    st.warning("No `profile.json` found for this farm.")
else:
    with open(profile_path) as f:
        profile = json.load(f)

    st.markdown(f"📍 **Location**: {profile.get('location', 'N/A')}")
    st.markdown(f"🐄 **Number of animals**: {profile.get('num_animals', 'N/A')}")
    st.markdown(f"🌾 **Farm size (ha)**: {profile.get('farm_size_ha', 'N/A')}")
    st.markdown(f"👨‍🌾 **Owner**: {profile.get('owner', 'N/A')}")

    # === Získání počasí od agenta ===
    if profile.get("location"):
        st.divider()
        st.subheader("☁️ Weather Summary from Agent")

        if os.path.exists(weather_path):
            with open(weather_path) as f:
                summary = f.read()
            st.success(summary)
        else:
            thread = openai.beta.threads.create()

            # přilož JSON jako vstup
            openai.beta.threads.messages.create(
                thread_id=thread.id,
                role="user",
                content="""
You are a dairy sustainability assistant.
You are given a JSON description of a farm. Based on that, generate a short weather and climate summary for the farm region.
Return only a short paragraph that would be helpful for a dairy farmer.
""",
                attachments=[{
                    "file_id": openai.files.create(
                        file=open(profile_path, "rb"), purpose="assistants"
                    ).id,
                    "tools": [{"type": "code_interpreter"}]
                }]
            )

            run = openai.beta.threads.runs.create(
                thread_id=thread.id,
                assistant_id=st.secrets["dairy_sustainability_agent"]["id"]
            )

            with st.spinner("🔍 Getting weather summary from agent..."):
                import time
                while run.status not in ["completed", "failed"]:
                    time.sleep(1)
                    run = openai.beta.threads.runs.retrieve(run.id, thread_id=thread.id)

            messages = openai.beta.threads.messages.list(thread_id=thread.id)
            for msg in messages.data[::-1]:
                if msg.role == "assistant":
                    summary = msg.content[0].text.value.strip()
                    st.success(summary)
                    with open(weather_path, "w") as f:
                        f.write(summary)
                    break
