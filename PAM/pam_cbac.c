#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/socket.h>
#include <sys/un.h>
#include <security/pam_appl.h>
#include <security/pam_modules.h>

#define  SOCKET_PATH "/run/cbac.sock"

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
    int ngrupos = 0;
    pam_get_item(pamh, PAM_USER, (const void **)&user);

    const char *group_excep = "tecnicos";

    struct group *gr getgrnam(group_excep);
    struct passwd *pw = getpwnam(user);
    if (gr == NULL || pw == NULL) {
        pam_error(pamh, "Error de usuario\n");
        return PAM_SYSTEM_ERR
    }
    getgrouplist(user, pw->pw_gid, NULL, &ngroups);

    gid_t *grupos = malloc(ngrupos * sizeof(gid_t));
    if (!grupos) {
        pam_error(pamh, "Error de memoria\n");
        return PAM_SYSTEM_ERR;
    }

    getgrouplist(user, pw->pw_gid, grupos, &ngrupos);

    for (int i = 0; i < ngrupos; i++) {
        if (grupos[i] == gr->gr_id) {
            pam_info(pamh, "Autenticado como técnico\n");
            return PAM_SUCCESS;
        }
    }
    


    // Conexión a socket, request y respuesta

    int sock;
    struct sockaddr_un addr;
    ssize_t n;

    sock = socket(AF_UNIX, SOCK_SEQPACKET, 0);
    if (sock < 0) {
        return PAM_SYSTEM_ERR;
    }

    memset(&addr, 0, sizeof(addr));
    addr.sun_family = AF_UNIX;
    strncopy(addr.sun_path, SOCKET_PATH, sizeof(addr.sun_path) - 1);

    if (connect(sock, (struct sockaddr *)&addr, sizeof(addr)) < 0) {
        close(sock);
        return PAM_SYSTEM_ERR;
    }

    if (send(sock, mensaje, strlen(mensaje), 0) < 0) {
        close(sock);
        return PAM_SYSTEM_ERR;
    }

    n = recv(sock, respuesta, resp_size - 1, 0);
    if (n < 0) {
        close(sock);
        return PAM_SYSTEM_ERR;
    }

    close(sock);



    return PAM_AUTH_ERR;
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
