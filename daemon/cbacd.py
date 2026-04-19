
# cbacd.py
# Daemon for CBAC

# TODO: Definir configuración de .env e implementarla
# TODO: Función que arregla formato del calendario, log de quien crea eventos sin formato


#!.venv/bin/python3.12
import time
import os
import subprocess
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
SOCKET_PATH = "/run/cbacd/cbac.sock"
PACKET_MESSAGE_SIZE = 128 # 4 de codigo + 128 de mensaje
PACKET_SIZE = 4 + PACKET_MESSAGE_SIZE


# Packet response codes
CBAC_OK             = 0  # General success flag                                       Message empty
CBAC_CHECK_SUCCESS  = 1  # User exists and has a reservation                          Message set to end of reservation time
CBAC_USER_CREATED   = 2  # User has been created correctly                            Message set to user's email address
CBAC_USER_DELETED   = 3  # User has been deleted correctly                            Message set to user's email address
CBAC_RESERV_CREATED = 4  # Reservation has been created for user                      Message empty
CBAC_WRONG_USER     = 5  # No reservation, occupied space                             Message empty
CBAC_EMPTY_SPACE    = 6  # No reservation but empty space                             Message empty
CBAC_API_ERROR      = 7  # Daemon couldn't process request with Google API            Message set to origin of the error
CBAC_PARAM_ERROR    = 8  # Params given to daemon not valid                           Message set to origin of the error
CBAC_OCCUPIED       = 9  # Time supplied overlaps with event in the calendar          Message informative

# Packet request codes
CBAC_CHECK_RESERV   = 10 # Asks daemon to check if user can go through.               Message set to username to check
CBAC_MAKE_RESERV    = 11 # Asks daemon to make a reservation from now                 Message set to user, when, time interval, separated by spaces
CBAC_DEL_RESERV     = 12 # Asks daemon to delete a certain event                      Message set to timestamp intersecting with the event
CBAC_ADD_USER       = 13 # Asks daemon to add user to the calendar of the system.     Message set to user's email address and role, separated by space
CBAC_DEL_USER       = 14 # Asks daemon to delete user from the calendar               Message set to user's email address
CBAC_UPDATE_CONF    = 15 # Asks daemon to update env variables                        Message empty


SCOPES=["https://www.googleapis.com/auth/calendar"]
CALENDAR_NAME="CBAC Calendar"
CALENDAR_ID=os.getenv("CALENDAR_ID")



# Types of message to sent to user, useful only in message_user()
i = 0
k = 1
e = 2



class CBAC():
    def __init__(self):
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
    def get_events(self, when_dt: datetime, offset=120):
        calendar_id = self.get_or_create_calendar()

        events = self.service.events().list(
            calendarId=calendar_id,
            timeMin=(when_dt - timedelta(minutes=offset)).isoformat(),
            timeMax=(when_dt + timedelta(minutes=offset)).isoformat(),
            maxResults=10,
            singleEvents=True,
            orderBy='startTime'
        ).execute()

        event_list = events.get('items', [])

        if not event_list:
            return None
        
        return event_list



    # Function to delete the events on the calendar with a given time, logs the event and user of the deleted events
    def fix_events(self, when_dt: datetime):
        calendar_id = self.get_or_create_calendar()
        event_list = self.get_events(when_dt, offset=(os.getenv("MAX_EVENT_MINUTES") * 2))

        unformatted_list = []

        for event in event_list:
            start_dt = self.parse_timestamp(event["startime"].get("dateTime"))
            end_dt = self.parse_timestamp(event["end".get("dateTime")])

            if (end_dt - start_dt) < timedelta(minutes=os.getenv("MAX_RESERV_MINUTES")):
                unformatted_list.append(event)

        for event in unformatted_list:
            self.service.events().delete(
                calendarId = calendar_id,
                eventId = event["id"]
            ).execute()



    # Creates and returns the packet with a given code and message
    def create_packet(self, code: int, message: str) -> struct:
        return struct.pack(f"!i{PACKET_MESSAGE_SIZE}s", code, message.encode())



    # Attempts to make a reservation and returns the status struct to send back to the client
    def make_reserv(self, user: str, when: str, offset: str) -> struct:
        calendar_id = self.get_or_create_calendar()
        start_dt = self.parse_timestamp(when)

        if start_dt == None:
            return self.create_packet(CBAC_PARAM_ERROR, "Timestamp not valid")
        
        if not offset.isdigit():
            return self.create_packet(CBAC_PARAM_ERROR, "Time interval not valid")

        if int(offset) > int(os.getenv("MAX_RESERV_MINUTES")):
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



    # Attempts to delete an event from the calendar with a given time
    def del_reserv(self, when: str):
        calendar_id = self.get_or_create_calendar()
        when_dt = self.parse_timestamp(when)
        events = self.get_events(when_dt, 0)

        if not events:
            return self.create_packet(CBAC_PARAM_ERROR, "No event in timestamp given")
        
        for event in events:
            self.service.events().delete(
                calendarId=calendar_id,
                eventId = event["id"]
            ).execute()



    # Attempts to add user to the calendar and returns the status struct to send back to the client  
    def add_user_to_calendar(self, user_email: str, role: str) -> struct:
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

    

    def del_user_from_calendar(self, user_email: str) -> struct:
        calendar_id = self.get_or_create_calendar()

        if not user_email.endswith("@gmail.com"):
            return self.create_packet(CBAC_PARAM_ERROR, "User address not valid")

        try:
            self.service.acl().delete(
                calendarId=calendar_id,
                ruleId=user_email
            ).execute()

            return self.create_packet(CBAC_USER_DELETED, user_email)

        except Exception as e:
            return self.create_packet(CBAC_API_ERROR, "Couldn't remove user from calendar")



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
    


    # Updates env variables when asked by client
    def update_conf(self) -> struct:
        load_dotenv(override=True)
        return self.create_packet(CBAC_OK, "")



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
            data_send = self.add_user_to_calendar(user_email, role)
        elif code_recv == CBAC_DEL_USER:
            user_email = message_recv
            data_send = self.del_user_from_calendar(user_email)
        elif code_recv == CBAC_DEL_RESERV:
            when = message_recv
            data_send = self.del_reserv(when)

        return data_send



    def parse_timestamp(self, when: str):
        dt = datetime.fromisoformat(when)
        return dt



    # Sends message to the client through the terminal they're connected to via SSH, additionally you can add a type to make the message informative, a confirmation
    # or an error, used for direct communication with client without requiring an initial connection from the client
    def message_sessions(self,user: str, message: str, type=None):
        if type == i:
            message = "[*] - " + message
        elif type == k:
            message = "[+] - " + message
        elif type == e:
            message = "[-] - " + message
        
        try:
            subprocess.run(["sudo", "wall", message])
        except:
            pass


    
    # Thread for fixing events every EVENT_FIX_MINUTES time, defined in .env
    def fix_event_loop(self):
        secs = os.getenv("EVENT_FIX_MINUTES") * 60
        while(True):
            self.fix_events(datetime.now())
            time.sleep(secs)



    # Thread for the current ssh session, informative messages and eventually termination of the process
    def handle_session(self, user: str, time_left: timedelta):
        print("Waiting time left of reservation...")
        seconds_left = time_left.total_seconds()

        if seconds_left > 300:
            seconds_left -= 300
            time.sleep(seconds_left)
            self.message_sessions(user, "5 minutes left in session", i)
            time.sleep(300)
        else:
            self.message_sessions(user, f"{int(seconds_left)} seconds left in session", i)
            time.sleep(time_left.total_seconds())
        
        list_sessions = subprocess.check_output(["sudo", "loginctl", "list-sessions"]).decode()
        sessions = []

        for line in list_sessions.splitlines()[1:]:
            info = line.split()
            if len(info) >= 3 and info[2] == user:
                sessions.append(info[0])

        for session in sessions:
            self.message_sessions(user, "Session terminated...", i)
            subprocess.run(["sudo", "loginctl", "kill-session", session])


    # Main loop

    def run(self):
        data_recv = None

        event_fix_thread = threading.Thread(target=self.fix_event_loop)
        event_fix_thread.start()

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