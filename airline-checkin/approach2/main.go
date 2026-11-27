
package main

import (
    "database/sql"
    "log"

    "airline-checkin/airline"
)

func main() {
    db := airline.ConnectDB()
    defer db.Close()

    // Run only when you want to recreate all tables and seed data.
    // if err := airline.Reset(db); err != nil {
    //     log.Fatal(err)
    // }

    log.Println("Approach 2: Starting...")

    allocateSeat(db)
}

func allocateSeat(db *sql.DB) {
    // TODO: Implement seat allocation logic
}
