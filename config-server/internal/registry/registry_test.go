package registry

import (
	"os"
	"path/filepath"
	"testing"

	"ulpf-config-server/internal/models"
)

func TestRegistryWorkflow(t *testing.T) {
	tmpDir, err := os.MkdirTemp("", "ulpf-reg-test-*")
	if err != nil {
		t.Fatalf("failed to create temp dir: %v", err)
	}
	defer os.RemoveAll(tmpDir)

	dataFile := filepath.Join(tmpDir, "registry.json")
	reg := NewRegistry(dataFile, func() string { return "test-head-sha-1234" })

	// 1. Register new collector without config (orphan)
	collectorA := &models.CollectorRegistration{
		MachineID:     "collector-a-01",
		SiteID:        "kol-dc1",
		CollectorType: "collector-a",
		Hostname:      "fw-host-01",
		Version:       "v1.0.0",
		Capabilities:  []string{"syslog", "cef"},
		HostIP:        "10.0.1.5",
	}

	resp, err := reg.Register(collectorA, false)
	if err != nil {
		t.Fatalf("Register failed: %v", err)
	}

	if resp.Token == "" {
		t.Errorf("expected non-empty token")
	}
	if resp.ConfigExists {
		t.Errorf("expected ConfigExists to be false")
	}

	// Verify token authorization
	machineID, ok := reg.AuthorizeToken(resp.Token)
	if !ok || machineID != "collector-a-01" {
		t.Errorf("AuthorizeToken failed: got %v, %v; want collector-a-01, true", machineID, ok)
	}

	// Verify notification alert queued for orphan
	notifs := reg.GetNotifications(true)
	if len(notifs) != 1 {
		t.Fatalf("expected 1 notification, got %d", len(notifs))
	}
	if notifs[0].Type != "orphan_collector" {
		t.Errorf("expected orphan_collector, got %s", notifs[0].Type)
	}

	// 2. Re-registration returns existing token
	resp2, err := reg.Register(collectorA, true)
	if err != nil {
		t.Fatalf("Re-register failed: %v", err)
	}
	if resp2.Token != resp.Token {
		t.Errorf("expected same token on re-registration, got %s vs %s", resp2.Token, resp.Token)
	}

	// 3. Heartbeat
	hb := &models.CollectorHeartbeat{
		MachineID:    "collector-a-01",
		SiteID:       "kol-dc1",
		CurrentSHA:   "test-head-sha-1234",
		Status:       "healthy",
		EventsPerSec: 155.2,
		BufferBytes:  10240,
		KafkaLag:     0,
		UptimeSecs:   120,
	}
	if err := reg.Heartbeat(hb); err != nil {
		t.Fatalf("Heartbeat failed: %v", err)
	}

	// Verify list collectors
	collectors := reg.List("kol-dc1")
	if len(collectors) != 1 {
		t.Fatalf("expected 1 collector, got %d", len(collectors))
	}
	if collectors[0].LastHeartbeat == nil || collectors[0].LastHeartbeat.EventsPerSec != 155.2 {
		t.Errorf("heartbeat not recorded in collector entry")
	}

	// 4. Resolve notification
	notifID := notifs[0].ID
	if err := reg.ResolveNotification(notifID); err != nil {
		t.Fatalf("ResolveNotification failed: %v", err)
	}
	unresolved := reg.GetNotifications(true)
	if len(unresolved) != 0 {
		t.Errorf("expected 0 unresolved notifications, got %d", len(unresolved))
	}
}
