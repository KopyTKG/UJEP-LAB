package perms

import (
	"nebula_cluster/log"
	"os"
)

func RootCheck() {
	if os.Geteuid() != 0 {
		log.Err("Root permissions are needed for this program")
		os.Exit(1)
	}
}
