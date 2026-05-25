
// cbac_command.c
// Code for the command cbac for the terminal


#include "cbac_client/cbac_client.h"

#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <unistd.h>
#include <stdarg.h>
#include <string.h>
#include <pwd.h>
#include <sys/types.h>
#include <sys/socket.h>
#include <sys/un.h>



void print_help() {
    printf("Console tool for different options for the CBAC service.\n\n");
    printf("Usage: cbac <command> <arguments>\n\n");
    printf("Commands:\n");
    printf("\thelp     \t\tPrint help message\n");
    printf("\tadduser  \t\tAdds user email to the shared calendar, argument must be the email address of the user. Requires root.\n");
    printf("\tdeluser  \t\tRemoves user email from the shared calendar, argument must be the email address of the user. Requires root.\n");
    printf("\taddreserv\t\tAdds a reservation to the calendar, arguments must be set to \n");
    printf("\tdelreserv\t\tDeletes a reservation in the calendar, argument must be set to timestamp interesecting with the reservation\n");
    printf("\textend   \t\tExtends the current reservation being used, argument must be set to the number of minutes to extend\n");
    printf("\tconfig   \t\tChanges configuration file of the daemon, arguments must be set to the field to change and the new value separated by a space. Requires root.\n\n");
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
            code = CBAC_EXTEND_RESERV;

            uid_t uid = getuid();
            struct passwd *pw = getpwuid(uid);
            char msg[CBAC_MSG_SIZE];

            if (pw != NULL) {
                snprintf(msg, sizeof(msg), "%s %s", pw->pw_name, argv[2]);
            }
            else {
                CBAC_WARN("Error: Wasn't able to extract username");
                return 0;
            }

            cbac_send_and_recv(code, msg, &data_recv);

            if (data_recv.code == CBAC_OK) {
                CBAC_OKAY("Reserv extended");
            }
            else {
                CBAC_WARN("Error: %s", data_recv.message);
            }
        
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