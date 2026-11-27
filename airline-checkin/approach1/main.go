package main

import (
	"sync"

	"airline-checkin/airline"

	"github.com/charmbracelet/log"
)

func book(user *airline.User) (*airline.Seat, error) {
	// Approach-specific seat booking logic goes here
	return nil, nil
}

func main() {
	airline.Reset()
	log.SetLevel(log.DebugLevel)

	users := airline.Users()

	log.Debugf("simulating %d users", len(users))

	var wg sync.WaitGroup
	wg.Add(len(users))

	for ix := range users {
		go func(user *airline.User) {
			defer wg.Done()

			seat, err := book(user)

			if err != nil {
				log.Errorf("We could not assign the seat %s to %s", seat.Name, user.Name)
				log.Error(err)
			} else {
				log.Infof("We assigned the seat %s to %s", seat.Name, user.Name)
			}
		}(users[ix])
	}

	wg.Wait()
}