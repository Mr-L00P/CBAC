#!/usr/bin/python3
import time
import os
import socket
import struct
import signal
import sys
import configparser

from google.oauth2 import service_account
from googleapiclient.discovery import build


# from daemon import runner

SOCKET_PATH = "/run/cbac.sock"
SIZE = 36 # 4 de codigo + 32 de mensaje

SERVICE_ACCOUNT_CREDS="/etc/cbac/cbac-488510-b501d8e5547f.json"
SCOPES = ["https://www.googleapis.com/auth/calendar"]

class CBAC():
    def __init__(self):
        self.stdin_path = '/dev/null'
        self.stdout_path = '/var/log/cbac.log'
        self.stderr_path = '/var/log/cbac.err'
        self.pidfile_path =  '/tmp/cbacd.pid'
        self.pidfile_timeout = 5

        self.credentials = service_account.Credentials.from_service_account_file(
            SERVICE_ACCOUNT_CREDS,
            scopes=SCOPES
        )

        # init variables with conf file in /etc/cbac/cbac.conf

        # init socket
        if os.path.exists(SOCKET_PATH):
            os.remove(SOCKET_PATH)
        self.server = socket.socket(socket.AF_UNIX, socket.SOCK_SEQPACKET)
        self.server.bind(SOCKET_PATH)
        self.server.listen(1)

        # init google auth 


    def cbac_send():
        pass

    def cbac_recv():
        pass

    
    def ask_google(self):
        pass


    # main loop

    def run(self):
        data = None

        while True:
            print("Inside run loop\n")
            conn, _ = self.server.accept()
            data = conn.recv(36)
            print("Data received\n")

            code, message = struct.unpack('!i32s', data)
            message = message.rstrip(b'\x00').decode('utf-8')

            print(f"Code: {code}")
            print(f"Message: {message}")

            time.sleep(5)

cbac = CBAC()

cbac.run()

# daemon_runner = runner.DaemonRunner(cbac)
# daemon_runner.do_action()