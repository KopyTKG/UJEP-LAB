package systemctl

import (
	"nebula_cluster/log"
	"os/exec"
)

type Daemon string

func Start(s Daemon) {
	log.Info("Starting " + string(s))
	cmd := exec.Command("systemctl", "start", string(s))
	output, err := cmd.CombinedOutput()
	if err != nil {
		log.Err(string(output))
		return
	}
	log.Success("Success")
	return
}

func Enable(s Daemon) {
	log.Info("Enabling " + string(s))
	cmd := exec.Command("systemctl", "enable", string(s))
	output, err := cmd.CombinedOutput()
	if err != nil {
		log.Err(string(output))
		return
	}
	log.Success("Success")
	return
}

func StartNow(s Daemon) {
	log.Info("Starting " + string(s) + " with link")
	cmd := exec.Command("systemctl", "enable", "--now", string(s))
	output, err := cmd.CombinedOutput()
	if err != nil {
		log.Err(string(output))
		return
	}
	log.Success("Success")
	return
}
