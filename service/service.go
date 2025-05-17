package service

import (
	"nebula_cluster/log"
	"os/exec"
	"strings"
)

type Daemon string

func Start(s Daemon) {
	cmd := exec.Command("systemctl", "start", string(s))
	output, err := cmd.CombinedOutput()
	if err != nil {
		log.Err(strings.Split(string(output), "\n")[0])
		return
	}
	log.Info("Success")
	return
}

func Enable(s Daemon) {
	cmd := exec.Command("systemctl", "enable", string(s))
	output, err := cmd.CombinedOutput()
	if err != nil {
		log.Err(strings.Split(string(output), "\n")[0])
		return
	}
	log.Info("Success")
	return
}

func StartNow(s Daemon) {
	cmd := exec.Command("systemctl", "enable", "--now", string(s))
	output, err := cmd.CombinedOutput()
	if err != nil {
		log.Err(strings.Split(string(output), "\n")[0])
		return
	}
	log.Info("Success")
	return
}
