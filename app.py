import streamlit as st
from langchain_core.messages import HumanMessage, AIMessage
from agent import agent_executor

st.set_page_config(page_title="Flight Search Agent")
st.title("✈ Flight Search Agent")
st.caption("To make bookings easier! · Powered by LangChain · Groq (LLaMA 3.3)")

with st.expander("How to use"):
    st.markdown("""
            **Use IATA airport codes**, not city names. For example,`BOS` instead of Boston.
            You can also ask it follow-up questions in the same session.
            You can search flights based on type of trip (e.g. one-way, round), cheapest days or compare two routes.
            Chat history will be cleared out every session.
                """)

## Session state
if "messages" not in st.session_state:
    st.session_state.messages = []
if "flight_cache" not in st.session_state:
    st.session_state.flight_cache = {}

## Display existing chat messages
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

## Chat input
if prompt := st.chat_input("Hello! How can I help you today?"):

    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    ## Only keep last 6 messages (3 turns) for context - for optimising time 
    recent = st.session_state.messages[-6:]
    chat_history = []
    for msg in recent[:-1]:
        if msg["role"] == "user":
            chat_history.append(HumanMessage(content=msg["content"]))
        elif msg["role"] == "assistant":
            chat_history.append(AIMessage(content=msg["content"]))

    ## Get agent response
    with st.chat_message("assistant"):
        with st.spinner("Searching flights..."):
            try:
                response = agent_executor.invoke({
                    "messages": chat_history + [HumanMessage(content=prompt)]
                })
                output = next(
                    (m.content for m in reversed(response["messages"]) if isinstance(m, AIMessage)),
                    "Sorry, I couldn't generate a response."
                )
            except Exception as e:
                output = f"Something went wrong: {str(e)}"

        st.markdown(output)

    st.session_state.messages.append({"role": "assistant", "content": output})