package mariadb

import (
	"database/sql"
	"fmt"
	"nebula_cluster/log"
	"nebula_cluster/password"

	_ "github.com/go-sql-driver/mysql"
)

func SecureInstall() {
	root := password.Generate(20)
	oneadmin := password.Generate(20)
	dsn := "root@unix(/var/lib/mysql/mysql.sock)/mysql"
	db, err := sql.Open("mysql", dsn)
	if err != nil {
		log.Err(err.Error())
		return
	}
	defer db.Close()

	log.Info("Changing root password for MariaDB")
	_, err = db.Exec(fmt.Sprintf("ALTER USER 'root'@'localhost' IDENTIFIED BY '%s';", root))
	if err != nil {
		log.Err(err.Error())
		return
	}
	log.Success("Success")

	password.Creds["dbroot"] = root

	_, err = db.Exec(fmt.Sprintf("FLUSH PRIVILEGES;"))
	if err != nil {
		log.Err(err.Error())
		return
	}

	log.Info("Creating ONEADMIN user for mariadb")
	_, err = db.Exec(fmt.Sprintf("CREATE USER 'oneadmin'@'%%' IDENTIFIED BY '%s';", oneadmin))
	if err != nil {
		log.Err(err.Error())
		return
	}
	log.Success("Success")
	password.Creds["dboneadmin"] = oneadmin

	log.Info("Setting permissions for ONEADMIN user")
	_, err = db.Exec(fmt.Sprintf("GRANT ALL PRIVILEGES ON opennebula.* TO 'oneadmin'@'%%'"))
	if err != nil {
		log.Err(err.Error())
		return
	}
	log.Success("Success")

	log.Info("Setting transaction to isolation")
	_, err = db.Exec(fmt.Sprintf("SET GLOBAL TRANSACTION ISOLATION LEVEL READ COMMITTED;"))
	if err != nil {
		log.Err(err.Error())
		return
	}
	log.Success("Success")

}
