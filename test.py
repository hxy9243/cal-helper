# import requests

# url = "https://api.cal.com/v2/bookings"

# payload = {
#     "attendee": {
#         "language": "en",
#         "name": "Kevin",
#         "timeZone": "America/Los_Angeles",
#         "email": "example@gmail.com"
#     },
#     "start": "2025-07-10T11:20:00-0700",
#     "eventTypeId": 2821630,
#     "location": {"type": "integration",           "integration": "cal-video"}
# }
# headers = {
#     "Authorization": "cal_live_189181ddcd40a32fbdc4100a29cc193b",
#     "cal-api-version": "2024-08-13",
#     "Content-Type": "application/json"
# }

# response = requests.request("POST", url, json=payload, headers=headers)

print(response.text)

import requests

url = "https://api.cal.com/v2/bookings"

querystring = {"take":"100"}

headers = {
    "Authorization": "cal_live_189181ddcd40a32fbdc4100a29cc193b",
    "cal-api-version": "2024-08-13"
}

response = requests.request("GET", url, headers=headers, params=querystring)

print(response.text)