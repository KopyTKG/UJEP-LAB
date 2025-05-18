package nebula

import (
	"fmt"
	"nebula_cluster/log"
	"nebula_cluster/password"
	"os"
	"os/user"
	"regexp"
	"strconv"
)

func Init() {
	//setupDB()
	flow_gate()
	setupUser()
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

func flow_gate() {
	files := []string{"/etc/one/oneflow-server.conf", "/etc/one/onegate-server.conf"}

	for _, file := range files {
		log.Info("Editing " + file)

		contentBytes, err := os.ReadFile(file)
		if err != nil {
			log.Err(err.Error())
			return
		}
		content := string(contentBytes)

		re := regexp.MustCompile(`:host:\s*\w*(.\w*){3}`)

		newBlock := `:host: 0.0.0.0`

		updated := re.ReplaceAllString(content, newBlock)
		err = os.WriteFile(file, []byte(updated), 0644)
		if err != nil {
			log.Err(err.Error())
			return
		}
		log.Success("Success")

	}

	contentBytes, err := os.ReadFile("/etc/one/oned.conf")
	if err != nil {
		log.Err(err.Error())
		return
	}
	content := string(contentBytes)

	re := regexp.MustCompile(`(#?)ONEGATE_ENDPOINT\s*=\s*"http://[^:"]+:5030"`)
	updated := re.ReplaceAllString(content, `ONEGATE_ENDPOINT="http://controller:5030"`)
	log.Debug("A")

	err = os.WriteFile("/etc/one/oned.conf", []byte(updated), 0644)
	if err != nil {
		log.Err(err.Error())
		return
	}
	log.Success("Success")

}

func setupUser() {
	userpass := password.Generate(5)

	log.Info("Writing oneadmin password ")
	err := os.WriteFile("/var/lib/one/.one/one_auth", []byte("oneadmin:"+userpass), 0600)
	if err != nil {
		log.Err("Cannot create file ")
		return
	}
	log.Success("Success")
	password.Creds["oneadmin"] = userpass

	log.Info("Changing owner of file")
	u, _ := user.Lookup("oneadmin")
	uid, _ := strconv.Atoi(u.Uid)
	gid, _ := strconv.Atoi(u.Gid)
	os.Chown("/var/lib/one/.one/one_auth", uid, gid)

	return
}
