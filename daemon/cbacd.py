
# cbacd.py
# Daemon for CBAC

# TODO: Hacer que sea demonio, no aplicación
# TODO: Definir configuración de .env e implementarla
# TODO: Definir comandos de consola que puedan llamar a funciones del demonio desde consola
# TODO: Función que arregla formato del calendario, log de quien crea eventos sin formato
# TODO: nombre de evento case-insensitive


#!.venv/bin/python3.12
import time
import os
import socket
import struct
import signal
import sys
import configparser
from datetime import datetime, timezone, timedelta

from google.oauth2 import service_account
from googleapiclient.discovery import build
from dotenv import load_dotenv
load_dotenv() 

# from daemon import runner


# Settings
SOCKET_PATH = "/run/cbac.sock"
PACKET_MESSAGE_SIZE = 64 # 4 de codigo + 64 de mensaje
PACKET_SIZE = 4 + PACKET_MESSAGE_SIZE


# Message codes
CBAC_SUCCESS      = 0  # User exists and has a reservation
CBAC_WRONG_USER   = 1  # No reservation, occupied space
CBAC_EMPTY_SPACE  = 2  # No reservation but empty space
CBAC_API_ERROR    = 3  # Daemon couldn't process request with Google API

CBAC_CHECK_RESERV = 10 # Asks daemon to check if user can go through. Message set to username to check
CBAC_MAKE_RESERV  = 11 # Asks daemon to make a reservation from now   Message set to time interval desired
CBAC_ADD_USER     = 12 # Asks daemon to add user to the calendar of the system



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
            "timeZone": "Europe/Madrid"
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

    def add_user_to_calendar(self, user_email, role):
        calendar_id = self.get_or_create_calendar()

        rule = {
            "scope":{
                "type":"user",
                "value":user_email
            },
            "role":role
        }

        created_rule = self.service.acl().insert(calendarId=calendar_id, body=rule).execute()

        return created_rule
    
    def ask_google(self, user):
        calendar_id = self.get_or_create_calendar()

        now_dt = datetime.now(timezone.utc)
        now = now_dt.isoformat()

        curr_event_list = self.service.events().list(
            calendarId=calendar_id,
            timeMin=(now_dt - timedelta(hours=2)).isoformat(),
            timeMax=(now_dt + timedelta(hours=2)).isoformat(),
            maxResults=10,
            singleEvents=True,
            orderBy='startTime'
        ).execute()

        curr_events = curr_event_list.get('items', [])

        if not curr_events:
            return CBAC_API_ERROR

        for event in curr_events:
            start_str = event["start"].get("dateTime")
            end_str = event["end"].get("dateTime")

            if not start_str or not end_str:
                return CBAC_API_ERROR
                

            start_dt = datetime.fromisoformat(start_str)
            end_dt = datetime.fromisoformat(end_str)

            if (start_dt <= now_dt <= end_dt) and (user == event.get("summary")):
                return CBAC_SUCCESS

        return CBAC_WRONG_USER

    def format_calendar(self):
        pass


    # main loop

    def run(self):
        data = None

        while True:
            print("Inside run loop\n")
            conn, _ = self.server.accept()
            data_recv = conn.recv(PACKET_SIZE)
            print("Data received")

            code_recv, message_recv = struct.unpack('!i64s', data_recv)
            message_recv = message_recv.rstrip(b'\x00').decode('utf-8')

            print(f"Code: {code_recv}")
            print(f"Message: {message_recv}\n")


            # Packet set
            code_send = self.ask_google(message_recv)
            message_send = ""


            data_send = struct.pack("!i64s", code_send, message_send.encode())
            conn.sendall(data_send)

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
