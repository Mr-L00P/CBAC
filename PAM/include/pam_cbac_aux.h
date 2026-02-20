#ifndef PAM_CBAC_AUX_H
#define PAM_CBAC_AUX_H

#include <stdint.h>

#define PAM_CBAC_MSG_SIZE 32

struct pam_proto_msg {
    int32_t codigo;
    char mensaje[PAM_CBAC_MSG_SIZE];
};


#endif