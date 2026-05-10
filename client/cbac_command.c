
// cbac_command.c
// Code for the command cbac for the terminal


#include "cbac_client/cbac_client.h"

#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <unistd.h>
#include <stdarg.h>
#include <string.h>
#include <sys/types.h>
#include <sys/socket.h>
#include <sys/un.h>



void print_help() {
    
}



int main(int argc, char *argv[]) {

    struct cbac_packet_t data_recv;

    int code;
    const char *message = NULL;
    char buffer[CBAC_MSG_SIZE];



    if (argc == 2) {

        if (strcmp(argv[1], "help")) {
            print_help();
            return 0;
        }

    }
    else if (argc == 3) {

        if (strcmp(argv[1], "adduser")) {
            if (getuid() != 0) {
                CBAC_WARN("Error: Permission denied\n");
                return 0;
            }

            code = CBAC_ADD_USER;
            cbac_send_and_recv(code, argv[2], &data_recv);

            if (data_recv.code == CBAC_USER_CREATED) {
                CBAC_OKAY("User created in calendar with address: %s", data_recv.message);
            }
            else {
                CBAC_WARN("ERROR: %s", data_recv.message);
            }
            
        }
        else if (strcmp(argv[1], "deluser")) {
            if (getuid() != 0) {
                CBAC_WARN("Error: Permission denied\n");
                return 0;
            }

            code = CBAC_DEL_USER;
            cbac_send_and_recv(code, argv[2], &data_recv);

            if (data_recv.code == CBAC_USER_DELETED) {
                CBAC_OKAY("User deleted in calendar with address: %s", data_recv.message);
            }
            else {
                CBAC_WARN("ERROR: %s", data_recv.message);
            }
        
        }
        else if (strcmp(argv[1], "delreserv")) {
        
        
        }
        else if (strcmp(argv[1], "extend")) {
        
        
        }

    }
    else if (argc == 4) {

        if (strcmp(argv[1], "config")) {
            code = CBAC_UPDATE_CONF;
            
            if (getuid() != 0) {
                CBAC_WARN("Error: Permission denied\n");
                return 0;
            }

        
        
        }
        else if (strcmp(argv[1], "addreserv")) {
            code = CBAC_MAKE_RESERV;
            
            

        }

    }
    else {

        print_help();
        return 0;

    }

    return 0;
}