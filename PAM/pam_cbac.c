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

#include "include/pam_cbac_aux.h"

typedef struct cbac_message {
    int code;
    char message[64];
};

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
        // pam_error(pamh, "Error de usuario\n");
        return PAM_SYSTEM_ERR;
    }
    getgrouplist(user, pw->pw_gid, NULL, &ngroups);

    gid_t *grupos = malloc(ngroups * sizeof(gid_t));
    if (!grupos) {
        // pam_error(pamh, "Error de memoria\n");
        return PAM_SYSTEM_ERR;
    }

    getgrouplist(user, pw->pw_gid, grupos, &ngroups);

    for (int i = 0; i < ngroups; i++) {
        if (grupos[i] == gr->gr_gid) {
            // pam_info(pamh, "Autenticado como técnico\n");
            return PAM_SUCCESS;
        }
    }
    


    // Conexión a socket, request y respuesta

    int sock;
    struct sockaddr_un addr;
    ssize_t n;
    struct cbac_message msg;
    

    sock = socket(AF_UNIX, SOCK_SEQPACKET, 0);
    if (sock < 0) {
        return PAM_SYSTEM_ERR;
    }

    if (cbac_connect(sock, &addr) < 0) {
        close(sock);
        return PAM_SYSTEM_ERR;
    }


    if (send(sock, &msg, sizeof(struct cbac_message), 0) < 0) {
        close(sock);
        return PAM_SYSTEM_ERR;
    }

    close(sock);

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
