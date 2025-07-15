import streamlit as st
import openai
import pandas as pd
import time
import os

openai.api_key = os.getenv("OPENAI_API_KEY")

CONTROLLER_AGENT_ID = "asst_your_controller_id_here"

st.title("🐄 Digital Twin Dairy Farm")

uploaded_files = st.file_uploader("Upload CSV files", accept_multiple_files=True)

dataframes = {}
if uploaded_files:
    for f in uploaded_files:
        df = pd.read_csv(f)
        dataframes[f.name] = df
        st.write(f"✅ {f.name}")
        st.dataframe(df.head())

query = st.text_input("Ask something:")

if st.button("Ask") and query and dataframes:
    thread = openai.beta.threads.create()
    openai.beta.threads.messages.create(
        thread_id=thread.id,
        role="user",
        content=query
    )

    run = openai.beta.threads.runs.create(
        thread_id=thread.id,
        assistant_id=CONTROLLER_AGENT_ID,
        tool_choice="auto"
    )

    with st.spinner("Thinking..."):
        while run.status not in ["completed", "failed"]:
            run = openai.beta.threads.runs.retrieve(run.id, thread_id=thread.id)
            time.sleep(1)

        messages = openai.beta.threads.messages.list(thread_id=thread.id)
        for msg in messages.data[::-1]:
            if msg.role == "assistant":
                st.markdown("### 🤖 Response:")
                st.markdown(msg.content[0].text.value)
