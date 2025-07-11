import time

import streamlit as st
from calhelper.assistant import CalHelper
from langchain_core.messages import HumanMessage, AIMessage

st.set_page_config(page_title="CalHelper Assistant", page_icon="🗓️")
st.title("🗓️ CalHelper Assistant")


def main():
    # Initialize CalHelper in session state
    if "cal_helper" not in st.session_state:
        st.session_state.cal_helper = CalHelper()
        st.session_state.messages = []

    # Display chat messages from history on app rerun
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    # React to user input
    if prompt := st.chat_input("What do you need help with?"):
        # Display user message in chat message container
        st.chat_message("user").markdown(prompt)
        # Add user message to chat history
        st.session_state.messages.append({"role": "user", "content": prompt})

        # Prepare initial state for the graph
        initial_state = {
            "messages": [
                (
                    "system",
                    (
                        "You are a helpful calendar assistant."
                        f"Current local timezone is {time.tzname[time.localtime().tm_isdst]}"
                        "All time string format is ISO-8601, example: 2025-07-10T09:00:00-0700."
                        "Respond everything in the current timezone."
                        "Before creating, cancelling, or rescheduling an event, prompt the user for confirmation with tool call arguments."
                    ),
                ),
                ("user", f"{time.strftime('%Y-%m-%d %H:%M:%S')}: {prompt}"),
            ]
        }

        # Invoke the graph and stream responses
        with st.chat_message("assistant"):
            message_placeholder = st.empty()
            full_response = ""
            for s in st.session_state.cal_helper.graph.stream(
                initial_state,
                config={"configurable": {"thread_id": "streamlit_user"}}, # Using a fixed thread_id for Streamlit
            ):
                if "llm_call" in s:
                    ai_message = s["llm_call"]["messages"][-1]
                    if isinstance(ai_message, AIMessage):
                        full_response += ai_message.content
                        message_placeholder.markdown(full_response + "▌")
            message_placeholder.markdown(full_response)

        # Add assistant response to chat history
        st.session_state.messages.append({"role": "assistant", "content": full_response})

    # Clear chat history button
    if st.button("Clear Chat"):
        st.session_state.messages = []
        st.session_state.cal_helper = CalHelper() # Re-initialize CalHelper to clear its internal state
        st.experimental_rerun()


if __name__ == "__main__":
    main()