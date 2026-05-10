
// cbac_client.c
// Implementation of auxiliary functions for CBAC


#include "cbac_client.h"

#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <unistd.h>
#include <stdarg.h>
#include <pwd.h>
#include <grp.h>
#include <arpa/inet.h>
#include <string.h>
#include <sys/types.h>
#include <sys/socket.h>
#include <sys/un.h>
#include <security/pam_appl.h>
#include <security/pam_modules.h>


int cbac_socket() {
    return socket(AF_UNIX, SOCK_SEQPACKET, 0);
}

int cbac_connect(int sockfd, struct sockaddr_un *addr) {
    memset(addr, 0, sizeof(struct sockaddr_un));
    addr->sun_family = AF_UNIX;
    strncpy(addr->sun_path, SOCKET_PATH, sizeof(addr->sun_path) -1);

    if (connect(sockfd, (struct sockaddr *) addr, sizeof(struct sockaddr_un)) < 0) return -1;

    return 0;
}

int cbac_create_packet(struct cbac_packet_t *packet, int code, const char *message) {
    packet->code = htonl(code);
    memset(packet->message, 0, CBAC_MSG_SIZE);
    snprintf(packet->message, CBAC_MSG_SIZE, "%s", message);
    if (packet->message == NULL) {
        packet->message[0] = '\0';
        return -1;
    }
    return 0;
}

int cbac_send_packet(int sockfd, const struct cbac_packet_t *packet) {

    if (send(sockfd, packet, sizeof(struct cbac_packet_t), 0) < 0) {
        return -1;
    }
    return 0;
}

int cbac_recv_packet(int sockfd, struct cbac_packet_t *packet) {
    if (recv(sockfd, packet, sizeof(*packet), 0) < 0) {
        return -1;
    }
    return 0;
}

int cbac_get_packet_code(struct cbac_packet_t *packet) {
    return packet->code;
}

char *cbac_get_packet_message(struct cbac_packet_t *packet) {
    return packet->message;
}

int cbac_send_and_recv(int code, const char* message, struct cbac_packet_t *recv_packet) {
    int sockfd = cbac_socket();
    struct cbac_packet_t send_packet;
    CBAC_SOCKADDR addr;

    cbac_create_packet(&send_packet, code, message);

    if (cbac_connect(sockfd, &addr) < 0) {
        close(sockfd);
        return -1;
    }

    if (cbac_send_packet(sockfd, &send_packet) < 0) {
        close(sockfd);
        return -1;
    }

    if (cbac_recv_packet(sockfd, recv_packet) < 0) {
        close(sockfd);
        return -1;
    }

    recv_packet->code = ntohl(recv_packet->code);

    return 0;

}