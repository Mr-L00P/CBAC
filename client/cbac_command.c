
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


void print_help() {

}


int adduser(const char* user) {

}


int deluser(const char* user) {

}


int addreserv() {

}


int delreserv() {

}


int config() {
    
}


int main(int argc, char *argv[]) {
    
    if (argc < 3) {
        print_help();
    }

    int code;
    char message[CBAC_MSG_SIZE];


    if        (strcmp(argv[2], "help")) {
        print_help();
    } 
    else if (strcmp(argv[2], "adduser")) {

    }
    else if (strcmp(argv[2], "deluser")) {

    }
    else if (strcmp(argv[2], "addreserv")) {

    }
    else if (strcmp(argv[2], "delreserv")) {

    }
    else if (strcmp(argv[2], "config")) {

    }
    else {
        print_help();
    }


    return 0;
}