
// pam_cbac.c
// PAM module implementation for CBAC 


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
#include <time.h>

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
            CBAC_OKAY(pamh, "Authenticated as administrator.");
            return PAM_SUCCESS;
        }
    }


    // Conexión a socket, request y respuesta

    int sock;
    struct sockaddr_un addr;
    struct pam_cbac_packet_t data_send;
    struct pam_cbac_packet_t data_recv;

    cbac_create_packet(&data_send, CBAC_CHECK_RESERV, user);

    sock = socket(AF_UNIX, SOCK_SEQPACKET, 0);
    if (sock < 0) {
        return PAM_SYSTEM_ERR;
    }

    if (cbac_connect(sock, &addr) < 0) {
        close(sock);
        return PAM_SYSTEM_ERR;
    }

    if (cbac_send_packet(sock, &data_send) < 0) {
        close(sock);
        return PAM_SYSTEM_ERR;
    }

    if (cbac_recv_packet(sock, &data_recv) < 0) {
        close(sock);
        return PAM_SYSTEM_ERR;
    }

    data_recv.code = ntohl(data_recv.code);

    switch(data_recv.code) {
    
    case CBAC_CHECK_RESERV:
        CBAC_OKAY(pamh, "Reservation verified, authenticated as %s", user);
        return PAM_SUCCESS;
        break;
    case CBAC_EMPTY_SPACE:
        CBAC_INFO(pamh, "User doesn't have a reservation but no one else is using the server");

        char *response = NULL;

        if (pam_prompt(pamh, PAM_PROMPT_ECHO_ON, &response, "Do you wish to make a reservation for now? yes/(no): ") != PAM_SUCCESS) {
            CBAC_WARN(pamh, "Error with prompt");
            return PAM_SYSTEM_ERR;
        }

        if (strcmp(response, "yes") == 0) {
            free(response);
            response = NULL;
            char msg[PAM_CBAC_MSG_SIZE];
            int minutes;

            if (pam_prompt(pamh, PAM_PROMPT_ECHO_ON, &response, "Input the number of minutes you want for your reservation: ") != PAM_SUCCESS) {
                CBAC_WARN(pamh, "Error with prompt");
                return PAM_SYSTEM_ERR;
            }

            if (atoi(response) == 0) {
                CBAC_WARN(pamh, "No minutes supplied, exiting...");
                return PAM_AUTH_ERR;
            }

            minutes = atoi(response);
            free(response);

            // Get local time to solicit reservation to daemon
            time_t now = time(NULL);
            struct tm *tm_info = localtime(&now);
            char now_dt[32];
            strftime(now_dt, sizeof(now_dt), "%Y-%m-%dT%H:%M:%SZ", tm_info);
            snprintf(msg, 128, "%s %s %d", user, now_dt, minutes);

            cbac_create_packet(&data_send, CBAC_MAKE_RESERV, msg);

            if (cbac_send_packet(sock, &data_send) < 0) {
                close(sock);
                return PAM_SYSTEM_ERR;
            }

            if (cbac_recv_packet(sock, &data_recv) < 0) {
                close(sock);
                return PAM_SYSTEM_ERR;
            }

            data_recv.code = ntohl(data_recv.code);
        
            if (data_recv.code == CBAC_RESERV_CREATED) {
                close(sock);
                CBAC_OKAY(pamh, "Reservation created for user %s for %d minutes", user, minutes);
                return PAM_SUCCESS;
            }
            else {
                close(sock);
                CBAC_WARN(pamh, "Error, daemon returned: %s", data_recv.message);
                return PAM_AUTH_ERR;
            }   
        }
        else {
            close(sock);
            CBAC_INFO(pamh, "No reservation created, exiting...");
            return PAM_AUTH_ERR;
        }

        break;
    case CBAC_WRONG_USER:
        CBAC_WARN(pamh, "Space occupied by another user");
        return PAM_AUTH_ERR;
        break;
    case CBAC_API_ERROR:
        CBAC_WARN(pamh, "Daemon error");
        return PAM_SYSTEM_ERR;
        break;
    default:
        return PAM_SYSTEM_ERR;
        break;

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
