
# cbacd.py
# Daemon for CBAC

# TODO: Hacer que sea demonio, no aplicación
# TODO: Definir configuración de .env e implementarla
# TODO: Definir comandos de consola que puedan llamar a funciones del demonio desde consola
# TODO: Función que arregla formato del calendario, log de quien crea eventos sin formato


#!.venv/bin/python3.12
import time
import os
import socket
import struct
import signal
import sys
import configparser
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo

from google.oauth2 import service_account
from googleapiclient.discovery import build
from dotenv import load_dotenv
load_dotenv() 

# from daemon import runner


# Settings
SOCKET_PATH = "/run/cbac.sock"
PACKET_MESSAGE_SIZE = 128 # 4 de codigo + 128 de mensaje
PACKET_SIZE = 4 + PACKET_MESSAGE_SIZE


# Message codes
CBAC_CHECK_SUCCESS  = 0  # User exists and has a reservation                          Message set to end of reservation time
CBAC_USER_CREATED   = 1  # User has been created correctly                            Message set to user's email address
CBAC_RESERV_CREATED = 2  # Reservation has been created for user                      Message empty
CBAC_WRONG_USER     = 3  # No reservation, occupied space                             Message empty
CBAC_EMPTY_SPACE    = 4  # No reservation but empty space                             Message empty
CBAC_API_ERROR      = 5  # Daemon couldn't process request with Google API            Message set to origin of the error
CBAC_PARAM_ERROR    = 6  # Params given to daemon not valid                           Message set to origin of the error
CBAC_OCCUPIED       = 7  # Time supplied overlaps with event in the calendar          Message informative

CBAC_CHECK_RESERV   = 10 # Asks daemon to check if user can go through.               Message set to username to check
CBAC_MAKE_RESERV    = 11 # Asks daemon to make a reservation from now                 Message set to user, when, time interval, separated by spaces
CBAC_ADD_USER       = 12 # Asks daemon to add user to the calendar of the system.     Message set to user's email address and role, separated by space



SCOPES=["https://www.googleapis.com/auth/calendar"]
CALENDAR_NAME="CBAC Calendar"
CALENDAR_ID=os.getenv("CALENDAR_ID")

class CBAC():
    def __init__(self):
        self.stdin_path = '/dev/null'
        self.stdout_path = '/var/log/cbac.log'
        self.stderr_path = '/var/log/cbac.err'
        self.pidfile_path =  '/tmp/cbacd.pid'
        self.pidfile_timeout = 5

        # init variables with conf file in /etc/cbac/cbac.conf

        # init socket
        if os.path.exists(SOCKET_PATH):
            os.remove(SOCKET_PATH)
        self.server = socket.socket(socket.AF_UNIX, socket.SOCK_SEQPACKET)
        self.server.bind(SOCKET_PATH)
        self.server.listen(1)

        # init google API
        self.credentials = service_account.Credentials.from_service_account_file(
            os.getenv("SERVICE_ACCOUNT_CREDS"),
            scopes=SCOPES
        )
        self.service = build("calendar", "v3", credentials=self.credentials)



    def get_or_create_calendar(self):
        global CALENDAR_ID

        if CALENDAR_ID:
            return CALENDAR_ID

        calendar_list = self.service.calendarList().list().execute()
        for cal in calendar_list.get("items", []):
            if cal["summary"] == CALENDAR_NAME:
                CALENDAR_ID = cal["id"]
                return CALENDAR_ID
            
        calendar = {
            "summary": CALENDAR_NAME,
            "timeZone": f"{os.getenv("TIMEZONE")}"
        }
        created = self.service.calendars().insert(body=calendar).execute()
        CALENDAR_ID = created["id"]

        with open(".env", "r") as f:
            lines = f.readlines()
        with open(".env", "w") as f:
            for line in lines:
                if line.startswith("CALENDAR_ID="):
                    f.write(f"CALENDAR_ID={CALENDAR_ID}\n")
                else:
                    f.write(line)

        return CALENDAR_ID
    


    # Checks the status of a calendar at a given time (datetime format) with a given offset (int in minutes)
    # Returns the status of the calendar at that time, and if there is an event at the time, returns the event
    def check_calendar_on_time(self, when, offset):
        event_list = self.get_events(when)

        when_end = when + timedelta(minutes=offset)

        if event_list == None:
            return CBAC_EMPTY_SPACE, None
        
        for event in event_list:
            start_str = event["start"].get("dateTime")
            end_str = event["end"].get("dateTime")

            if not start_str or not end_str:
                return CBAC_API_ERROR, None
                
            start_dt = datetime.fromisoformat(start_str)
            end_dt = datetime.fromisoformat(end_str)

            if when <= end_dt and start_dt <= when_end:
                return CBAC_OCCUPIED, event
            
        return CBAC_EMPTY_SPACE, None
            


    def get_events(self, when_dt):
        calendar_id = self.get_or_create_calendar()

        when_str = when_dt.isoformat()

        events = self.service.events().list(
            calendarId=calendar_id,
            timeMin=(when_dt - timedelta(hours=2)).isoformat(),
            timeMax=(when_dt + timedelta(hours=2)).isoformat(),
            maxResults=10,
            singleEvents=True,
            orderBy='startTime'
        ).execute()

        event_list = events.get('items', [])

        if not event_list:
            return None
        
        return event_list



    def format_calendar(self):
        pass



    def create_packet(self, code, message):
        return struct.pack(f"!i{PACKET_MESSAGE_SIZE}s", code, message.encode())



    def make_reserv(self, user, when, offset) -> struct:
        calendar_id = self.get_or_create_calendar()
        start_dt = self.parse_timestamp(when)

        if start_dt == None:
            return self.create_packet(CBAC_PARAM_ERROR, "Timestamp not valid")
        
        if not offset.isDigit():
            return self.create_packet(CBAC_PARAM_ERROR, "Time interval not valid")

        if int(offset) > int(os.getenv("MAX_TIME")):
            return self.create_packet(CBAC_PARAM_ERROR, "Requested more than the max time")

        end_dt = start_dt + timedelta(minutes=int(offset))

        if self.check_calendar_on_time(when, int(offset)):
            event = {
                "summary": user,
                "description": "",
                "start": {
                    "dateTime": datetime.isoformat(start_dt),
                    "timeZone": os.getenv("TIMEZONE"),
                },
                "end": {
                    "dateTime": datetime.isoformat(end_dt),
                    "timeZone": os.getenv("TIMEZONE"),
                }
            }
            insert = self.service.events().insert(
                calendar_id = calendar_id,
                body=event
            ).execute()

            return self.create_packet(CBAC_RESERV_CREATED, "")
        else:
            return self.create_packet(CBAC_OCCUPIED, "Time occupied on calendar")



    def add_user_to_calendar(self, user_email, role):
        calendar_id = self.get_or_create_calendar()

        if not user_email.endswith("@gmail.com"):
            return self.create_packet(CBAC_PARAM_ERROR, "User address not valid")

        if role not in ["writer", "reader", "freeBusyReader"]:
            return self.create_packet(CBAC_PARAM_ERROR, "Role not valid")

        rule = {
            "scope":{
                "type":"user",
                "value":user_email
            },
            "role":role
        }

        created_rule = self.service.acl().insert(calendarId=calendar_id, body=rule).execute()

        return self.create_packet(CBAC_USER_CREATED, user_email)

    

    def check_reserv(self, user) -> struct:
        now_dt = datetime.now(ZoneInfo(os.getenv("TIMEZONE")))
        now = now_dt.isoformat()

        curr_events = self.get_events(now_dt)

        if curr_events == None:
            return self.create_packet(CBAC_EMPTY_SPACE, "")

        status, event = self.check_calendar_on_time(now_dt, 0)

        if status == CBAC_OCCUPIED:
            if event["summary"] == user:
                return self.create_packet(CBAC_CHECK_RESERV, event["end"].get("dateTime"))
            else:
                return self.create_packet(CBAC_WRONG_USER, event["end"].get("dateTime"))

        return self.create_packet(CBAC_WRONG_USER, "")



    def treat_packet(self, data_recv) -> struct:
        code_recv, message_recv = struct.unpack(f'!i{PACKET_MESSAGE_SIZE}s', data_recv)
        message_recv = message_recv.rstrip(b'\x00').decode('utf-8')

        data_send = None

        # Tratar según el código
        if code_recv == CBAC_CHECK_RESERV:
            data_send = self.check_reserv(message_recv)
        elif code_recv == CBAC_MAKE_RESERV:
            user, when, time = message_recv.split()
            data_send = self.make_reserv(user, when, time)
        elif code_recv == CBAC_ADD_USER:
            user_email, role = message_recv.split()
            data_send = self.add_user(user_email, role)

        return data_send




    # Aux functions

    def parse_timestamp(s: str):
        try:
            dt = datetime.fromisoformat(s)
            if dt.tzinfo is not None:
                raise ValueError("Timezone no permitida")
            return dt
        except ValueError:
            return None



    # Main loop

    def run(self):
        data_recv = None

        while True:
            print("Inside run loop\n")
            conn, _ = self.server.accept()
            data_recv = conn.recv(PACKET_SIZE)
            print("Data received")

            code_recv, message_recv = struct.unpack(f'!i{PACKET_MESSAGE_SIZE}s', data_recv)
            message_recv = message_recv.rstrip(b'\x00').decode('utf-8')

            print(f"Code: {code_recv}")
            print(f"Message: {message_recv}\n")

            data_send = self.treat_packet(data_recv)
            conn.sendall(data_send)

            code_send, message_send = struct.unpack(f'!i{PACKET_MESSAGE_SIZE}s', data_send)

            print("Data Sent")
            print(f"Code: {code_send}")
            print(f"Message: {message_send}")

            time.sleep(5)



cbac = CBAC()

# cbac.add_user_to_calendar("pablofstrecovery@gmail.com", "writer")
# print(cbac.ask_google("servertfg"))

cbac.run()

# daemon_runner = runner.DaemonRunner(cbac)
# daemon_runner.do_action()
