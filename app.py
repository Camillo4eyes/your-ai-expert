"""
app.py — Streamlit entry point for "Your AI Expert"

Users can choose an AI expert and a language, then chat with streaming responses.
"""

import os

import streamlit as st
from dotenv import load_dotenv
from openai import OpenAI

from experts import EXPERTS
from languages import LANGUAGES

# Load API key from .env file if present
load_dotenv()


# ── Page config ──────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="Your AI Expert",
    page_icon="🤖",
    layout="centered",
)


# ── OpenAI client ─────────────────────────────────────────────────────────────

api_key = os.getenv("OPENAI_API_KEY")
client = OpenAI(api_key=api_key) if api_key else None


# ── Helper: build the system prompt ──────────────────────────────────────────

def build_system_prompt(expert_name: str, language: str) -> str:
    """Combine the expert's base prompt with the language instruction."""
    base = EXPERTS[expert_name]["system_prompt"]
    lang_instruction = LANGUAGES[language]
    return f"{base}\n\n{lang_instruction}"


# ── Helper: generate a welcome message via API ────────────────────────────────

def generate_welcome_message(expert_name: str, language: str) -> str:
    """Ask the expert to introduce themselves with a short welcome message."""
    system_prompt = build_system_prompt(expert_name, language)
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {
                    "role": "user",
                    "content": "Presentati brevemente e di' come puoi aiutarmi.",
                },
            ],
            max_tokens=200,
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"Ciao! Sono {expert_name}. (Errore durante la presentazione: {e})"


# ── Helper: stream a chat response ───────────────────────────────────────────

def stream_response(messages: list, expert_name: str, language: str):
    """Yield text chunks from the streaming OpenAI response."""
    system_prompt = build_system_prompt(expert_name, language)
    full_messages = [{"role": "system", "content": system_prompt}] + messages

    try:
        stream = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=full_messages,
            stream=True,
        )
        for chunk in stream:
            if chunk.choices and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content
    except Exception as e:
        yield f"\n\n⚠️ Errore durante la risposta: {e}"


# ── Session state initialisation ─────────────────────────────────────────────

def reset_conversation():
    """Clear the chat history and welcome message."""
    st.session_state.messages = []
    st.session_state.welcome_shown = False


if "selected_expert" not in st.session_state:
    st.session_state.selected_expert = list(EXPERTS.keys())[0]

if "selected_language" not in st.session_state:
    st.session_state.selected_language = "Italiano"

if "messages" not in st.session_state:
    st.session_state.messages = []

if "welcome_shown" not in st.session_state:
    st.session_state.welcome_shown = False


# ── Sidebar ───────────────────────────────────────────────────────────────────

with st.sidebar:
    st.title("🤖 Your AI Expert")
    st.markdown("---")

    # Language selector
    st.subheader("🌍 Lingua / Language")
    selected_language = st.selectbox(
        label="Scegli la lingua",
        options=list(LANGUAGES.keys()),
        index=list(LANGUAGES.keys()).index(st.session_state.selected_language),
        label_visibility="collapsed",
    )

    st.markdown("---")

    # Expert selector
    st.subheader("🧠 Scegli il tuo esperto")
    expert_options = [
        f"{info['emoji']} {name}" for name, info in EXPERTS.items()
    ]
    expert_names = list(EXPERTS.keys())

    current_index = expert_names.index(st.session_state.selected_expert)
    selected_label = st.radio(
        label="Esperto",
        options=expert_options,
        index=current_index,
        label_visibility="collapsed",
    )
    selected_expert = expert_names[expert_options.index(selected_label)]

    # Show the expert description
    st.caption(EXPERTS[selected_expert]["description"])

    st.markdown("---")

    # Reset button
    if st.button("🔄 Nuova conversazione", use_container_width=True):
        reset_conversation()
        st.session_state.selected_expert = selected_expert
        st.session_state.selected_language = selected_language
        st.rerun()

# Detect expert or language change and reset automatically
if (
    selected_expert != st.session_state.selected_expert
    or selected_language != st.session_state.selected_language
):
    st.session_state.selected_expert = selected_expert
    st.session_state.selected_language = selected_language
    reset_conversation()
    st.rerun()


# ── Main area ─────────────────────────────────────────────────────────────────

expert_info = EXPERTS[selected_expert]
st.title(f"{expert_info['emoji']} {selected_expert}")

# Warn if no API key is configured
if not api_key:
    st.warning(
        "⚠️ **API key non configurata.** Crea un file `.env` con `OPENAI_API_KEY=la-tua-chiave` e riavvia l'app.",
        icon="🔑",
    )
    st.stop()

# Generate and display welcome message on first load
if not st.session_state.welcome_shown:
    with st.spinner(f"{expert_info['emoji']} {selected_expert} si sta presentando…"):
        welcome = generate_welcome_message(selected_expert, selected_language)
    st.session_state.messages.append({"role": "assistant", "content": welcome})
    st.session_state.welcome_shown = True

# Display chat history
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# Chat input
user_input = st.chat_input("Scrivi un messaggio…")

if user_input:
    # Show and store user message
    with st.chat_message("user"):
        st.markdown(user_input)
    st.session_state.messages.append({"role": "user", "content": user_input})

    # Stream assistant response
    with st.chat_message("assistant"):
        response_text = st.write_stream(
            stream_response(
                st.session_state.messages,
                selected_expert,
                selected_language,
            )
        )

    st.session_state.messages.append(
        {"role": "assistant", "content": response_text}
    )
