#include "include/pam_cbac_aux.h"

#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
#include <pwd.h>
#include <grp.h>
#include <arpa/inet.h>
#include <string.h>
#include <sys/types.h>
#include <sys/socket.h>
#include <sys/un.h>
#include <security/pam_appl.h>
#include <security/pam_modules.h>

int cbac_connect(int sockfd, struct sockaddr_un *addr) {
    memset(addr, 0, sizeof(struct sockaddr_un));
    addr->sun_family = AF_UNIX;
    strncpy(addr->sun_path, SOCKET_PATH, sizeof(addr->sun_path) -1);

    if (connect(sockfd, (struct sockaddr *) addr, sizeof(struct sockaddr_un)) < 0) return -1;

    return 0;
}

int cbac_create_packet(struct pam_cbac_packet_t *packet, int code, const char *message) {
    packet->code = htonl(code);
    memset(packet->message, 0, PAM_CBAC_MSG_SIZE);
    snprintf(packet->message, PAM_CBAC_MSG_SIZE, "%s", message);
    if (packet->message == NULL) {
        packet->message[0] = '\0';
        return -1;
    }
    return 0;
}

int cbac_send_packet(int sockfd, const struct pam_cbac_packet_t *packet) {
    if (send(sockfd, packet, sizeof(struct pam_cbac_packet_t), 0) < 0) {
        return -1;
    }
    return 0;
}

int cbac_recv_packet(int sockfd, struct pam_cbac_packet_t *packet) {
    if (recv(sockfd, packet, sizeof(*packet), 0) < 0) {
        return -1;
    }
    return 0;
}

int cbac_info(const char *message) {
    return 0;
}