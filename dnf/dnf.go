package dnf

import (
	"nebula_cluster/log"
	"os/exec"
)

type Package string
type Repo string

func Install(pkg Package) {
	log.Info("Installing " + string(pkg))
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
		log.Err(string(output))
		return
	}

	log.Success("Success")
	yesCmd.Process.Kill()
}

func EnableRepo(r Repo) {
	log.Info("Adding " + string(r))
	dnfCmd := exec.Command("dnf", "config-manager", "--set-enabled", string(r))

	output, err := dnfCmd.CombinedOutput()
	if err != nil {
		log.Err(string(output))
		return
	}
	log.Success("Success")
}

func MakeCache() {
	log.Info("Making cache ")
	yesCmd := exec.Command("yes")
	dnfCmd := exec.Command("dnf", "makecache", "-y")

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
		log.Err(string(output))
		return
	}

	log.Success("Success")
	yesCmd.Process.Kill()
}
