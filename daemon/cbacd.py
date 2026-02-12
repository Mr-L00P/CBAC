#!/usr/bin/python3
import time
import os
import socket
import signal
import sys
import configparser
from daemon import runner

SOCKET_PATH = "/run/cbac.sock"

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

        # init google auth
    
    def ask_google(self):
        pass

    def run(self):

        while True:
            time.sleep(5)

cbac = CBAC()
# daemon_runner = runner.DaemonRunner(cbac)
# daemon_runner.do_action()