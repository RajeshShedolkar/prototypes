package airline

import (
	"log"
	"os"
)

func Reset() {
	db := DB()

	query, err := os.ReadFile("migrations/setup.sql")
	if err != nil {
		log.Fatal(err)
	}

	_, err = db.Exec(string(query))
	if err != nil {
		log.Fatal(err)
	}

	log.Println("Database reset completed successfully")
}

func Users() []*User {
	db := DB()

	rows, err := db.Query("SELECT id, name FROM users")
	if err != nil {
		log.Fatal(err)
	}
	defer rows.Close()

	var users []*User

	for rows.Next() {
		var user User

		err := rows.Scan(&user.ID, &user.Name)
		if err != nil {
			log.Fatal(err)
		}

		users = append(users, &user)
	}

	if err := rows.Err(); err != nil {
		log.Fatal(err)
	}

	return users
}