from typing import List, Dict, Any

import os
import requests
from dotenv import load_dotenv


class CalAPI:
    API_BASE_URL = "https://api.cal.com/v2"
    API_VERSION = "2024-08-13"

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
            "cal-api-version": self.API_VERSION,
        }
        response = requests.request("GET", url, headers=headers)
        return response.json()

    def get_event_types(self, user: Dict) -> List[Dict[str, Any]]:
        """
        Fetch event types supported by the user's calendar profile.
        """
        url = f"{self.API_BASE_URL}/event-types"
        headers = {
            "Authorization": self.api_key,
            "cal-api-version": self.API_VERSION,
        }
        response = requests.request("GET", url, headers=headers)
        resp_data = response.json()

        # filter key to reduce the size of the response
        keys = ["id", "lengthInMinutes", "title", "slug", "description", "locations"]
        return [
            d[key] for d in resp_data["data"] for key in keys
        ]

    def get_bookings(
        self,
        start_date: str | None,
        end_date: str | None,
    ) -> List[Dict[str, Any]]:
        """
        Fetch bookings from the calendar between start_date and end_date.
        """
        url = f"{self.API_BASE_URL}/bookings"
        headers = {
            "Authorization": self.api_key,
            "cal-api-version": self.API_VERSION,
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

    def get_slot(
        self,
        start_date,
        end_date,
    ):
        """
        Fetch available slots from the calendar between start_date and end_date.
        """
        ...

    def create_booking(
        self,
        booking_details,
    ):
        """
        Create a new booking in the calendar.
        """
        ...

    def update_booking(
        self,
        booking_id,
        updated_details,
    ): ...
