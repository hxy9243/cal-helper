# CalHelper: An AI-Powered Calendar Assistant

CalHelper is an AI-powered calendar assistant toy app designed to streamline your scheduling and event management using the` Cal.com API.
It has a command-line interface (CLI) and a Streamlit web application for interacting with your Cal.com APIs.

## Features

*   **AI-Powered Interactions:** Leverage large language models (LLMs) to understand natural language requests for calendar management.
*   **Event Management:**
    *   Fetch your profile and available event types.
    *   Retrieve existing meeting bookings.
    *   Find available slots for specific event types.
    *   Create new bookings.
    *   Cancel existing bookings.
    *   Reschedule bookings.
*   **Flexible Interface:** Interact with the assistant via a command-line interface or a user-friendly Streamlit web application.
*   **Cal.com Integration:** Seamlessly connects with your Cal.com account to manage your calendar events.

## Installation

To set up CalHelper, follow these steps:

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/your-repo/calhelper.git # Replace with actual repo URL
    cd calhelper
    ```

2.  **Create a virtual environment (recommended):**
    ```bash
    python -m venv venv
    source venv/bin/activate # On Windows, use `venv\Scripts\activate`
    ```

3.  **Install dependencies:**
    ```bash
    pip install -e .
    ```
    This will install all necessary Python packages, including `langchain`, `openai`, `streamlit`, and `pydantic`.

## Configuration

CalHelper requires a `CAL_API_KEY` to interact with the Cal.com API.

1.  **Obtain your Cal.com API Key:**
    *   Log in to your Cal.com account.
    *   Navigate to your API Keys section (usually under Developer Settings or Integrations).
    *   Generate a new API key if you don't have one.

2.  **Create a `.env` file:**
    In the root directory of the `calhelper` project, create a file named `.env` and add your API key:
    ```
    OPENAI_API_KEY="sk-YOUR_OPENAI_KEY"
    CAL_API_KEY="YOUR_CAL_COM_API_KEY"
    ```
    Replace `"YOUR_CAL_COM_API_KEY"` with the actual API key you obtained from Cal.com.

## Usage

CalHelper can be used via its CLI or a Streamlit web application.

### Command-Line Interface (CLI)

You can interact with the CalHelper assistant directly from your terminal.

```bash
calhelper
```

Once started, you can type your calendar-related queries, e.g.:
*   "What are my upcoming meetings?"
*   "Schedule a 30-minute meeting with John Doe tomorrow at 10 AM about project status."
*   "Cancel my meeting with Jane Smith on Friday."

### Streamlit Web Application

To run the interactive web application:

```bash
streamlit run src/streamlit_app.py
```

This command will start the Streamlit server, and a new tab in your web browser will open, displaying the CalHelper chat interface. You can then type your requests into the chat window.

## Project Structure

*   `src/calhelper/api.py`: Contains the `CalAPI` class for interacting with the Cal.com API.
*   `src/calhelper/assistant.py`: Implements the AI assistant logic using LangChain and LangGraph, integrating the Cal.com API tools.
*   `src/calhelper/cli.py`: Defines the command-line interface for the assistant.
*   `src/streamlit_app.py`: Provides the Streamlit web application interface.
*   `pyproject.toml`: Project metadata and dependencies.
*   `.env`: Environment variables (e.g., `CAL_API_KEY`).
