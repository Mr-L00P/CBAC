
// cbac_client.h 
// Definitions and declarations for CBAC


#ifndef PAM_CBAC_AUX_H
#define PAM_CBAC_AUX_H

#include <stdint.h>
#include <sys/un.h>
#include <security/pam_appl.h>
#include <security/pam_modules.h>


// Settings
#define CBAC_MSG_SIZE 128
#define SOCKET_PATH "/run/cbacd/cbac.sock"


// Packet structure
struct pam_cbac_packet_t {
    int32_t code;
    char message[CBAC_MSG_SIZE];
};


// Message codes
#define CBAC_CHECK_SUCCESS  0  // User exists and has a reservation                      Message set to end of reservation time
#define CBAC_USER_CREATED   1  // User has been created correctly                        Message set to user's email address
#define CBAC_USER_DELETED   2  // User has been deleted correctly                        Message empty
#define CBAC_RESERV_CREATED 3  // Reservation has been created for user                  Message set to user, when, time interval, separated by spaces
#define CBAC_WRONG_USER     4  // No reservation, occupied space                         Message empty
#define CBAC_EMPTY_SPACE    5  // No reservation but empty space                         Message empty
#define CBAC_API_ERROR      6  // Daemon couldn't process request with Google API        Message set to origin of the error
#define CBAC_PARAM_ERROR    7  // Params given to daemon not valid                       Message set to origin of the error
#define CBAC_OCCUPIED       8  // Time supplied overlaps with event in the calendar      Message informative

#define CBAC_CHECK_RESERV   10 // Asks daemon to check if user can go through.           Message set to username to check
#define CBAC_MAKE_RESERV    11 // Asks daemon to make a reservation from now             Message set to time interval desired
#define CBAC_ADD_USER       12 // Asks daemon to add user to the calendar of the system  Message set to user's email address
#define CBAC_DEL_USER       13 // Asks daemon to delete user from the calendar           Message set to user's email address


// Info conv macros for PAM
#define CBAC_OKAY(pamh, msg, ...) pam_info(pamh, "\n[+] - " msg "\n", ##__VA_ARGS__)
#define CBAC_INFO(pamh, msg, ...) pam_info(pamh, "\n[*] - " msg "\n", ##__VA_ARGS__)
#define CBAC_WARN(pamh, msg, ...) pam_info(pamh, "\n[-] - " msg "\n", ##__VA_ARGS__)


// CBAC Packet struct functions
int cbac_connect(int sockfd, struct sockaddr_un *addr);
int cbac_create_packet(struct pam_cbac_packet_t *packet, int code, const char *message);
int cbac_send_packet(int sockfd, const struct pam_cbac_packet_t *packet);
int cbac_recv_packet(int sockfd, struct pam_cbac_packet_t *packet);


#endif
