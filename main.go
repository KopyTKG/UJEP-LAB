package main

import (
	"nebula_cluster/dnf"
	"nebula_cluster/file"
	"nebula_cluster/firewalld"
	"nebula_cluster/log"
	"nebula_cluster/mariadb"
	"nebula_cluster/nebula"
	"nebula_cluster/password"
	"nebula_cluster/perms"
	"nebula_cluster/systemctl"
	"os"
)

func main() {
	args := os.Args[1:]

	if len(args) < 1 {
		log.LogLevel = 1
		mainLogic()
	} else {
		handleArgs(args)
	}

}

func handleArgs(args []string) {
	for _, arg := range args {
		switch arg {
		case "-L0":
			log.LogLevel = 0
		case "-L1":
			log.LogLevel = 1
		case "-L2":
			log.LogLevel = 2
		case "-L3":
			log.LogLevel = 3
		default:
			log.Info("Unknown argument: " + arg)
			log.LogLevel = 1
		}
		break
	}
	mainLogic()
}

func mainLogic() {
	perms.RootCheck()

	CreateNeededFiles()

	repos := []dnf.Repo{"crb"}

	pkgs := []dnf.Package{"chrony", "centos-release-ceph-reef", "cephadm", "epel-release", "ceph-common", "opennebula", "opennebula-fireedge", "opennebula-gate", "opennebula-flow", "opennebula-provision", "mariadb-server"}

	usedport := []firewalld.Port{"8443/tcp", "3000/tcp", "9095/tcp", "9093/tcp", "9100/tcp", "9283/tcp", "123/udp", "2616/tcp", "9869/tcp", "4124/tcp", "4124/udp", "4125/tcp", "3306/tcp", "2633/tcp", "2474/tcp", "5030/tcp", "29876/tcp"}

	daemons := []systemctl.Daemon{"chronyd.service", "mariadb.service"}

	for _, r := range repos {
		dnf.EnableRepo(r)
		dnf.MakeCache()
	}

	dnf.MakeCache()

	for _, p := range pkgs {
		dnf.Install(p)
	}

	for _, p := range usedport {
		firewalld.AddPerma(p)
	}

	for _, daemon := range daemons {
		systemctl.StartNow(daemon)
	}

	mariadb.SecureInstall()
	nebula.Init()

	nebulaDaemons := []systemctl.Daemon{"opennebula", "opennebula-fireedge", "opennebula-gate", "opennebula-flow"}

	for _, daemon := range nebulaDaemons {
		systemctl.Start(daemon)
	}

	for _, daemon := range nebulaDaemons {
		systemctl.Enable(daemon)
	}

	password.DumpCreds("passwords")
}

func CreateNeededFiles() {
	// Add opennebula CE repo
	file.Write("/etc/yum.repos.d/opennebula.repo", `[opennebula]
name=OpenNebula Community Edition
baseurl=https://downloads.opennebula.io/repo/6.10/RedHat/$releasever/$basearch
enabled=1
gpgkey=https://downloads.opennebula.io/repo/repo2.key
gpgcheck=1
repo_gpgcheck=1
`)

	// Add ntp config to use cesnet.cz
	file.Write("/etc/chrony.conf", `server tik.cesnet.cz iburst
server tak.cesnet.cz iburst

sourcedir /run/chrony-dhcp
driftfile /var/lib/chrony/drift
makestep 1.0 3
rtcsync
keyfile /etc/chrony.keys
ntsdumpdir /var/lib/chrony
leapsectz right/UTC
logdir /var/log/chrony
	`)
}
