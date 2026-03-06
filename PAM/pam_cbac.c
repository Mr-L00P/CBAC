
// pam_cbac.c
// PAM module implementation for CBAC 

// TODO: Tratar respuesta para distintos modos 
// TODO: Crear paquete de acuerdo con lo requerido


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
#include <security/pam_ext.h>
#include <arpa/inet.h>

#include "include/pam_cbac_func.h"


PAM_EXTERN int
pam_sm_authenticate(pam_handle_t *pamh, int flags,
    int argc, const char *argv[])
{

    return PAM_SUCCESS;
}

PAM_EXTERN int
pam_sm_setcred(pam_handle_t *pamh, int flags,
    int argc, const char *argv[])
{

    return PAM_SUCCESS;
}

PAM_EXTERN int
pam_sm_acct_mgmt(pam_handle_t *pamh, int flags,
    int argc, const char *argv[])
{

    // Dejar pasar a un grupo en específico

    const char *user = NULL;
    int ngroups = 0;
    pam_get_item(pamh, PAM_USER, (const void **)&user);

    const char *group_excep = "tecnicos";

    struct group *gr = getgrnam(group_excep);
    struct passwd *pw = getpwnam(user);
    if (gr == NULL || pw == NULL) {
        return PAM_SYSTEM_ERR;
    }
    getgrouplist(user, pw->pw_gid, NULL, &ngroups);

    gid_t *grupos = malloc(ngroups * sizeof(gid_t));
    if (!grupos) {
        return PAM_SYSTEM_ERR;
    }

    getgrouplist(user, pw->pw_gid, grupos, &ngroups);

    for (int i = 0; i < ngroups; i++) {
        if (grupos[i] == gr->gr_gid) {
            CBAC_OKAY(pamh, "Autenticado como técnico");
            return PAM_SUCCESS;
        }
    }

    CBAC_INFO(pamh, "No es técnico, verificando reserva...");
    


    // Conexión a socket, request y respuesta

    int sock;
    struct sockaddr_un addr;
    struct pam_cbac_packet_t msg_send;
    struct pam_cbac_packet_t msg_recv;

    cbac_create_packet(&msg_send, 17, user);

    sock = socket(AF_UNIX, SOCK_SEQPACKET, 0);
    if (sock < 0) {
        return PAM_SYSTEM_ERR;
    }

    if (cbac_connect(sock, &addr) < 0) {
        close(sock);
        return PAM_SYSTEM_ERR;
    }

    if (cbac_send_packet(sock, &msg_send) < 0) {
        close(sock);
        return PAM_SYSTEM_ERR;
    }

    if (cbac_recv_packet(sock, &msg_recv) < 0) {
        close(sock);
        return PAM_SYSTEM_ERR;
    }

    msg_recv.code = ntohl(msg_recv.code);

    if (msg_recv.code != CBAC_SUCCESS) {
        close(sock);
        return PAM_AUTH_ERR;
    }

    close(sock);
    CBAC_OKAY(pamh, "Reserva confirmada, autenticado como usuario %s", user);
    return PAM_SUCCESS;
}

PAM_EXTERN int
pam_sm_open_session(pam_handle_t *pamh, int flags,
    int argc, const char *argv[])
{

    return PAM_SUCCESS;
}

PAM_EXTERN int
pam_sm_close_session(pam_handle_t *pamh, int flags,
    int argc, const char *argv[])
{

    return PAM_SUCCESS;
}

PAM_EXTERN int
pam_sm_chauthtok(pam_handle_t *pamh, int flags,
    int argc, const char *argv[])
{

    return PAM_SERVICE_ERR;
}
