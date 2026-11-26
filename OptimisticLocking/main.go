
package main

import (
	"database/sql"
	"fmt"
	"log"
	"time"

	_ "github.com/go-sql-driver/mysql"
)

func main() {

	// MySQL connection string
	dsn := "app_user:app123@tcp(localhost:3306)/app_db?parseTime=true"

	// Open database connection
	db, err := sql.Open("mysql", dsn)
	if err != nil {
		log.Fatal("Failed to open database:", err)
	}
	defer db.Close()

	// Connection pool configuration
	db.SetMaxOpenConns(25)
	db.SetMaxIdleConns(10)
	db.SetConnMaxLifetime(5 * time.Minute)

	// Verify database connectivity
	err = db.Ping()
	if err != nil {
		log.Fatal("Database connection failed:", err)
	}

	fmt.Println("Successfully connected to MySQL!")

	// Execute query
	var version string

	err = db.QueryRow("SELECT VERSION()").Scan(&version)
	if err != nil {
		log.Fatal("Query failed:", err)
	}

	fmt.Println("MySQL Version:", version)

	// Create table
	_, err = db.Exec(`
		CREATE TABLE IF NOT EXISTS users (
			id INT AUTO_INCREMENT PRIMARY KEY,
			name VARCHAR(100),
			email VARCHAR(150)
		)
	`)
	if err != nil {
		log.Fatal("Table creation failed:", err)
	}

	fmt.Println("Users table is ready!")

	// Insert record
	result, err := db.Exec(
		"INSERT INTO users (name, email) VALUES (?, ?)",
		"Rajesh",
		"rajesh@example.com",
	)
	if err != nil {
		log.Fatal("Insert failed:", err)
	}

	id, _ := result.LastInsertId()
	fmt.Println("Inserted user ID:", id)

	// Fetch records
	rows, err := db.Query("SELECT id, name, email FROM users")
	if err != nil {
		log.Fatal("Select failed:", err)
	}
	defer rows.Close()

	fmt.Println("\nUsers:")

	for rows.Next() {
		var id int
		var name, email string

		if err := rows.Scan(&id, &name, &email); err != nil {
			log.Fatal(err)
		}

		fmt.Printf("ID: %d | Name: %s | Email: %s\n",
			id, name, email)
	}

	if err := rows.Err(); err != nil {
		log.Fatal(err)
	}
}
