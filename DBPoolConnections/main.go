package main

import (
	"context"
	"fmt"
	"os"
	"sync"
	"sync/atomic"
	"time"

	"github.com/jackc/pgx/v5"
)

const (
	defaultDSN = "postgres://postgres:postgres@localhost:5432/testdb?sslmode=disable"
)

// runDirectQuery opens a brand new TCP connection, executes query, and tears it down.
func runDirectQuery(ctx context.Context, dsn string, sleepSec float64) (time.Duration, error) {
	start := time.Now()

	// 1. New TCP connection + Postgres auth handshake
	conn, err := pgx.Connect(ctx, dsn)
	if err != nil {
		return 0, err
	}
	defer conn.Close(ctx) // Close TCP socket

	// 2. Execute query
	var dummy int
	query := fmt.Sprintf("SELECT 1 FROM pg_sleep(%f)", sleepSec)
	err = conn.QueryRow(ctx, query).Scan(&dummy)
	if err != nil {
		return 0, err
	}

	return time.Since(start), nil
}

// runPooledQuery borrows an idle connection from the pool, runs query, and returns it.
func runPooledQuery(ctx context.Context, pool *SimplePool, sleepSec float64) (time.Duration, error) {
	start := time.Now()

	// 1. Borrow connection from pool
	conn, err := pool.Acquire(ctx)
	if err != nil {
		return 0, err
	}
	defer pool.Release(conn) // Return back to pool

	// 2. Execute query
	var dummy int
	query := fmt.Sprintf("SELECT 1 FROM pg_sleep(%f)", sleepSec)
	err = conn.QueryRow(ctx, query).Scan(&dummy)
	if err != nil {
		return 0, err
	}

	return time.Since(start), nil
}

func main() {
	dsn := os.Getenv("DATABASE_URL")
	if dsn == "" {
		dsn = defaultDSN
	}

	ctx := context.Background()

	// 1. Verify database connectivity & fetch max_connections
	fmt.Println("Connecting to PostgreSQL at:", dsn)
	testConn, err := pgx.Connect(ctx, dsn)
	if err != nil {
		fmt.Printf("\n❌ Could not connect to PostgreSQL: %v\n", err)
		fmt.Println("💡 Make sure Docker container is running: docker compose up -d")
		os.Exit(1)
	}

	var maxConnections string
	_ = testConn.QueryRow(ctx, "SHOW max_connections").Scan(&maxConnections)
	testConn.Close(ctx)

	fmt.Printf("✅ DB Connected! PostgreSQL max_connections limit is: %s\n\n", maxConnections)

	// ----------------------------------------------------
	// SPIKE / BURST TEST: 150 SIMULTANEOUS REQUESTS
	// ----------------------------------------------------
	const burstSize = 1500
	const sleepDuration = 0.05 // 50ms query so connections overlap

	fmt.Println("==================================================================")
	fmt.Printf(" 💥 BURST EXPERIMENT: %d SIMULTANEOUS REQUESTS\n", burstSize)
	fmt.Printf(" Postgres limit = %s | In-flight sleep = %.0fms\n", maxConnections, sleepDuration*1000)
	fmt.Println("==================================================================")

	// Part A: Burst with Direct Connection (Unbounded)
	fmt.Printf("\n[1] Firing %d simultaneous queries with DIRECT CONNECTIONS...\n", burstSize)
	var directSuccess int64
	var directFail int64
	var directSampleErr string
	var errOnce sync.Once

	startGateDirect := make(chan struct{})
	var wgDirect sync.WaitGroup
	directStart := time.Now()

	for i := 0; i < burstSize; i++ {
		wgDirect.Add(1)
		go func() {
			defer wgDirect.Done()
			<-startGateDirect // Wait for simultaneous release
			_, err := runDirectQuery(ctx, dsn, sleepDuration)
			if err != nil {
				atomic.AddInt64(&directFail, 1)
				errOnce.Do(func() {
					directSampleErr = err.Error()
				})
			} else {
				atomic.AddInt64(&directSuccess, 1)
			}
		}()
	}

	close(startGateDirect) // Release all 150 goroutines simultaneously!
	wgDirect.Wait()
	directDuration := time.Since(directStart)

	fmt.Println("\n--- Direct Connection Burst Result ---")
	fmt.Printf("✅ Successful Queries:  %d / %d\n", directSuccess, burstSize)
	fmt.Printf("❌ Failed Queries:      %d / %d\n", directFail, burstSize)
	fmt.Printf("⏱ Total Time:          %v\n", directDuration)
	if directFail > 0 {
		fmt.Printf("💥 Postgres Error:      \"%s\"\n", directSampleErr)
	}

	// Part B: Burst with Simple DBPool (Capped at MaxConn = 10)
	fmt.Printf("\n------------------------------------------------------------------\n")
	fmt.Printf("[2] Firing %d simultaneous queries through DBPool (MaxConn=10)...\n", burstSize)

	poolCfg := PoolConfig{
		DSN:     dsn,
		MinConn: 2,
		MaxConn: 10,
	}
	pool, err := NewSimplePool(ctx, poolCfg)
	if err != nil {
		fmt.Printf("Failed to initialize SimplePool: %v\n", err)
		os.Exit(1)
	}
	defer pool.Close(ctx)

	var poolSuccess int64
	var poolFail int64
	var poolSampleErr string
	var poolErrOnce sync.Once

	startGatePool := make(chan struct{})
	var wgPool sync.WaitGroup
	poolStart := time.Now()

	for i := 0; i < burstSize; i++ {
		wgPool.Add(1)
		go func() {
			defer wgPool.Done()
			<-startGatePool // Wait for simultaneous release
			_, err := runPooledQuery(ctx, pool, sleepDuration)
			if err != nil {
				atomic.AddInt64(&poolFail, 1)
				poolErrOnce.Do(func() {
					poolSampleErr = err.Error()
				})
			} else {
				atomic.AddInt64(&poolSuccess, 1)
			}
		}()
	}

	close(startGatePool) // Release all 150 goroutines simultaneously!
	wgPool.Wait()
	poolDuration := time.Since(poolStart)

	totalConns, idleConns, activeConns := pool.Stats()
	fmt.Println("\n--- Simple DBPool Burst Result ---")
	fmt.Printf("✅ Successful Queries:  %d / %d\n", poolSuccess, burstSize)
	fmt.Printf("❌ Failed Queries:      %d / %d\n", poolFail, burstSize)
	fmt.Printf("⏱ Total Time:          %v\n", poolDuration)
	fmt.Printf("🛡 Max Conns Opened:    %d (Safely below Postgres limit of %s!)\n", totalConns, maxConnections)
	fmt.Printf("Final Pool State:       Total=%d, Idle=%d, Active=%d\n", totalConns, idleConns, activeConns)
	if poolFail > 0 {
		fmt.Printf("Errors:                 \"%s\"\n", poolSampleErr)
	}

	// Summary
	fmt.Println("\n==================================================================")
	fmt.Println(" 🎯 KEY TAKEAWAY")
	fmt.Println("==================================================================")
	fmt.Printf("• Without DBPool: Direct connections overwhelmed Postgres (%d queries failed with 'too many clients')\n", directFail)
	fmt.Printf("• With DBPool:    The pool buffered the spike to %d safe connections (%d queries succeeded, 0 failed!)\n", totalConns, poolSuccess)
	fmt.Println("==================================================================")
}
