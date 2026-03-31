"""
app.py — Streamlit entry point for "Your AI Expert"

Users can choose an AI expert and a language, then chat with streaming responses.
"""

import logging
import os

import google.generativeai as genai
import streamlit as st
from dotenv import load_dotenv
from google.api_core.exceptions import GoogleAPIError, PermissionDenied, ResourceExhausted

from experts import EXPERTS
from languages import LANGUAGES

logger = logging.getLogger(__name__)

# Load API key from .env file if present
load_dotenv()

GEMINI_MODEL = "gemini-2.0-flash"


# ── Page config ──────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="Your AI Expert",
    page_icon="🤖",
    layout="centered",
)


# ── Gemini client ─────────────────────────────────────────────────────────────

api_key = os.getenv("GOOGLE_API_KEY")
if api_key:
    genai.configure(api_key=api_key)


# ── Helper: build the system prompt ──────────────────────────────────────────

def build_system_prompt(expert_name: str, language: str) -> str:
    """Combine the expert's base prompt with the language instruction."""
    base = EXPERTS[expert_name]["system_prompt"]
    lang_instruction = LANGUAGES[language]
    return f"{base}\n\n{lang_instruction}"


def _to_gemini_history(messages: list) -> list:
    """Convert OpenAI-style message list to Gemini chat history format.

    System messages are skipped because the system prompt is passed via
    ``system_instruction`` when constructing the GenerativeModel.
    """
    history = []
    for msg in messages:
        if msg["role"] == "system":
            continue
        role = "model" if msg["role"] == "assistant" else "user"
        history.append({"role": role, "parts": [msg["content"]]})
    return history


# ── Helper: generate a welcome message via API ────────────────────────────────

def generate_welcome_message(expert_name: str, language: str) -> str:
    """Ask the expert to introduce themselves with a short welcome message."""
    system_prompt = build_system_prompt(expert_name, language)
    try:
        model = genai.GenerativeModel(GEMINI_MODEL, system_instruction=system_prompt)
        response = model.generate_content(
            "Presentati brevemente e di' come puoi aiutarmi.",
            generation_config=genai.GenerationConfig(max_output_tokens=200),
        )
        return response.text
    except ResourceExhausted:
        return (
            f"👋 Ciao! Sono {expert_name}.\n\n"
            "⚠️ **Quota API esaurita.** Il limite di utilizzo dell'API Google Gemini è stato raggiunto. "
            "Verifica il tuo piano su [aistudio.google.com](https://aistudio.google.com)."
        )
    except PermissionDenied:
        return (
            f"👋 Ciao! Sono {expert_name}.\n\n"
            "⚠️ **Chiave API non valida.** Controlla il valore di `GOOGLE_API_KEY` nel file `.env`."
        )
    except GoogleAPIError:
        return (
            f"👋 Ciao! Sono {expert_name}.\n\n"
            "⚠️ **Impossibile connettersi all'API Google Gemini.** Controlla la tua connessione internet."
        )
    except Exception:
        logger.exception("Unexpected error generating welcome message for %s", expert_name)
        return (
            f"👋 Ciao! Sono {expert_name}.\n\n"
            "⚠️ Si è verificato un errore imprevisto. Riprova più tardi."
        )


# ── Helper: stream a chat response ───────────────────────────────────────────

def stream_response(messages: list, expert_name: str, language: str):
    """Yield text chunks from the streaming Gemini response."""
    system_prompt = build_system_prompt(expert_name, language)
    # Split history (all but the last user message) from the current prompt
    history = _to_gemini_history(messages[:-1])
    current_prompt = messages[-1]["content"]

    try:
        model = genai.GenerativeModel(GEMINI_MODEL, system_instruction=system_prompt)
        chat = model.start_chat(history=history)
        stream = chat.send_message(current_prompt, stream=True)
        for chunk in stream:
            if chunk.text:
                yield chunk.text
    except ResourceExhausted:
        yield (
            "\n\n⚠️ **Quota API esaurita.** Il limite di utilizzo dell'API Google Gemini è stato raggiunto. "
            "Verifica il tuo piano su [aistudio.google.com](https://aistudio.google.com)."
        )
    except PermissionDenied:
        yield "\n\n⚠️ **Chiave API non valida.** Controlla il valore di `GOOGLE_API_KEY` nel file `.env`."
    except GoogleAPIError:
        yield "\n\n⚠️ **Impossibile connettersi all'API Google Gemini.** Controlla la tua connessione internet."
    except Exception:
        logger.exception("Unexpected error streaming response for %s", expert_name)
        yield "\n\n⚠️ Si è verificato un errore imprevisto. Riprova più tardi."


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
        "⚠️ **API key non configurata.** Crea un file `.env` con `GOOGLE_API_KEY=la-tua-chiave` e riavvia l'app.",
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
