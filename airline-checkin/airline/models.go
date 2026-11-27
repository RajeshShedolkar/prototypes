package airline

type User struct {
	ID   int
	Name string
}

type Seat struct {
	ID     int
	Name   string
	TripID int
	UserID *int
}