package main

import (
	"context"
	"errors"
	"fmt"
	"sync"

	"github.com/jackc/pgx/v5"
)

// PoolConfig holds the configuration for our custom SimplePool.
type PoolConfig struct {
	DSN     string
	MinConn int
	MaxConn int
}

// SimplePool represents a simple, thread-safe connection pool for PostgreSQL.
// It uses a buffered Go channel as a bounded blocking queue to manage idle connections.
type SimplePool struct {
	cfg         PoolConfig
	mu          sync.Mutex
	conns       chan *pgx.Conn // Bounded channel holding idle connections
	currentOpen int            // Total connections currently managed (idle + active)
	isClosed    bool
}

// NewSimplePool initializes the pool and pre-warms MinConn connections.
func NewSimplePool(ctx context.Context, cfg PoolConfig) (*SimplePool, error) {
	if cfg.MinConn < 0 || cfg.MaxConn <= 0 || cfg.MinConn > cfg.MaxConn {
		return nil, fmt.Errorf("invalid pool bounds: min=%d, max=%d", cfg.MinConn, cfg.MaxConn)
	}

	p := &SimplePool{
		cfg:   cfg,
		conns: make(chan *pgx.Conn, cfg.MaxConn),
	}

	// 1. Pre-warm: initialize min connections upfront
	for i := 0; i < cfg.MinConn; i++ {
		conn, err := pgx.Connect(ctx, cfg.DSN)
		if err != nil {
			p.Close(ctx)
			return nil, fmt.Errorf("failed to pre-warm connection %d/%d: %w", i+1, cfg.MinConn, err)
		}
		p.conns <- conn
		p.currentOpen++
	}

	fmt.Printf("[DBPool] Initialized with minConn=%d, maxConn=%d (pre-warmed %d conns)\n",
		cfg.MinConn, cfg.MaxConn, p.currentOpen)

	return p, nil
}

// Acquire retrieves an available connection from the pool.
// 1. If an idle connection is available in the queue, it returns immediately.
// 2. If no idle connection exists, but total connections < MaxConn, it opens a new one.
// 3. If total connections == MaxConn, it blocks until a connection is released or context expires.
func (p *SimplePool) Acquire(ctx context.Context) (*pgx.Conn, error) {
	// Step 1: Fast path - try to pop an existing idle connection without blocking
	select {
	case conn := <-p.conns:
		return conn, nil
	default:
	}

	// Step 2: Can we create a new connection up to MaxConn?
	p.mu.Lock()
	if p.isClosed {
		p.mu.Unlock()
		return nil, errors.New("pool is closed")
	}

	if p.currentOpen < p.cfg.MaxConn {
		p.currentOpen++
		p.mu.Unlock() // Unlock before network I/O so other goroutines aren't blocked

		conn, err := pgx.Connect(ctx, p.cfg.DSN)
		if err != nil {
			p.mu.Lock()
			p.currentOpen--
			p.mu.Unlock()
			return nil, fmt.Errorf("failed to open new pooled connection: %w", err)
		}
		return conn, nil
	}
	p.mu.Unlock()

	// Step 3: Max connections reached; block until another goroutine releases one
	select {
	case conn := <-p.conns:
		return conn, nil
	case <-ctx.Done():
		return nil, fmt.Errorf("acquire timed out or canceled: %w", ctx.Err())
	}
}

// Release returns a borrowed connection back to the pool's idle queue.
func (p *SimplePool) Release(conn *pgx.Conn) {
	if conn == nil {
		return
	}

	p.mu.Lock()
	defer p.mu.Unlock()

	if p.isClosed {
		conn.Close(context.Background())
		p.currentOpen--
		return
	}

	select {
	case p.conns <- conn:
		// Returned connection back to the idle channel successfully
	default:
		// Queue was unexpectedly full; close this excess connection
		conn.Close(context.Background())
		p.currentOpen--
	}
}

// Stats returns the current state of the pool (total open, idle, active).
func (p *SimplePool) Stats() (totalOpen, idle, active int) {
	p.mu.Lock()
	defer p.mu.Unlock()
	totalOpen = p.currentOpen
	idle = len(p.conns)
	active = totalOpen - idle
	return
}

// Close closes all connections in the pool and shuts it down.
func (p *SimplePool) Close(ctx context.Context) {
	p.mu.Lock()
	if p.isClosed {
		p.mu.Unlock()
		return
	}
	p.isClosed = true
	close(p.conns)
	p.mu.Unlock()

	for conn := range p.conns {
		conn.Close(ctx)
	}
	fmt.Println("[DBPool] All connections closed.")
}

