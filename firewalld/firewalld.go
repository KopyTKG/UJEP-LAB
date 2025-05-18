package firewalld

import (
	"nebula_cluster/log"
	"os/exec"
	"strings"
)

type Port string

func Add(p Port) {
	log.Info("Openning port " + string(p))
	cmd := exec.Command("firewall-cmd", "--add-port="+string(p))
	output, err := cmd.CombinedOutput()
	split := strings.Split(string(output), "\n")
	if err != nil {
		log.Err(split[0])
		return
	}
	if len(split) > 2 {
		log.SYSWarn(split[0])
		return
	}
	log.Success(split[0])
	return
}

func AddPerma(p Port) {
	log.Info("Openning permanent port " + string(p))
	cmd := exec.Command("firewall-cmd", "--add-port="+string(p), "--permanent")
	output, err := cmd.CombinedOutput()
	split := strings.Split(string(output), "\n")
	if err != nil {
		log.Err(split[0])
		return
	}
	if len(split) > 2 {
		log.SYSWarn(split[0])
		return
	}
	log.Success(split[0])
	return
}

func Reload() {
	log.Info("Reloading firewalld rules")
	cmd := exec.Command("firewall-cmd", "--reload")
	output, err := cmd.CombinedOutput()
	split := strings.Split(string(output), "\n")
	if err != nil {
		log.Err(split[0])
		return
	}
	log.Success(split[0])
	return
}
