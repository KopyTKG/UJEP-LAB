package file

import (
	"nebula_cluster/log"
	"os"
)

func Write(file string, data string) {
	err := os.WriteFile(file, []byte(data), 0644)
	if err != nil {
		log.Err("Cannot create file " + file)
		return
	}
	log.Info("Success")
	return
}
