package airline

import (
	"database/sql"
	"log"
	"sync"

	_ "github.com/go-sql-driver/mysql"
)

var (
	db   *sql.DB
	once sync.Once
)

func DB() *sql.DB {
	once.Do(func() {
		var err error

		dsn := "app_user:app123@tcp(localhost:3306)/app_db?parseTime=true&multiStatements=true"

		db, err = sql.Open("mysql", dsn)
		if err != nil {
			log.Fatal(err)
		}

		if err = db.Ping(); err != nil {
			log.Fatal(err)
		}
	})

	return db
}