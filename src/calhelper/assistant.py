from typing import List, Dict, Any, TypedDict, Annotated

import os
import time
import logging

from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables import RunnableLambda
from langchain_core.messages import BaseMessage, ToolMessage
from pydantic import BaseModel, Field

from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.checkpoint.memory import MemorySaver
from langchain_core.messages import HumanMessage, AIMessage, BaseMessage

from calhelper.api import CalAPI, Attendee, Location

# Setup logging to log file
log_file = "calhelper.log"
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(log_file),
    ]
)
logger = logging.getLogger(__name__)


class AgentState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]
    tool_outcome: Annotated[list[ToolMessage], add_messages]
    next_step: str


class CalHelper:

    def __init__(self):
        self.cal_api = CalAPI()
        self.llm = ChatOpenAI(model="gpt-4o", temperature=0.0)
        self.tools = self._initialize_tools()
        self.checkpointer = MemorySaver()
        self.graph = self._initialize_graph()

    def _initialize_tools(self):
        @tool
        def get_my_profile() -> dict:
            """Fetch the profile of the authenticated user from the calendar API."""
            return self.cal_api.get_my_profile()

        @tool
        def get_event_types() -> List[Dict]:
            """
            Fetch event types supported by the user's calendar profile.
            """
            return self.cal_api.get_event_types(user=self.cal_api.profile)

        @tool
        def get_bookings(
            start_date: str | None = None, end_date: str | None = None
        ) -> List[Dict]:
            """
            Fetch bookings from the calendar between start_date and end_date.
            """
            return self.cal_api.get_bookings(start_date=start_date, end_date=end_date)

        @tool
        def get_slots(
            event_type_id: str,
            start_date: str | None = None,
            end_date: str | None = None,
        ) -> List[Dict]:
            """
            Fetch available slots for a specific event type between start_date and end_date.
            """
            return self.cal_api.get_slots(
                event_type_id=event_type_id, start_date=start_date, end_date=end_date
            )

        class CreateBookingInput(BaseModel):
            event_type_id: int = Field(description="The ID of the event type to book.")
            start_time: str = Field(description="The start time of the booking in ISO-8601 format.")
            attendees: Attendee = Field(description="A Dictionary containing the attendee's details.")
            location: Location = Field(description="The location of the booking, which can be a physical address or link. If the event type is specified, it should be a valid location from that event type.")
            guest_emails: List[str] = Field(default_factory=list, description="A list of email addresses of guests to invite to the booking.")

        @tool
        def create_booking(input: CreateBookingInput) -> Dict:
            """
            Create a new booking in the calendar.
            Before calling this function, clarify the event type id, start time, open slots,
            attendees, guest emails, and location with the user.
            """
            return self.cal_api.create_booking(
                event_type_id=input.event_type_id,
                start_time=input.start_time,
                location=input.location,
                attendees=input.attendees,
                guest_emails=input.guest_emails,
            )

        @tool
        def cancel_booking(booking_uid: str, reason: str) -> Dict:
            """
            Cancel a booking based on uid
            """
            return self.cal_api.cancel_booking(booking_uid, reason)

        @tool
        def reschedule_booking(booking_uid: str, start_time: str, reason: str) -> Dict:
            """
            Reschedule a booking to new start time based on uid
            """
            return self.cal_api.reschedule_booking(booking_uid, start_time, reason)

        return [
            get_my_profile,
            get_event_types,
            get_bookings,
            get_slots,
            create_booking,
            cancel_booking,
            reschedule_booking,
        ]

    def _call_model(self, state: AgentState):
        messages = state['messages']
        logger.info(f"Calling LLM with messages: {messages}")

        llm = self.llm.bind_tools(self.tools)

        response = llm.invoke(messages)
        logger.info(f"LLM Response: {response}")

        if response.tool_calls:
            return {"messages": [response], "next_step": "call_tool"}
        else:
            return {"messages": [response], "next_step": "end"}

    def _call_tool(self, state: AgentState):
        messages = []
        for tool_call in state["messages"][-1].tool_calls:
            tool_name = tool_call["name"]
            tool_args = tool_call["args"]
            logger.info(f"Attempting to call tool: {tool_name} with args: {tool_args}")
            tool_output = next(
                (t.invoke(tool_args) for t in self.tools if t.name == tool_name),
                None,
            )
            logger.info(f"Tool {tool_name} executed. Output: {tool_output}")
            messages.append(
                ToolMessage(
                    content=str(tool_output),
                    tool_call_id=tool_call["id"],
                    name=tool_name,
                )
            )

        return {"messages": messages, "next_step": "llm_call"}

    def _initialize_graph(self):
        workflow = StateGraph(AgentState)

        workflow.add_node("llm_call", self._call_model)
        workflow.add_node("call_tool", self._call_tool)
        # workflow.add_node("human_intervene", self._human_intervene)

        workflow.add_edge(START, "llm_call")

        workflow.add_conditional_edges(
            "llm_call",
            lambda state: state["next_step"],
            {
                "call_tool": "call_tool",
                "end": END,
            },
        )
        workflow.add_edge("call_tool", "llm_call")

        app = workflow.compile(checkpointer=self.checkpointer)
        return app

    def run(self):
        thread_id = "1"  # Using a fixed thread_id for demonstration
        while True:
            try:
                user_input = input("You: ")
                if user_input.lower() in ["exit", "quit"]:
                    print("Exiting CalHelper.")
                    break

                # Invoke the graph
                # Add the user's message to the state
                initial_state = {
                    "messages": [
                        (
                            "system",
                            (
                                "You are a helpful calendar assistant."
                                f"Current local timezone is {time.tzname[time.localtime().tm_isdst]}"
                                "Time format is ISO-8601, example: 2025-07-10T09:00:00-0700."
                                "Respond everything in the current timezone."
                            ),
                        ),
                        (
                            "user",
                            f"{time.strftime('%Y-%m-%d %H:%M:%S')}: {user_input}",
                        ),
                    ]
                }

                for s in self.graph.stream(
                    initial_state,
                    config={"configurable": {"thread_id": thread_id}},
                ):
                    if "__end__" not in s: ...
                        # print(s)
                    if "llm_call" in s:
                        print("LLM Response:", s["llm_call"]["messages"][-1].content)

            except (KeyboardInterrupt, EOFError):
                print("Bye bye.")
                break
