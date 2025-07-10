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
        def get_event_types() -> list[dict]:
            """
            Fetch event types supported by the user's calendar profile.
            """
            return self.cal_api.get_event_types(user=self.cal_api.profile)

        @tool
        def get_bookings(
            start_date: str | None = None, end_date: str | None = None
        ) -> list[dict]:
            """
            Fetch bookings from the calendar between start_date and end_date.
            """
            return self.cal_api.get_bookings(start_date=start_date, end_date=end_date)

        @tool
        def get_slots(
            event_type_id: str,
            start_date: str | None = None,
            end_date: str | None = None,
        ) -> list[dict]:
            """
            Fetch available slots for a specific event type between start_date and end_date.
            """
            return self.cal_api.get_slots(
                event_type_id=event_type_id, start_date=start_date, end_date=end_date
            )

        class CreateBookingInput(BaseModel):
            event_type_id: int = Field(description="The ID of the event type to book.")
            start_time: str = Field(description="The start time of the booking in ISO-8601 format.")
            attendees: Attendee = Field(description="A dictionary containing the attendee's details.")
            location: Location = Field(description="The location of the booking, which can be a physical address or link. If the event type is specified, it should be a valid location from that event type.")
            guest_emails: List[str] = Field(default_factory=list, description="A list of email addresses of guests to invite to the booking.")

        @tool
        def create_booking(input: CreateBookingInput) -> dict:
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
        def cancel_booking(uid: str, reason: str) -> dict:
            """
            Cancel a booking based on uid
            """
            return self.cal_api.cancel_booking(uid, reason)

        return [
            get_my_profile,
            get_event_types,
            get_bookings,
            get_slots,
            create_booking,
            cancel_booking,
        ]

    def _custom_approve(self, tool_dict: Dict) -> bool:
        """
        Custom approval function for the HumanApprovalCallbackHandler.
        This function can be modified to implement custom logic for approving
        the tool calls made by the agent.
        """
        # Here you can implement your custom logic to approve or reject the tool call
        tool_name = tool_dict.get("name")
        tool_args = tool_dict.get("args")

        if tool_name in ["create_booking", "cancel_booking"]:
            print("\n--Human Approval Required--")
            print("\nYour helper wants to call the following function:")
            print(f"  Tool Name: {tool_name}")
            print(f"  Arguments: {tool_args}")
            confirmation = (
                input("Do you approve this action? (yes/no): ").strip().lower()
            )
            if confirmation in ("yes", "y"):
                print("Action approved. Executing tool...")
                return True
            else:
                print("Action rejected by user.")
                return False

        return True

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
        all_approved = True
        for tool_call in state["messages"][-1].tool_calls:
            tool_name = tool_call["name"]
            tool_args = tool_call["args"]
            logger.info(f"Attempting to call tool: {tool_name} with args: {tool_args}")
            if self._custom_approve({"name": tool_name, "args": tool_args}):
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
            else:
                all_approved = False
                logger.warning(f"Tool {tool_name} call rejected by user.")
                messages.append(
                    ToolMessage(
                        content="User rejected this tool call.",
                        tool_call_id=tool_call["id"],
                        name=tool_name,
                    )
                )

        if all_approved:
            return {"messages": messages, "next_step": "llm_call"}
        else:
            return {"messages": messages, "next_step": "human_intervene"}

    def _human_intervene(self, state: AgentState):
        """
        This function is called when the agent needs human intervention.
        It can be used to log the state or notify the user.
        """
        print("Human intervention required. Current state:")
        user_input = input("Please provide your feedback to continue: ")

        messages = [
            HumanMessage(
                content=f"User feedback: {user_input}",
                additional_kwargs={"timestamp": time.strftime("%Y-%m-%d %H:%M:%S")},
            )
        ]
        return {"messages": messages}

    def _should_intervene(self, state: AgentState):
        if state["next_step"] == "human_intervene":
            return "human_intervene"
        elif state["next_step"] == "call_tool":
            return "call_tool"
        elif state["next_step"] == "llm_call":
            return "llm_call"
        else:
            return "end"

    def _initialize_graph(self):
        workflow = StateGraph(AgentState)

        workflow.add_node("llm_call", self._call_model)
        workflow.add_node("call_tool", self._call_tool)
        workflow.add_node("human_intervene", self._human_intervene)

        workflow.add_edge(START, "llm_call")

        workflow.add_conditional_edges(
            "llm_call",
            lambda state: state["next_step"],
            {
                "call_tool": "call_tool",
                "end": END,
            },
        )

        workflow.add_conditional_edges(
            "call_tool",
            self._should_intervene,
            {
                "llm_call": "llm_call",
                "human_intervene": "human_intervene",
                "end": END,
            },
        )
        workflow.add_edge("human_intervene", "llm_call")

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
