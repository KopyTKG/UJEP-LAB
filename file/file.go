package file

import (
	"nebula_cluster/log"
	"os"
)

func Write(file string, data string) {
	log.Info("Writing file " + file)
	err := os.WriteFile(file, []byte(data), 0644)
	if err != nil {
		log.Err("Cannot create file " + file)
		return
	}
	log.Success("Success")
	return
}
