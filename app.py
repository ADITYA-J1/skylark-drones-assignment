"""
Drone Operations Coordinator — Streamlit conversational UI.
Run: streamlit run app.py
"""
import streamlit as st

from src.agent import run_agent


def _rerun():
    try:
        st.rerun()
    except AttributeError:
        st.experimental_rerun()


st.set_page_config(page_title="Drone Operations Coordinator", page_icon="🚁", layout="centered")
st.title("🚁 Drone Operations Coordinator")
st.caption("Skylark Drones — Roster, assignments, fleet, and conflict detection")

# Session state for chat history
if "messages" not in st.session_state:
    st.session_state.messages = []

# Show chat history
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# Input
if prompt := st.chat_input("Ask about pilots, drones, assignments, conflicts, or status updates..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        try:
            reply, _ = run_agent(prompt)
            st.markdown(reply)
        except Exception as e:
            st.error(f"Error: {e}")
            reply = str(e)
    st.session_state.messages.append({"role": "assistant", "content": reply})

# Sidebar
with st.sidebar:
    st.header("Quick actions")
    if st.button("Check conflicts"):
        st.session_state.messages.append({"role": "user", "content": "Check conflicts"})
        try:
            reply, _ = run_agent("Check conflicts")
        except Exception as e:
            reply = str(e)
        st.session_state.messages.append({"role": "assistant", "content": reply})
        _rerun()
    if st.button("List missions"):
        st.session_state.messages.append({"role": "user", "content": "List all projects"})
        try:
            reply, _ = run_agent("List all projects")
        except Exception as e:
            reply = str(e)
        st.session_state.messages.append({"role": "assistant", "content": reply})
        _rerun()
    if st.button("Clear chat"):
        st.session_state.messages = []
        _rerun()
    st.divider()
    with st.expander("What can I ask?"):
        st.markdown("- *Who is available in Bangalore?*")
        st.markdown("- *Pilots with DGCA certification*")
        st.markdown("- *Drones in Mumbai*")
        st.markdown("- *Suggest assignment for PRJ001*")
        st.markdown("- *Urgent reassignment for PRJ002*")
        st.markdown("- *Check conflicts*")
        st.markdown("- *Set pilot P004 status to On Leave*")
        st.markdown("- *Confirm reassignment PRJ002 to P002 and D003*")
