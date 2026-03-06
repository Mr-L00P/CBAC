#ifndef PAM_CBAC_AUX_H
#define PAM_CBAC_AUX_H

#include <stdint.h>

// Settings
#define PAM_CBAC_MSG_SIZE 64
#define SOCKET_PATH "/run/cbac.sock"

// Packet structure
struct pam_cbac_packet_t {
    int32_t code;
    char message[PAM_CBAC_MSG_SIZE];
};


// Message codes
#define CBAC_SUCCESS 0


// CBAC Packet struct functions
int cbac_connect(int sockfd, struct sockaddr_un *addr);
int cbac_create_packet(struct pam_cbac_packet_t *packet, int code, const char *message);
int cbac_send_packet(int sockfd, const struct pam_cbac_packet_t *packet);
int cbac_recv_packet(int sockfd, struct pam_cbac_packet_t *packet);


// Display info to user
int cbac_info(const char *message);


#endif