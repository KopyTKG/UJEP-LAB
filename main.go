package main

import (
	"nebula_cluster/dnf"
	"nebula_cluster/file"
	"nebula_cluster/log"
	"nebula_cluster/port"
	"nebula_cluster/service"
)

func main() {
	repos := []dnf.Repo{"crb"}

	pkgs := []dnf.Package{"chrony", "centos-release-ceph-reef", "cephadm", "epel-release", "ceph-common", "opennebula", "opennebula-fireedge", "opennebula-gate", "opennebula-flow", "opennebula-provision", "mariadb-server"}

	usedport := []port.Port{"8443/tcp", "3000/tcp", "9095/tcp", "9093/tcp", "9100/tcp", "9283/tcp", "123/udp", "2616/tcp", "9869/tcp", "4124/tcp", "4125/tcp", "3306/tcp"}

	daemons := []service.Daemon{"chronyd.service", "mariadb.service"}

	for _, r := range repos {
		log.Info("Enabling repo=" + string(r))
		dnf.EnableRepo(r)
		dnf.MakeCahe()
	}

	file.Write("/etc/yum.repos.d/opennebula.repo", `[opennebula]
name=OpenNebula Community Edition
baseurl=https://downloads.opennebula.io/repo/6.10/RedHat/$releasever/$basearch
enabled=1
gpgkey=https://downloads.opennebula.io/repo/repo2.key
gpgcheck=1
repo_gpgcheck=1
`)
	dnf.MakeCahe()

	for _, p := range pkgs {
		log.Info("Installing package=" + string(p))
		dnf.Install(p)
	}

	for _, p := range usedport {
		log.Info("Adding port=" + string(p))
		port.AddPerma(p)
	}
	port.Reload()

	for _, daemon := range daemons {
		log.Info("Starting service=" + string(daemon))
		service.StartNow(daemon)
	}

}
