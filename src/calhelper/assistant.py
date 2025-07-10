import os
import time
from typing import TypedDict, Annotated, Dict

from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables import RunnableLambda
from langchain_core.messages import BaseMessage, ToolMessage

from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.checkpoint.memory import MemorySaver

from calhelper.api import CalAPI


class AgentState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]
    tool_outcome: Annotated[list[ToolMessage], add_messages]
    next_step: str


class CalHelper:

    def __init__(self):
        self.cal_api = CalAPI()
        self.llm = ChatOpenAI(model="gpt-4o", temperature=0.0)
        self.tools = self._initialize_tools()
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

        @tool
        def create_booking(
            event_type_id: str,
            start_time: str,
            end_time: str,
            title: str,
            description: str | None = None,
            attendees: list[str] | None = None,
        ) -> dict:
            """
            Create a new booking in the calendar.
            """
            return self.cal_api.create_booking(
                event_type_id=event_type_id,
                start_time=start_time,
                end_time=end_time,
                title=title,
                description=description,
                attendees=attendees,
            )

        return [
            get_my_profile,
            get_event_types,
            get_bookings,
            get_slots,
            create_booking,
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

        if tool_name == "create_booking":
            print("\n--Human Approval Required--")
            print("\nYour helper wants to call the following function:")
            print(f"  Tool Name: {tool_name}")
            print(f"  Arguments: {tool_args}")
            print("\nDo you approve this action? (yes/no)")
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
        messages = state["messages"]
        llm = self.llm.bind_tools(self.tools)

        response = llm.invoke(messages)

        return {"messages": [response]}

    def _call_tool(self, state: AgentState):
        tool_messages = []
        for tool_call in state["messages"][-1].tool_calls:
            tool_name = tool_call["name"]
            tool_args = tool_call["args"]
            if self._custom_approve({"name": tool_name, "args": tool_args}):
                tool_output = next(
                    (t.invoke(tool_args) for t in self.tools if t.name == tool_name),
                    None,
                )
                tool_messages.append(
                    ToolMessage(
                        content=str(tool_output),
                        tool_call_id=tool_call["id"],
                        name=tool_name,
                    )
                )
            else:
                tool_messages.append(
                    ToolMessage(
                        content="Tool call rejected by user.",
                        tool_call_id=tool_call["id"],
                        name=tool_name,
                    )
                )
        return {"messages": tool_messages}

        return {
            "messages": [BaseMessage(content=user_input, type="human")],
            "next_step": "continue",
        }

    def _should_continue(self, state: AgentState):
        messages = state["messages"]
        last_message = messages[-1]
        if last_message.tool_calls:
            return "continue"
        return "end"

    def _initialize_graph(self):
        workflow = StateGraph(AgentState)

        workflow.add_node("llm_call", self._call_model)
        workflow.add_node("call_tool", self._call_tool)
        # workflow.add_node("human_intervene", self._human_intervene)

        workflow.add_edge(START, "llm_call")
        workflow.add_conditional_edges(
            "llm_call",
            self._should_continue,
            {
                "continue": "call_tool",
                "end": END,
            },
        )
        workflow.add_edge("call_tool", "llm_call")
        # workflow.add_edge("human_intervene", "llm_call")

        app = workflow.compile()
        return app

    def run(self):
        while True:
            try:
                user_input = input("You: ")
                if user_input.lower() in ["exit", "quit"]:
                    print("Exiting CalHelper.")
                    break

                # Add the user's message to the state
                initial_state = {
                    "messages": [
                        (
                            "system",
                            (
                                "You are a helpful calendar assistant."
                                "Current local timezone is {time.tzname(time.localtime().tm_isdst)}"
                            ),
                        ),
                        (
                            "user",
                            f"{time.strftime('%Y-%m-%d %H:%M:%S')}: {user_input}",
                        ),
                    ]
                }

                # Invoke the graph
                for s in self.graph.stream(initial_state):
                    if "__end__" not in s:
                        print(s)
                    if "llm_call" in s:
                        print("LLM Response:", s["llm_call"]["messages"][-1].content)

            except (KeyboardInterrupt, EOFError):
                print("Bye bye.")
                break
