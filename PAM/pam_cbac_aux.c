#include "include/pam_cbac_aux.h"

#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
#include <pwd.h>
#include <grp.h>
#include <string.h>
#include <sys/types.h>
#include <sys/socket.h>
#include <sys/un.h>
#include <security/pam_appl.h>
#include <security/pam_modules.h>

int cbac_create_packet(struct pam_cbac_packet_t *packet, int code, const char *message) {
    return 0;
}

int cbac_send_packet(int sockfd, const struct pam_cbac_packet_t *packet) {
    return 0;
}

int cbac_recv_packet(int sockfd, struct pam_cbac_packet_t *packet) {
    return 0;
}

int cbac_clean_packet(struct pam_cbac_packet_t *packet) {
    return 0;
}

int cbac_info(const char *message) {
    return 0;
}