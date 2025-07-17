import streamlit as st
import json
import os
import openai
import time
import re

# === Load current farm context ===
farm_name = st.session_state.get("farm_name")
FOLDER_BASE = "streamlet/farm_data"

if not farm_name:
    st.warning("No farm selected. Please choose a farm from the main menu.")
    st.stop()

FOLDER = os.path.join(FOLDER_BASE, farm_name.replace(" ", "_"))
profile_path = os.path.join(FOLDER, "profile.json")
weather_path = os.path.join(FOLDER, "weather_summary.txt")

st.title("🌍 Farm Profile & Weather Info")

# === Create profile.json if missing ===
if not os.path.exists(profile_path):
    st.info("🧠 Generating farm profile using uploaded CSV files...")
    
    csv_files = [f for f in os.listdir(FOLDER) if f.endswith(".csv")]
    if not csv_files:
        st.warning("No CSV files found in the farm folder.")
        st.stop()

    # Upload all CSVs as attachments
    attachments = []
    for f in csv_files:
        file_path = os.path.join(FOLDER, f)
        file = openai.files.create(file=open(file_path, "rb"), purpose="assistants")
        attachments.append({
            "file_id": file.id,
            "tools": [{"type": "code_interpreter"}]
        })

    thread = openai.beta.threads.create()

    openai.beta.threads.messages.create(
        thread_id=thread.id,
        role="user",
        content="""
You are a dairy farm assistant. Based on the uploaded farm CSVs, generate a farm profile with the following JSON structure:

{
  "location": "...",
  "farm_size_ha": float,
  "num_animals": int,
  "owner": "..."
}

Respond ONLY with valid JSON. Do not include any explanation, text, or markdown.
""",
        attachments=attachments
    )

    run = openai.beta.threads.runs.create(
        thread_id=thread.id,
        assistant_id=st.secrets["dairy_sustainability_agent"]["id"]
    )

    with st.spinner("🤖 Processing files and creating profile..."):
        while run.status not in ["completed", "failed"]:
            time.sleep(1)
            run = openai.beta.threads.runs.retrieve(run.id, thread_id=thread.id)

    messages = openai.beta.threads.messages.list(thread_id=thread.id)
    for msg in messages.data[::-1]:
        if msg.role == "assistant":
            match = re.search(r"\{[\s\S]*?\}", msg.content[0].text.value)
            if match:
                try:
                    profile = json.loads(match.group(0))
                    with open(profile_path, "w") as f:
                        json.dump(profile, f, indent=2)
                    st.success("✅ Farm profile generated successfully.")
                except Exception as e:
                    st.error(f"Failed to parse JSON from assistant: {e}")
            break

# === Display profile ===
if not os.path.exists(profile_path):
    st.warning("Farm profile could not be generated.")
    st.stop()

with open(profile_path) as f:
    profile = json.load(f)

st.markdown(f"📍 **Location**: {profile.get('location', 'N/A')}")
st.markdown(f"🐄 **Number of animals**: {profile.get('num_animals', 'N/A')}")
st.markdown(f"🌾 **Farm size (ha)**: {profile.get('farm_size_ha', 'N/A')}")
st.markdown(f"👨‍🌾 **Owner**: {profile.get('owner', 'N/A')}")

# === Weather summary ===
if profile.get("location"):
    st.divider()
    st.subheader("☁️ Weather Summary")

    if os.path.exists(weather_path):
        with open(weather_path) as f:
            summary = f.read()
        st.success(summary)
    else:
        thread = openai.beta.threads.create()

        file_uploaded = openai.files.create(file=open(profile_path, "rb"), purpose="assistants")

        openai.beta.threads.messages.create(
            thread_id=thread.id,
            role="user",
            content="""
You are a sustainability assistant. Based on the uploaded JSON farm profile, generate a short weather and climate summary relevant for dairy farming.
Keep it in English and return only a short paragraph. No markdown.
""",
            attachments=[{
                "file_id": file_uploaded.id,
                "tools": [{"type": "code_interpreter"}]
            }]
        )

        run = openai.beta.threads.runs.create(
            thread_id=thread.id,
            assistant_id=st.secrets["dairy_sustainability_agent"]["id"]
        )

        with st.spinner("⛅ Generating weather report..."):
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
