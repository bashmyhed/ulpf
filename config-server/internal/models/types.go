package models

import (
	"time"
)

// ConfigBundle represents a configuration bundle served to agents
type ConfigBundle struct {
	SHA           string            `json:"sha"`
	SiteID        string            `json:"site_id"`
	MachineID     string            `json:"machine_id"`
	CollectorType string            `json:"collector_type"`
	Files         map[string]string `json:"files"`
	EnvVars       map[string]string `json:"env_vars"`
	GeneratedAt   time.Time         `json:"generated_at"`
}

// AckRequest represents an acknowledgment from an agent
type AckRequest struct {
	MachineID     string    `json:"machine_id" binding:"required"`
	SiteID        string    `json:"site_id" binding:"required"`
	CollectorType string    `json:"collector_type" binding:"required"`
	AppliedSHA    string    `json:"applied_sha" binding:"required"`
	Status        string    `json:"status" binding:"required"` // "applied", "failed", "rolled_back"
	Error         string    `json:"error,omitempty"`
	Timestamp     time.Time `json:"timestamp"`
}

// MachineStatus represents the status of a machine in the fleet
type MachineStatus struct {
	MachineID     string    `json:"machine_id"`
	SiteID        string    `json:"site_id"`
	CollectorType string    `json:"collector_type"`
	CurrentSHA    string    `json:"current_sha"`
	Status        string    `json:"status"` // "current", "behind", "failed", "offline"
	LastAck       time.Time `json:"last_ack"`
	Error         string    `json:"error,omitempty"`
	// Runtime metrics from heartbeat
	EventsPerSec float64   `json:"events_per_sec"`
	BufferBytes  int64     `json:"buffer_bytes"`
	KafkaLag     int64     `json:"kafka_lag"`
	UptimeSecs   float64   `json:"uptime_secs"`
	HostIP       string    `json:"host_ip"`
	Hostname     string    `json:"hostname"`
	Version      string    `json:"version"`
	Capabilities []string  `json:"capabilities"`
	RegisteredAt time.Time `json:"registered_at"`
}

// FleetStatus represents the overall fleet status
type FleetStatus struct {
	SiteID   string          `json:"site_id"`
	Machines []MachineStatus `json:"machines"`
	HEADSHA  string          `json:"head_sha"`
}

// CollectorRegistration is sent by an agent on first contact
type CollectorRegistration struct {
	MachineID     string   `json:"machine_id" binding:"required"`
	SiteID        string   `json:"site_id" binding:"required"`
	CollectorType string   `json:"collector_type" binding:"required"`
	Hostname      string   `json:"hostname"`
	Version       string   `json:"version"`
	Capabilities  []string `json:"capabilities"`
	HostIP        string   `json:"host_ip"`
}

// RegistrationResponse is returned after successful registration
type RegistrationResponse struct {
	Token          string `json:"token"`
	HEADSHA        string `json:"head_sha"`
	PollIntervalSecs int  `json:"poll_interval_secs"`
	ConfigExists   bool   `json:"config_exists"`
	Message        string `json:"message"`
}

// CollectorHeartbeat sent every 30s by the agent
type CollectorHeartbeat struct {
	MachineID    string  `json:"machine_id" binding:"required"`
	SiteID       string  `json:"site_id" binding:"required"`
	CurrentSHA   string  `json:"current_sha"`
	Status       string  `json:"status"`
	EventsPerSec float64 `json:"events_per_sec"`
	BufferBytes  int64   `json:"buffer_bytes"`
	KafkaLag     int64   `json:"kafka_lag"`
	UptimeSecs   float64 `json:"uptime_secs"`
	Error        string  `json:"error,omitempty"`
}

// Notification is placed on the alert queue for significant events
type Notification struct {
	ID            string    `json:"id"`
	Type          string    `json:"type"`     // "orphan_collector" | "config_applied" | "config_failed"
	MachineID     string    `json:"machine_id"`
	SiteID        string    `json:"site_id"`
	CollectorType string    `json:"collector_type"`
	Message       string    `json:"message"`
	Severity      string    `json:"severity"` // "info" | "warn" | "error"
	Timestamp     time.Time `json:"timestamp"`
	Resolved      bool      `json:"resolved"`
	ResolvedAt    *time.Time `json:"resolved_at,omitempty"`
}