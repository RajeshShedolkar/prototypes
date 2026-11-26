
package main

import (
	"database/sql"
	"fmt"
	"log"
	"os"

	_ "github.com/go-sql-driver/mysql"
)



func ResetDatabase(db *sql.DB) error {

    fmt.Println("Starting fresh database setup...")

    // Step 1: Drop existing tables
    _, err := db.Exec(`
        DROP TABLE IF EXISTS seats;
        DROP TABLE IF EXISTS users;
        DROP TABLE IF EXISTS trips;
    `)
    if err != nil {
        return fmt.Errorf("failed to drop tables: %w", err)
    }

    fmt.Println("Existing tables dropped.")

    // Step 2: Read SQL file
    query, err := os.ReadFile("queries/setup.sql")
    if err != nil {
        return fmt.Errorf("failed to read SQL file: %w", err)
    }

    // Step 3: Execute DDL and INSERT queries
    _, err = db.Exec(string(query))
    if err != nil {
        return fmt.Errorf("failed to create tables and insert data: %w", err)
    }

    fmt.Println("Fresh tables created successfully!")
    fmt.Println("Trip inserted: 1")
    fmt.Println("Users inserted: 120")
    fmt.Println("Seats generated: 120")

    return nil
}


func PrintSeatArrangement(db *sql.DB, tripID int) error {

    query := `
        SELECT
            s.name,
            s.user_id,
            COALESCE(u.name, 'Available') AS passenger
        FROM seats s
        LEFT JOIN users u ON s.user_id = u.id
        WHERE s.trip_id = ?
        ORDER BY s.id
    `

    rows, err := db.Query(query, tripID)
    if err != nil {
        return err
    }
    defer rows.Close()

    // Store seats by row and column
    seatMap := make(map[int][]string)

    for rows.Next() {
        var seatName string
        var userID sql.NullInt64
        var passenger string

        if err := rows.Scan(&seatName, &userID, &passenger); err != nil {
            return err
        }

        var row int
        var column string

        if _, err := fmt.Sscanf(seatName, "%d-%s", &row, &column); err != nil {
            return err
        }

        status := "."
        if userID.Valid {
            status = "X"
        }

        seatMap[row] = append(seatMap[row], status)
    }

    if err := rows.Err(); err != nil {
        return err
    }

    fmt.Println("\n========== AIRLINE SEAT ARRANGEMENT ==========")
    fmt.Println("           FRONT / COCKPIT")
    fmt.Println("         =====================")
    fmt.Println()
    fmt.Println("            A B C     D E F")
    fmt.Println("         -------------------------")

    for row := 1; row <= len(seatMap); row++ {

        seats := seatMap[row]

        if len(seats) != 6 {
            return fmt.Errorf("invalid seat count in row %d: got %d", row, len(seats))
        }

        fmt.Printf("Row %2d      ", row)

        for col := 0; col < 6; col++ {

            if col == 3 {
                fmt.Print("    ")
            }

            fmt.Printf("%s ", seats[col])
        }

        fmt.Println()
    }

    fmt.Println("\nLegend: [O] Available  [X] Booked")
    fmt.Println("==============================================")

    return nil
}


func main() {

	// MySQL connection string
	dsn := "app_user:app123@tcp(localhost:3306)/app_db?parseTime=true&multiStatements=true"

	// Connect to MySQL
	db, err := sql.Open("mysql", dsn)
	if err != nil {
		log.Fatal("Database initialization failed:", err)
	}
	defer db.Close()

	// Verify connection
	if err := db.Ping(); err != nil {
		log.Fatal("MySQL connection failed:", err)
	}

	fmt.Println("Successfully connected to MySQL!")

	ResetDatabase(db)
    err = PrintSeatArrangement(db, 1)
    if err != nil {
        log.Fatal(err)
    }
}
