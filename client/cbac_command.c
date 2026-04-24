
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

    int sock;
    struct sockaddr_un addr;
    struct cbac_packet_t data_send;
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
            code = CBAC_ADD_USER;

        }
        else if (strcmp(argv[1], "deluser")) {
            code = CBAC_DEL_USER;

        }
        else if (strcmp(argv[1], "addreserv")) {
            code = CBAC_MAKE_RESERV;

        }
        else if (strcmp(argv[1], "delreserv")) {
            code = CBAC_DEL_RESERV;

        }

    }
    else if (argc == 4) {

        if (strcmp(argv[1], "config")) {
            code = CBAC_UPDATE_CONF;
            
        }

    }
    else {

        print_help();
        return 0;

    }


    message = buffer;
    cbac_create_packet(&data_send, code, message);

    sock = socket(AF_UNIX, SOCK_SEQPACKET, 0);
    if (sock < 0) {
        return -1;
    }

    if (cbac_connect(sock, &addr) < 0) {
        close(sock);
        return -1;
    }

    if (cbac_send_packet(sock, &data_send) < 0) {
        close(sock);
        return -1;
    }

    if (cbac_recv_packet(sock, &data_recv) < 0) {
        close(sock);
        return -1;
    }


    return 0;
}