package dnf

import (
	"nebula_cluster/log"
	"os/exec"
	"strings"
)

type Package string
type Repo string

func Install(pkg Package) {
	yesCmd := exec.Command("yes")
	dnfCmd := exec.Command("dnf", "install", "-y", string(pkg))

	pipe, err := yesCmd.StdoutPipe()
	if err != nil {
		log.Err("Failed to create pipe for yes command")
		return
	}
	dnfCmd.Stdin = pipe

	if err := yesCmd.Start(); err != nil {
		log.Err("Failed to start yes command")
		return
	}

	output, err := dnfCmd.CombinedOutput()
	if err != nil {
		log.Err(strings.Split(string(output), "\n")[0])
		return
	}

	log.Info("Success")
	yesCmd.Process.Kill()
}

func EnableRepo(r Repo) {
	dnfCmd := exec.Command("dnf", "config-manager", "--set-enabled", string(r))

	output, err := dnfCmd.CombinedOutput()
	if err != nil {
		log.Err(strings.Split(string(output), "\n")[0])
		return
	}
	log.Info("Success")
}

func MakeCahe() {
	dnfCmd := exec.Command("dnf", "makecache")

	output, err := dnfCmd.CombinedOutput()
	if err != nil {
		log.Err(strings.Split(string(output), "\n")[0])
		return
	}
	log.Info("Success")
}
