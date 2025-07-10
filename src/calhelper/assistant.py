from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables import RunnableLambda
from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain.memory import ConversationBufferMemory
import os

from calhelper.api import CalAPI


class CalHelper:

    def __init__(self):
        self.cal_api = CalAPI()
        self.client = ChatOpenAI(model="gpt-4o", temperature=0.0)
        self.tools = self._initialize_tools()

    def _initialize_tools(self):
        @tool
        def get_my_profile() -> dict:
            """Fetch the profile of the authenticated user from the calendar API."""
            return self.cal_api.get_my_profile()

        @tool
        def get_event_types() -> list[dict]:
            """
            Fetch event types supported by the user's calendar profile.
            """
            return self.cal_api.get_event_types(user=self.cal_api.profile)

        @tool
        def get_bookings(start_date: str | None = None, end_date: str | None = None) -> list[dict]:
            """
            Fetch bookings from the calendar between start_date and end_date.
            """
            return self.cal_api.get_bookings(start_date=start_date, end_date=end_date)

        return [
            get_my_profile,
            get_event_types,
            get_bookings,
        ]

    def get_agent_executor(self):
        prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    "You are a helpful assistant that can interact with a calendar API.",
                ),
                MessagesPlaceholder(variable_name="chat_history"),
                ("user", "{prompt}"),
                MessagesPlaceholder(variable_name="agent_scratchpad"),
            ]
        )

        memory = ConversationBufferMemory(memory_key="chat_history", return_messages=True)

        agent = create_tool_calling_agent(
            llm=self.client, tools=self.tools, prompt=prompt
        )
        return AgentExecutor(agent=agent, tools=self.tools, memory=memory, verbose=True)

    def run(self):
        agent_executor = self.get_agent_executor()

        while True:
            user_input = input("You: ")
            if user_input.lower() in ["exit", "quit"]:
                print("Exiting CalHelper.")
                break

            response = agent_executor.invoke({"prompt": user_input})
            print(f"Assistant: {response}")
