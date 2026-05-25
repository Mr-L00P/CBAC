
# cbacd.py
# Daemon for CBAC

# TODO: Función que arregla formato del calendario, log de quien crea eventos sin formato
# TODO: Handler de sesiones nuevo
# TODO: Revisar función de formato, dos casos, ALLOW_INTERSECT por separado? 
#       PRIMERO ELIMINA POR TIEMPO Y DESPUES INTERVALO DE MIN MINUTOS PARA INTERSECT 
# TODO: Extender sesión


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
import pwd
import grp
from datetime import datetime, timezone, timedelta
from dateutil import parser
from zoneinfo import ZoneInfo

from google.oauth2 import service_account
from googleapiclient.discovery import build
from dotenv import load_dotenv
load_dotenv("/etc/cbac/config")


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
CBAC_RESERV_DELETED = 5  # Reservation has been deleted                               Message empty
CBAC_WRONG_USER     = 6  # No reservation, occupied space                             Message empty
CBAC_EMPTY_SPACE    = 7  # No reservation but empty space                             Message empty
CBAC_API_ERROR      = 8  # Daemon couldn't process request with Google API            Message set to origin of the error
CBAC_PARAM_ERROR    = 9  # Params given to daemon not valid                           Message set to origin of the error
CBAC_OCCUPIED       = 10 # Time supplied overlaps with event in the calendar          Message informative

# Packet request codes
CBAC_CHECK_RESERV   = 11 # Asks daemon to check if user can go through.               Message set to username to check
CBAC_MAKE_RESERV    = 12 # Asks daemon to make a reservation from now                 Message set to user, when, time interval, separated by spaces
CBAC_DEL_RESERV     = 13 # Asks daemon to delete a certain event                      Message set to timestamp intersecting with the event
CBAC_ADD_USER       = 14 # Asks daemon to add user to the calendar of the system.     Message set to user's email address and role, separated by space
CBAC_DEL_USER       = 15 # Asks daemon to delete user from the calendar               Message set to user's email address
CBAC_UPDATE_CONF    = 16 # Asks daemon to update env variables                        Message empty
CBAC_EXTEND_RESERV  = 17 # Asks daemon to extend the current reservation              Message set to user and minutes to extend


SCOPES=["https://www.googleapis.com/auth/calendar"]
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
        os.chmod(SOCKET_PATH, 0o777)
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
            if cal["summary"] == os.getenv("CALENDAR_NAME"):
                CALENDAR_ID = cal["id"]
                return CALENDAR_ID
            
        calendar = {
            "summary": os.getenv("CALENDAR_NAME"),
            "timeZone": os.getenv("TIMEZONE")
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
                
            start_dt = self.parse_timestamp(start_str)
            end_dt = self.parse_timestamp(end_str)

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
    def fix_events_by_time(self, when_dt: datetime):
        calendar_id = self.get_or_create_calendar()
        event_list = self.get_events(when_dt, offset=120)

        unformatted_event_set = set()

        for event in event_list:
            start_dt = self.parse_timestamp(event["startime"].get("dateTime"))
            end_dt = self.parse_timestamp(event["end".get("dateTime")])

            if (end_dt - start_dt) > timedelta(minutes=int(os.getenv("MAX_RESERV_MINUTES"))) or (end_dt - start_dt) < timedelta(minutes=int(os.getenv("MIN_RESERV_MINUTES"))):
                unformatted_event_set.add(event["id"])

        for event in unformatted_event_set:
            self.service.events().delete(
                calendarId = calendar_id,
                eventId = event["id"]
            ).execute()



    # Function to delete the events that intersect with another that was created earlier
    def fix_events_by_intersect(self, when_dt: datetime):
        calendar_id = self.get_or_create_calendar()
        event_list = self.get_events(when_dt, offset=0)

        first_event_id = None
        first_event_dt = None

        for event in event_list:
            curr_event_dt = self.parse_timestamp(event["created"])
            if (first_event_id is None or curr_event_dt < first_event_id):
                first_event_id = event["id"]
                first_event_dt = self.parse_timestamp(event["created"])

        for event in event_list:
            if (event["id"] != first_event_id):
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

            try:
                insert = self.service.events().insert(
                    calendarId = calendar_id,
                    body=event
                ).execute()

                return self.create_packet(CBAC_RESERV_CREATED, "")
            except Exception as e:
                return self.create_packet(CBAC_API_ERROR, "Couldn't make reservation")
        else:
            return self.create_packet(CBAC_OCCUPIED, "Time occupied on calendar")



    # Attempts to delete an event from the calendar with a given time
    def del_reserv(self, when: str):
        calendar_id = self.get_or_create_calendar()
        when_dt = self.parse_timestamp(when)
        events = self.get_events(when_dt, 0)

        if not events:
            return self.create_packet(CBAC_PARAM_ERROR, "No event in timestamp given")
        
        try:
            for event in events:
                self.service.events().delete(
                    calendarId=calendar_id,
                    eventId = event["id"]
                ).execute()

            return self.create_packet(CBAC_RESERV_DELETED, "")
        except Exception as e:
            return self.create_packet(CBAC_API_ERROR, "Couldn't delete reservation") 



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

        try:
            created_rule = self.service.acl().insert(calendarId=calendar_id, body=rule).execute()
            return self.create_packet(CBAC_USER_CREATED, user_email)
        except Exception as e:
            return self.create_packet(CBAC_API_ERROR, "Couldn't add user to calendar")
        


    # Function to delete user from calendar
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
        now_dt = datetime.now()
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
    


    def extend_reserv(self, user: str, minutes: str):
        if int(minutes) > int(os.getenv("MAX_RESERV_MINUTES")) or int(minutes) < int(os.getenv("MIN_RESERV_MINUTES")):
            return self.create_packet(CBAC_PARAM_ERROR, "Requested more than the max time")

        calendar_id = self.get_or_create_calendar()

        now_dt = datetime.now()
        now = datetime.isoformat(now_dt)
        end_dt = now_dt + timedelta(minutes=int(minutes))
        end = datetime.isoformat(end_dt)

        curr_events = self.get_events(now_dt, 0)
        found = False

        for event in curr_events:
            if event["summary"] == user:
                event["start"]["datetime"] = now
                event["end"]["datetime"] = end

                self.service.events().update(
                    calendarId=calendar_id,
                    eventId=event["id"],
                    body=event
                ).execute()

                found = True

        if found:
            return self.create_packet(CBAC_OK, "")
        else:
            return self.create_packet(CBAC_API_ERROR, "No event for user found")


    # Updates env variables when asked by client
    def update_conf(self) -> struct:
        load_dotenv("/etc/cbac/config", override=True)
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
        elif code_recv == CBAC_UPDATE_CONF:
            data_send = self.update_conf()
        elif code_recv == CBAC_EXTEND_RESERV:
            user, time = message_recv.split()
            data_send = self.extend_reserv(user, time)

        return data_send



    def parse_timestamp(self, when: str):
        dt = parser.parse(when)
        return dt



    # Sends message to the client through the terminal they're connected to via SSH, additionally you can add a type to make the message informative, a confirmation
    # or an error, used for direct communication with client without requiring an initial connection from the client
    def message_sessions(self,user: str, message: str, type=None):
        if type == i:
            message = f"[*] - USER: {user}  - " + message
        elif type == k:
            message = f"[+] - USER: {user}  - " + message
        elif type == e:
            message = f"[-] - USER: {user}  - " + message
        
        try:
            subprocess.run(["sudo", "wall", message])
        except:
            pass


    
    # Thread for fixing events every EVENT_FIX_MINUTES time, defined in .env
    def fix_event_loop(self):
        secs = int(os.getenv("EVENT_FIX_MINUTES")) * 60
        now_dt = datetime.now() 
        while(True):
            self.fix_events_by_time(now_dt)
            for i in range(10):
                self.fix_events_by_intersect(now_dt + timedelta(minutes=(i * int(os.getenv("MIN_RESERV_MINUTES")))))
            time.sleep(secs)



    # Thread for the current ssh session, informative messages and eventually termination of the process
    def handle_session(self, user: str, time_left: timedelta):

        while True:
            command_output = subprocess.check_output(["sudo", "loginclt", "list-sessions"]).decode()
            session_list = []
            user_list = []

            for line in command_output.splitlines()[1:]:
                info = line.split()
                if len(info) >= 3:
                    session_list.append(info[0])
                    user_list.append(info[2])

            now_dt = datetime.now()
            events = self.get_events(now_dt, 0)

            
            for i in range(len(session_list)):

                user_info = pwd.getpwnam(user)
                primary_gid = user_info.pw_gid

                if not any(
                            g.gr_name == os.getenv("FULL_ACCESS_GROUP") and (user in g.gr_mem or g.gr_gid == primary_gid)
                            for g in grp.getgrall()
                    ):
                    user_permission = False
                    users_event = None
                    for event in events:
                        if user_list[i] == event["summary"]:
                            users_event = event
                            user_permission = True
                    if not user_permission:
                        self.message_sessions(user_list[i], "Reservation ended, terminating session in 10 seconds...", i)
                        time.sleep(10)
                        subprocess.run(["sudo", "loginctl", "kill-session", session_list[i]])
                    else:
                        remaining = (self.parse_timestamp(event["end"].get("dateTime")) - now_dt).total_seconds() // 60
                        if remaining < 5:
                            self.message_sessions(user, f"{remaining} minutes left of reservation", i)
            
            time.sleep(60)


    # Main loop

    def run(self):
        data_recv = None

        session_manager_thread = threading.Thread(target=self.handle_session)
        session_manager_thread.start()

        event_fix_thread = threading.Thread(target=self.fix_event_loop)
        event_fix_thread.start()

        while True:
            conn, _ = self.server.accept()
            while True:
                data_recv = conn.recv(PACKET_SIZE)

                if not data_recv:
                    break

                code_recv, message_recv = struct.unpack(f'!i{PACKET_MESSAGE_SIZE}s', data_recv)
                message_recv = message_recv.rstrip(b'\x00').decode('utf-8')

                data_send = self.treat_packet(data_recv)

                code_send, message_send = struct.unpack(f'!i{PACKET_MESSAGE_SIZE}s', data_send)
                message_send = message_send.rstrip(b'\x00').decode('utf-8')

                conn.sendall(data_send)


if __name__ == "__main__":
    cbac = CBAC()
    cbac.run()