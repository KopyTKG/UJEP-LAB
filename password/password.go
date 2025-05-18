package password

import (
	"crypto/rand"
	"encoding/base64"
	"nebula_cluster/log"
	"os"
)

var Creds map[string]string

func init() {
	Creds = make(map[string]string)
}

func Generate(length int) string {
	log.Info("Generating password")
	bytes := make([]byte, length)
	_, err := rand.Read(bytes)
	if err != nil {
		log.Err("Error while generating password")
		os.Exit(1)
	}
	return base64.URLEncoding.EncodeToString(bytes)[:length]
}

func DumpCreds(filename string) {
	log.Info("Creting password dump file")
	f, err := os.OpenFile(filename, os.O_CREATE|os.O_WRONLY|os.O_TRUNC, 0600)
	if err != nil {
		log.Err(err.Error())
		return
	}
	defer f.Close()
	for user, pass := range Creds {
		_, err := f.WriteString(user + ": " + pass + "\n")
		if err != nil {
			log.Err(err.Error())
			return
		}
	}
	log.Success("Dump created")
}
