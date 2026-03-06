
// pam_cbac_func.h 
// Definitions and declarations for CBAC

// TODO: Definir el resto de códigos de mensaje, mensajes enviados por PAM
//       IMPORTANTE: También definir en cbacd.py


#ifndef PAM_CBAC_AUX_H
#define PAM_CBAC_AUX_H

#include <stdint.h>
#include <sys/un.h>
#include <security/pam_appl.h>
#include <security/pam_modules.h>

// Settings
#define PAM_CBAC_MSG_SIZE 64
#define SOCKET_PATH "/run/cbac.sock"

// Packet structure
struct pam_cbac_packet_t {
    int32_t code;
    char message[PAM_CBAC_MSG_SIZE];
};


// Message codes
#define CBAC_SUCCESS       0  // User exists and has a reservation
#define CBAC_WRONG_USER    1  // No reservation, occupied space
#define CBAC_EMPTY_SPACE   2  // No reservation but empty space
#define CBAC_DAEMON_ERROR  3  // Daemon couldn't process request with Google API

#define CBAC_CHECK_RESERV  10 // Asks daemon to check if user can go through. Message set to username to check
#define CBAC_MAKE_RESERV   11 // Asks daemon to make a reservation from now   Message set to time interval desired
#define CBAC_ADD_USER      12 // Asks daemon to add user to the calendar of the system



// Info conv macros
#define CBAC_OKAY(pamh, msg, ...) pam_info(pamh, "[+] - " msg "\n", ##__VA_ARGS__)
#define CBAC_INFO(pamh, msg, ...) pam_info(pamh, "[*] - " msg "\n", ##__VA_ARGS__)
#define CBAC_WARN(pamh, msg, ...) pam_info(pamh, "[-] - " msg "\n", ##__VA_ARGS__)

// CBAC Packet struct functions
int cbac_connect(int sockfd, struct sockaddr_un *addr);
int cbac_create_packet(struct pam_cbac_packet_t *packet, int code, const char *message);
int cbac_send_packet(int sockfd, const struct pam_cbac_packet_t *packet);
int cbac_recv_packet(int sockfd, struct pam_cbac_packet_t *packet);

#endif
