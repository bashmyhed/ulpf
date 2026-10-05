// Package registry manages collector registration, heartbeats, and the notification alert queue.
package registry

import (
	"crypto/rand"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"regexp"
	"sync"
	"time"

	"ulpf-config-server/internal/models"
)

// machineIDRegex — strict allowlist to prevent injection
var machineIDRegex = regexp.MustCompile(`^[a-zA-Z0-9_\-]+$`)

// CollectorEntry is the full registry record for one collector
type CollectorEntry struct {
	Registration models.CollectorRegistration `json:"registration"`
	Token        string                       `json:"token"`
	LastHeartbeat *models.CollectorHeartbeat  `json:"last_heartbeat,omitempty"`
	LastSeen      time.Time                   `json:"last_seen"`
	RegisteredAt  time.Time                   `json:"registered_at"`
}

// Registry is the in-memory + file-persisted store for all collectors and notifications.
type Registry struct {
	mu            sync.RWMutex
	collectors    map[string]*CollectorEntry   // key: machineID
	notifications []models.Notification
	dataFile      string
	headSHAFunc   func() string // callback to get current HEAD from server
}

// persistedData is the JSON structure written to disk
type persistedData struct {
	Collectors    map[string]*CollectorEntry `json:"collectors"`
	Notifications []models.Notification      `json:"notifications"`
}

// NewRegistry creates and loads a registry.
// dataFile: path to JSON persistence file
// headSHAFunc: callback returning current HEAD SHA (for config-exists check)
func NewRegistry(dataFile string, headSHAFunc func() string) *Registry {
	r := &Registry{
		collectors:  make(map[string]*CollectorEntry),
		dataFile:    dataFile,
		headSHAFunc: headSHAFunc,
	}
	r.load()
	return r
}

// Register processes a collector registration request.
// If the collector is new it issues a fresh token and persists.
// If it already exists it refreshes metadata and returns the existing token.
// Writes an "orphan_collector" notification if no config exists for this machine.
func (r *Registry) Register(reg *models.CollectorRegistration, configExists bool) (*models.RegistrationResponse, error) {
	if !machineIDRegex.MatchString(reg.MachineID) {
		return nil, fmt.Errorf("invalid machine_id: only alphanumerics, hyphens and underscores are allowed")
	}
	if len(reg.MachineID) > 64 {
		return nil, fmt.Errorf("machine_id too long (max 64 chars)")
	}

	r.mu.Lock()
	defer r.mu.Unlock()

	entry, exists := r.collectors[reg.MachineID]
	if !exists {
		token, err := generateToken()
		if err != nil {
			return nil, fmt.Errorf("token generation failed: %w", err)
		}
		entry = &CollectorEntry{
			Registration: *reg,
			Token:        token,
			RegisteredAt: time.Now().UTC(),
			LastSeen:     time.Now().UTC(),
		}
		r.collectors[reg.MachineID] = entry
		// Write token to secrets dir for persistence
		r.writeTokenFile(reg.MachineID, token)
	} else {
		// Refresh mutable fields
		entry.Registration.Hostname = reg.Hostname
		entry.Registration.HostIP = reg.HostIP
		entry.Registration.Version = reg.Version
		entry.Registration.Capabilities = reg.Capabilities
		entry.LastSeen = time.Now().UTC()
	}

	// Orphan notification — push once (de-duplicate by machineID + type)
	if !configExists && !exists {
		notif := models.Notification{
			ID:            newNotifID(),
			Type:          "orphan_collector",
			MachineID:     reg.MachineID,
			SiteID:        reg.SiteID,
			CollectorType: reg.CollectorType,
			Message: fmt.Sprintf(
				"Collector '%s' (type: %s, site: %s) registered but has NO configuration in the config repo. "+
					"Please push a config to machines/%s/ or sites/%s/%s/.",
				reg.MachineID, reg.CollectorType, reg.SiteID,
				reg.MachineID, reg.SiteID, reg.CollectorType,
			),
			Severity:  "warn",
			Timestamp: time.Now().UTC(),
			Resolved:  false,
		}
		r.notifications = append(r.notifications, notif)
	}

	r.save()

	headSHA := ""
	if r.headSHAFunc != nil {
		headSHA = r.headSHAFunc()
	}

	msg := "Registration successful"
	if !configExists {
		msg = "Registered — WARNING: no config found for this machine. An alert has been raised."
	}
	if exists {
		msg = "Re-registration accepted, token refreshed"
	}

	return &models.RegistrationResponse{
		Token:            entry.Token,
		HEADSHA:          headSHA,
		PollIntervalSecs: 30,
		ConfigExists:     configExists,
		Message:          msg,
	}, nil
}

// Heartbeat updates the liveness and metrics snapshot for a registered collector.
func (r *Registry) Heartbeat(hb *models.CollectorHeartbeat) error {
	r.mu.Lock()
	defer r.mu.Unlock()

	entry, ok := r.collectors[hb.MachineID]
	if !ok {
		return fmt.Errorf("unknown machine_id: %s — register first", hb.MachineID)
	}
	entry.LastHeartbeat = hb
	entry.LastSeen = time.Now().UTC()
	r.save()
	return nil
}

// AuthorizeToken checks if the given token belongs to a known collector.
// Returns (machineID, true) if valid, ("", false) otherwise.
func (r *Registry) AuthorizeToken(token string) (string, bool) {
	r.mu.RLock()
	defer r.mu.RUnlock()
	for machineID, entry := range r.collectors {
		if entry.Token == token {
			return machineID, true
		}
	}
	return "", false
}

// List returns all collector entries, optionally filtered by siteID.
func (r *Registry) List(siteID string) []*CollectorEntry {
	r.mu.RLock()
	defer r.mu.RUnlock()
	var out []*CollectorEntry
	for _, e := range r.collectors {
		if siteID == "" || e.Registration.SiteID == siteID {
			// shallow copy to avoid races
			cp := *e
			out = append(out, &cp)
		}
	}
	return out
}

// Get returns a single collector entry.
func (r *Registry) Get(machineID string) (*CollectorEntry, bool) {
	r.mu.RLock()
	defer r.mu.RUnlock()
	e, ok := r.collectors[machineID]
	if !ok {
		return nil, false
	}
	cp := *e
	return &cp, true
}

// GetNotifications returns notifications, optionally filtered by resolved state.
func (r *Registry) GetNotifications(onlyUnresolved bool) []models.Notification {
	r.mu.RLock()
	defer r.mu.RUnlock()
	var out []models.Notification
	for _, n := range r.notifications {
		if onlyUnresolved && n.Resolved {
			continue
		}
		out = append(out, n)
	}
	return out
}

// ResolveNotification marks a notification resolved.
func (r *Registry) ResolveNotification(id string) error {
	r.mu.Lock()
	defer r.mu.Unlock()
	for i, n := range r.notifications {
		if n.ID == id {
			t := time.Now().UTC()
			r.notifications[i].Resolved = true
			r.notifications[i].ResolvedAt = &t
			r.save()
			return nil
		}
	}
	return fmt.Errorf("notification %s not found", id)
}

// load reads persisted state from disk (best-effort; starts fresh if missing/corrupt).
func (r *Registry) load() {
	if r.dataFile == "" {
		return
	}
	data, err := os.ReadFile(r.dataFile)
	if err != nil {
		return // fresh start
	}
	var pd persistedData
	if err := json.Unmarshal(data, &pd); err != nil {
		fmt.Fprintf(os.Stderr, "registry: failed to parse %s: %v — starting fresh\n", r.dataFile, err)
		return
	}
	if pd.Collectors != nil {
		r.collectors = pd.Collectors
	}
	if pd.Notifications != nil {
		r.notifications = pd.Notifications
	}
}

// save flushes state to disk (best-effort; errors are logged but not fatal).
func (r *Registry) save() {
	if r.dataFile == "" {
		return
	}
	if err := os.MkdirAll(filepath.Dir(r.dataFile), 0750); err != nil {
		fmt.Fprintf(os.Stderr, "registry: mkdir %s: %v\n", filepath.Dir(r.dataFile), err)
		return
	}
	pd := persistedData{
		Collectors:    r.collectors,
		Notifications: r.notifications,
	}
	data, err := json.MarshalIndent(pd, "", "  ")
	if err != nil {
		fmt.Fprintf(os.Stderr, "registry: marshal failed: %v\n", err)
		return
	}
	// Atomic write via temp file
	tmp := r.dataFile + ".tmp"
	if err := os.WriteFile(tmp, data, 0640); err != nil {
		fmt.Fprintf(os.Stderr, "registry: write %s: %v\n", tmp, err)
		return
	}
	if err := os.Rename(tmp, r.dataFile); err != nil {
		fmt.Fprintf(os.Stderr, "registry: rename %s: %v\n", tmp, err)
	}
}

// writeTokenFile writes a token to the secrets directory for external reference.
func (r *Registry) writeTokenFile(machineID, token string) {
	// Derive secrets dir from dataFile path
	secretsDir := filepath.Join(filepath.Dir(r.dataFile), "tokens")
	if err := os.MkdirAll(secretsDir, 0750); err != nil {
		return
	}
	path := filepath.Join(secretsDir, machineID+".token")
	_ = os.WriteFile(path, []byte(token), 0600)
}

// generateToken returns a cryptographically random agent token.
func generateToken() (string, error) {
	b := make([]byte, 16)
	if _, err := rand.Read(b); err != nil {
		return "", err
	}
	return "ulpf_agent_" + hex.EncodeToString(b), nil
}

// newNotifID returns a short random notification ID.
func newNotifID() string {
	b := make([]byte, 6)
	_, _ = rand.Read(b)
	return hex.EncodeToString(b)
}
