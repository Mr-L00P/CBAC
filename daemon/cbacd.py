
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
import threading
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


# Packet response codes
CBAC_CHECK_SUCCESS  = 0  # User exists and has a reservation                          Message set to end of reservation time
CBAC_USER_CREATED   = 1  # User has been created correctly                            Message set to user's email address
CBAC_RESERV_CREATED = 2  # Reservation has been created for user                      Message empty
CBAC_WRONG_USER     = 3  # No reservation, occupied space                             Message empty
CBAC_EMPTY_SPACE    = 4  # No reservation but empty space                             Message empty
CBAC_API_ERROR      = 5  # Daemon couldn't process request with Google API            Message set to origin of the error
CBAC_PARAM_ERROR    = 6  # Params given to daemon not valid                           Message set to origin of the error
CBAC_OCCUPIED       = 7  # Time supplied overlaps with event in the calendar          Message informative

# Packet request codes
CBAC_CHECK_RESERV   = 10 # Asks daemon to check if user can go through.               Message set to username to check
CBAC_MAKE_RESERV    = 11 # Asks daemon to make a reservation from now                 Message set to user, when, time interval, separated by spaces
CBAC_ADD_USER       = 12 # Asks daemon to add user to the calendar of the system.     Message set to user's email address and role, separated by space



SCOPES=["https://www.googleapis.com/auth/calendar"]
CALENDAR_NAME="CBAC Calendar"
CALENDAR_ID=os.getenv("CALENDAR_ID")



# Types of message to sent to user, useful only in message_user()
i = 0
k = 1
e = 2



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



    # Returns the ID of the current calendar or creates the calendar, sets the env variable and returns it.
    def get_or_create_calendar(self) -> str:
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
    


    # Returns the status of the calendar at that time, and if there is an event at the time, returns the event
    def check_calendar_on_time(self, when_dt: datetime, offset: int):
        event_list = self.get_events(when_dt)

        when_end = when_dt + timedelta(minutes=offset)

        if event_list == None:
            return CBAC_EMPTY_SPACE, None
        
        for event in event_list:
            start_str = event["start"].get("dateTime")
            end_str = event["end"].get("dateTime")

            if not start_str or not end_str:
                return CBAC_API_ERROR, None
                
            start_dt = datetime.fromisoformat(start_str)
            end_dt = datetime.fromisoformat(end_str)

            if when_dt <= end_dt and start_dt <= when_end:
                return CBAC_OCCUPIED, event
            
        return CBAC_EMPTY_SPACE, None
            


    # Returns a list of event objects from the API within a time frame from a given datetime
    def get_events(self, when_dt: datetime):
        calendar_id = self.get_or_create_calendar()

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



    # Function to delete the events on the calendar with a given time, logs the event and user of the deleted events
    def format_calendar(self, when_dt: datetime):
        pass


    # Creates and returns the packet with a given code and message
    def create_packet(self, code: str, message: str) -> struct:
        return struct.pack(f"!i{PACKET_MESSAGE_SIZE}s", code, message.encode())



    # Attempts to make a reservation and returns the status struct to send back to the client
    def make_reserv(self, user: str, when: str, offset: str) -> struct:
        calendar_id = self.get_or_create_calendar()
        start_dt = self.parse_timestamp(when)

        if start_dt == None:
            return self.create_packet(CBAC_PARAM_ERROR, "Timestamp not valid")
        
        if not offset.isdigit():
            return self.create_packet(CBAC_PARAM_ERROR, "Time interval not valid")

        if int(offset) > int(os.getenv("MAX_TIME")):
            return self.create_packet(CBAC_PARAM_ERROR, "Requested more than the max time")

        end_dt = start_dt + timedelta(minutes=int(offset))

        if self.check_calendar_on_time(start_dt, int(offset)):
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
                calendarId = calendar_id,
                body=event
            ).execute()

            return self.create_packet(CBAC_RESERV_CREATED, "")
        else:
            return self.create_packet(CBAC_OCCUPIED, "Time occupied on calendar")



    # Attempts to add user to the calendar and returns the status struct to send back to the client  
    def add_user_to_calendar(self, user_email: str, role: str):
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

    

    # Checks if the current event on the calendar matches the user supplied
    def check_reserv(self, user: str) -> struct:
        now_dt = datetime.now(ZoneInfo(os.getenv("TIMEZONE")))
        now = datetime.isoformat(now_dt)

        curr_events = self.get_events(now_dt)

        if curr_events == None:
            return self.create_packet(CBAC_EMPTY_SPACE, "")

        status, event = self.check_calendar_on_time(now_dt, 0)

        if status == CBAC_OCCUPIED:
            if event["summary"] == user:
                return self.create_packet(CBAC_CHECK_SUCCESS, event["end"].get("dateTime"))
            else:
                return self.create_packet(CBAC_WRONG_USER, event["end"].get("dateTime"))

        return self.create_packet(CBAC_WRONG_USER, "")



    # Main logic to process packets based on the code, returns the corresponding struct to send back to client
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



    def parse_timestamp(self, when: str):
        try:
            dt = datetime.fromisoformat(when)
            if dt.tzinfo != timezone.utc:
                raise ValueError("Timezone no permitida")
            return dt
        except ValueError:
            return None



    # Sends message to the client through the terminal they're connected to via SSH, additionally you can add a type to make the message informative, a confirmation
    # or an error, used for direct communication with client without requiring an initial connection from the client
    def message_user(self,user: str, message: str, type=None):
        if type == i:
            message = "[*] - " + message
        elif type == k:
            message = "[+] - " + message
        elif type == e:
            message = "[-] - " + message
        
        pass



    # Thread for the current ssh session, informative messages and eventually termination of the process
    def handle_session(self, user: str, time_left: timedelta):
        print("Waiting time left of reservation...")
        secs_left = time_left.total_seconds()
        
        if secs_left < 300:
            self.message_user(user, "Less than 5 minutes remaning before session is terminated automatically", i)
            time.sleep(secs_left)
        else:
            time.sleep(secs_left - 300)
            self.message_user(user, "5 minutes remaining for session to be terminated automatically", i)
            time.sleep(300)
            
        self.message_user(user, "Session ended, forcefully terminating process...", e)
        print("Killing ssh process of user")
        os.system(f"pkill -u {user} -f sshd")


    # Main loop

    def run(self):
        data_recv = None

        while True:
            print("Inside run loop\n")
            conn, _ = self.server.accept()
            while True:
                data_recv = conn.recv(PACKET_SIZE)

                if not data_recv:
                    print("Client disconnected")
                    break

                print("Data received")

                code_recv, message_recv = struct.unpack(f'!i{PACKET_MESSAGE_SIZE}s', data_recv)
                message_recv = message_recv.rstrip(b'\x00').decode('utf-8')

                print(f"Code: {code_recv}")
                print(f"Message: {message_recv}\n")

                data_send = self.treat_packet(data_recv)
                code_send, message_send = struct.unpack(f'!i{PACKET_MESSAGE_SIZE}s', data_send)
                message_send = message_send.rstrip(b'\x00').decode('utf-8')
                conn.sendall(data_send)

                if code_send == CBAC_CHECK_SUCCESS:
                    time_left = (datetime.fromisoformat(message_send) - datetime.now(timezone.utc))
                    conn_thread = threading.Thread(target=self.handle_session, args=(message_recv, time_left, ))
                    conn_thread.start()

                print("Data Sent")
                print(f"Code: {code_send}")
                print(f"Message: {message_send}")

            # time.sleep(5)


if __name__ == "__main__":
    cbac = CBAC()
    cbac.run()