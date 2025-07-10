from typing import List, Dict, Any, Literal, Optional

import os
import requests
from dataclasses import dataclass
from dotenv import load_dotenv


@dataclass
class Attendee:
    """
    Represents an attendee for a calendar event.
    """

    name: str
    email: str
    timeZone: str = "America/Los_Angeles"
    phoneNumber: str = ""


class Location1:
    type: Literal = "address"


class Location2:
    type: Literal = "attendeeAddress"
    address: str


class Location3:
    type: Literal = "attendeeDefined"
    location: str


class Location4:
    type: Literal = "integration"
    integration: str


Location = Location1 | Location2 | Location3 | Location4


class CalAPI:
    API_BASE_URL = "https://api.cal.com/v2"

    def __init__(self):
        load_dotenv()

        self.api_key = os.getenv("CAL_API_KEY")
        if not self.api_key:
            raise ValueError("CAL_API_KEY environment variable is not set.")

        self.profile = self.get_my_profile()

    def get_my_profile(self) -> Dict[str, Any]:
        """Fetch the profile of the authenticated user from the calendar API."""

        url = f"{self.API_BASE_URL}/me"
        headers = {
            "Authorization": self.api_key,
            "cal-api-version": "2024-08-13",
        }
        response = requests.request("GET", url, headers=headers)
        return response.json()["data"]

    def get_event_types(self, user: Dict) -> List[Dict[str, Any]]:
        """
        Fetch event types supported by the user's calendar profile.
        """
        if not user:
            user = self.get_my_profile()

        url = f"{self.API_BASE_URL}/event-types"
        headers = {
            "Authorization": self.api_key,
            "cal-api-version": "2024-06-14",
        }
        query = {"username": user.get("username")}

        response = requests.request("GET", url, headers=headers, params=query)
        resp_data = response.json()

        # filter key to reduce the size of the response
        keys = ["id", "lengthInMinutes", "title", "slug", "description", "locations"]
        print(f"Response data: {resp_data}")
        return [d[key] for d in resp_data["data"] for key in keys]

    def get_bookings(
        self,
        start_date: str | None,
        end_date: str | None,
    ) -> List[Dict[str, Any]]:
        """
        Fetch meeting bookings from the calendar between start_date and end_date.
        """
        url = f"{self.API_BASE_URL}/bookings"
        headers = {
            "Authorization": self.api_key,
            "cal-api-version": "2024-08-13",
        }

        params = {"take": "100"}
        if start_date:
            params["start"] = start_date
        if end_date:
            params["end"] = end_date

        response = requests.request("GET", url, headers=headers, params=params)
        resp_data = response.json()

        keys = ["id", "title", "description", "status", "start", "end", "duration"]
        return [
            {key: booking[key] for key in keys if key in booking}
            for booking in resp_data["data"]
        ]

    def get_slots(
        self,
        event_type_id: int,
        start_date: str,
        end_date: str,
    ):
        """
        Fetch available slots from the calendar between start_date and end_date.
        """
        url = f"{self.API_BASE_URL}/slots"
        headers = {
            "Authorization": self.api_key,
            "cal-api-version": "2024-09-04",
        }
        params = {
            "start": start_date,
            "end": end_date,
            "eventTypeId": event_type_id,
        }
        response = requests.request("GET", url, headers=headers, params=params)
        return response.json()["data"]

    def create_booking(
        self,
        event_type_id: int,
        start_time: str,
        attendees: Attendee,
        location: Location,
        guest_emails: List[str] = [],
    ):
        """
        Create a new booking in the calendar.
        """
        url = f"{self.API_BASE_URL}/bookings"
        headers = {
            "Authorization": self.api_key,
            "cal-api-version": "2024-08-13",
            "Content-Type": "application/json",
        }

        request = {
            "start": start_time,
            "eventTypeId": event_type_id,
            "attendee": {
                "name": attendees.name,
                "email": attendees.email,
                "timeZone": attendees.timeZone,
                "phoneNumber": attendees.phoneNumber,
            },
            "guests": guest_emails,
            "location": location,
        }
        response = requests.request("POST", url, headers=headers, json=request)
        resp_data = response.json()

        if resp_data["status"] == "success":
            return resp_data["data"]
        else:
            return resp_data["error"]

    def update_booking(
        self,
        booking_id,
        updated_details,
    ): ...
