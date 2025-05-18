package nebula

import (
	"fmt"
	"nebula_cluster/log"
	"nebula_cluster/password"
	"os"
	"regexp"
)

func Init() {
	setupDB()
}

func setupDB() {
	log.Info("Editing oned.conf to use mariadb")
	contentBytes, err := os.ReadFile("/etc/one/oned.conf")
	if err != nil {
		log.Err(err.Error())
		return
	}
	content := string(contentBytes)

	// Regex to match DB = [ ... ] block (non-greedy)
	re := regexp.MustCompile(`(?s)DB\s*=\s*\[.*?\]`)

	newBlock := fmt.Sprintf(`DB = [ BACKEND = "mysql",
       SERVER  = "localhost",
       PORT    = 0,
       USER    = "oneadmin",
       PASSWD  = "%s",
       DB_NAME = "opennebula",
       CONNECTIONS = 25,
       COMPARE_BINARY = "no" ]`, password.Creds["dboneadmin"])

	updated := re.ReplaceAllString(content, newBlock)

	err = os.WriteFile("/etc/one/oned.conf", []byte(updated), 0644)
	if err != nil {
		log.Err(err.Error())
		return
	}
	log.Success("Success")
	return
}
