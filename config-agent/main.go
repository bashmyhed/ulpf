package main

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"os"
	"os/exec"
	"os/signal"
	"path/filepath"
	"strings"
	"syscall"
	"time"

	"gopkg.in/yaml.v3"
)

// Config holds the agent configuration
type Config struct {
	ConfigServerURL string
	AgentToken      string
	SiteID          string
	MachineID       string
	CollectorType   string
	VectorConfigDir string
	StagingDir      string
	BackupDir       string
	PollInterval    time.Duration
	VectorPIDFile   string
}

// ConfigBundle represents a configuration bundle from the server
type ConfigBundle struct {
	SHA           string            `json:"sha"`
	SiteID        string            `json:"site_id"`
	MachineID     string            `json:"machine_id"`
	CollectorType string            `json:"collector_type"`
	Files         map[string]string `json:"files"`
	EnvVars       map[string]string `json:"env_vars"`
	GeneratedAt   string            `json:"generated_at"`
}

// AckRequest represents an acknowledgment to send to the server
type AckRequest struct {
	MachineID     string `json:"machine_id"`
	SiteID        string `json:"site_id"`
	CollectorType string `json:"collector_type"`
	AppliedSHA    string `json:"applied_sha"`
	Status        string `json:"status"` // "applied", "failed", "rolled_back"
	Error         string `json:"error,omitempty"`
	Timestamp     string `json:"timestamp"`
}

func main() {
	// Load configuration from environment
	cfg := Config{
		ConfigServerURL: getEnv("CONFIG_SERVER_URL", "http://config-server:8080"),
		AgentToken:      getEnv("AGENT_TOKEN", ""),
		SiteID:          getEnv("SITE_ID", "kol-dc1"),
		MachineID:       getEnv("MACHINE_ID", ""),
		CollectorType:   getEnv("COLLECTOR_TYPE", ""),
		VectorConfigDir: getEnv("VECTOR_CONFIG_DIR", "/etc/vector"),
		StagingDir:      getEnv("STAGING_DIR", "/staging"),
		BackupDir:       getEnv("BACKUP_DIR", "/backup"),
		PollInterval:    getDurationEnv("POLL_INTERVAL", 30*time.Second),
		VectorPIDFile:   getEnv("VECTOR_PID_FILE", "/run/vector.pid"),
	}
	
	if cfg.AgentToken == "" || cfg.MachineID == "" || cfg.CollectorType == "" {
		fmt.Fprintf(os.Stderr, "Missing required environment variables: AGENT_TOKEN, MACHINE_ID, COLLECTOR_TYPE\n")
		os.Exit(1)
	}
	
	fmt.Printf("Starting config agent for %s/%s (type: %s)\n", cfg.SiteID, cfg.MachineID, cfg.CollectorType)
	fmt.Printf("Config server: %s\n", cfg.ConfigServerURL)
	fmt.Printf("Vector config dir: %s\n", cfg.VectorConfigDir)
	
	// Create directories
	for _, dir := range []string{cfg.StagingDir, cfg.BackupDir, cfg.VectorConfigDir} {
		if err := os.MkdirAll(dir, 0755); err != nil {
			fmt.Fprintf(os.Stderr, "Failed to create directory %s: %v\n", dir, err)
			os.Exit(1)
		}
	}
	
	// Create HTTP client
	client := &http.Client{Timeout: 10 * time.Second}
	
	// Current applied SHA
	currentSHA := ""
	
	// Load current SHA from file if exists
	if shaBytes, err := os.ReadFile(filepath.Join(cfg.VectorConfigDir, ".applied_sha")); err == nil {
		currentSHA = strings.TrimSpace(string(shaBytes))
		fmt.Printf("Current applied SHA: %s\n", currentSHA)
	}
	
	// Context for graceful shutdown
	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()
	
	// Handle signals
	sigCh := make(chan os.Signal, 1)
	signal.Notify(sigCh, syscall.SIGTERM, syscall.SIGINT)
	go func() {
		<-sigCh
		fmt.Println("Received shutdown signal")
		cancel()
	}()
	
	// Main polling loop
	ticker := time.NewTicker(cfg.PollInterval)
	defer ticker.Stop()
	
	// Initial poll
	pollAndApply(ctx, client, &cfg, &currentSHA)
	
	for {
		select {
		case <-ctx.Done():
			fmt.Println("Shutting down config agent")
			return
		case <-ticker.C:
			pollAndApply(ctx, client, &cfg, &currentSHA)
		}
	}
}

func pollAndApply(ctx context.Context, client *http.Client, cfg *Config, currentSHA *string) {
	// Build request URL
	url := fmt.Sprintf("%s/config?site_id=%s&machine_id=%s&collector_type=%s", 
		cfg.ConfigServerURL, cfg.SiteID, cfg.MachineID, cfg.CollectorType)
	if *currentSHA != "" {
		url += "&since_sha=" + *currentSHA
	}
	
	req, err := http.NewRequestWithContext(ctx, "GET", url, nil)
	if err != nil {
		fmt.Printf("Error creating request: %v\n", err)
		return
	}
	req.Header.Set("Authorization", "Bearer "+cfg.AgentToken)
	
	resp, err := client.Do(req)
	if err != nil {
		fmt.Printf("Error polling config: %v\n", err)
		return
	}
	defer resp.Body.Close()
	
	if resp.StatusCode == http.StatusNotModified {
		// No changes
		return
	}
	
	if resp.StatusCode != http.StatusOK {
		body, _ := io.ReadAll(resp.Body)
		fmt.Printf("Config server error: %d - %s\n", resp.StatusCode, string(body))
		sendAck(client, cfg, *currentSHA, "failed", fmt.Sprintf("server error: %d", resp.StatusCode))
		return
	}
	
	// Parse bundle
	var bundle ConfigBundle
	if err := json.NewDecoder(resp.Body).Decode(&bundle); err != nil {
		fmt.Printf("Error decoding bundle: %v\n", err)
		sendAck(client, cfg, *currentSHA, "failed", fmt.Sprintf("decode error: %v", err))
		return
	}
	
	fmt.Printf("Received new config bundle: SHA=%s\n", bundle.SHA)
	
	// Apply the bundle
	if err := applyBundle(cfg, &bundle); err != nil {
		fmt.Printf("Failed to apply bundle: %v\n", err)
		sendAck(client, cfg, bundle.SHA, "failed", err.Error())
		return
	}
	
	// Update current SHA
	*currentSHA = bundle.SHA
	
	// Save SHA to file
	if err := os.WriteFile(filepath.Join(cfg.VectorConfigDir, ".applied_sha"), []byte(bundle.SHA), 0644); err != nil {
		fmt.Printf("Warning: failed to write .applied_sha: %v\n", err)
	}
	
	// Send success ack
	sendAck(client, cfg, bundle.SHA, "applied", "")
}

func applyBundle(cfg *Config, bundle *ConfigBundle) error {
	// Create staging directory for this SHA
	stageDir := filepath.Join(cfg.StagingDir, bundle.SHA)
	if err := os.MkdirAll(stageDir, 0755); err != nil {
		return fmt.Errorf("failed to create staging dir: %w", err)
	}
	
	// Merge all vector.yaml files into a single vector.yaml at the root
	mergedYAML, err := mergeBundle(bundle)
	if err != nil {
		return fmt.Errorf("failed to merge bundle: %w", err)
	}
	
	// Write merged vector.yaml at root
	if err := os.WriteFile(filepath.Join(stageDir, "vector.yaml"), []byte(mergedYAML), 0644); err != nil {
		return err
	}
	
	// Write .env file
	envContent := ""
	for k, v := range bundle.EnvVars {
		envContent += fmt.Sprintf("%s=%s\n", k, v)
	}
	if err := os.WriteFile(filepath.Join(stageDir, ".env"), []byte(envContent), 0644); err != nil {
		return err
	}
	
	// Validate with vector
	if err := validateConfig(stageDir); err != nil {
		return fmt.Errorf("validation failed: %w", err)
	}
	
	// Atomic swap: backup current, then symlink new
	if err := atomicSwap(cfg.VectorConfigDir, stageDir, cfg.BackupDir); err != nil {
		return fmt.Errorf("atomic swap failed: %w", err)
	}
	
	// Hot reload Vector
	if err := hotReloadVector(cfg.VectorPIDFile); err != nil {
		// Rollback on reload failure
		if rollbackErr := rollback(cfg.VectorConfigDir, cfg.BackupDir); rollbackErr != nil {
			fmt.Printf("CRITICAL: Rollback also failed: %v\n", rollbackErr)
		}
		return fmt.Errorf("hot reload failed: %w", err)
	}
	
	fmt.Printf("Successfully applied config SHA: %s\n", bundle.SHA)
	return nil
}

func validateConfig(configDir string) error {
	// Find vector binary
	vectorBin := findVectorBinary()
	if vectorBin == "" {
		return fmt.Errorf("vector binary not found")
	}
	
	cmd := exec.Command(vectorBin, "validate", "--no-environment", "--config-dir", configDir)
	cmd.Dir = configDir
	output, err := cmd.CombinedOutput()
	
	if err != nil {
		return fmt.Errorf("vector validate failed: %w\nOutput: %s", err, string(output))
	}
	
	outStr := string(output)
	if strings.Contains(outStr, "Failed to load") || strings.Contains(outStr, "Invalid") {
		return fmt.Errorf("vector validation failed: %s", outStr)
	}
	
	return nil
}

func findVectorBinary() string {
	paths := []string{
		"/home/paul/.vector/bin/vector",
		"/usr/local/bin/vector",
		"/usr/bin/vector",
		"/opt/vector/bin/vector",
		"/root/.vector/bin/vector",
	}
	
	for _, p := range paths {
		if _, err := exec.LookPath(p); err == nil {
			return p
		}
	}
	
	if path, err := exec.LookPath("vector"); err == nil {
		return path
	}
	
	return ""
}

func copyDir(src, dst string) error {
	if err := os.MkdirAll(dst, 0755); err != nil {
		return err
	}
	entries, err := os.ReadDir(src)
	if err != nil {
		return err
	}
	for _, entry := range entries {
		srcPath := filepath.Join(src, entry.Name())
		dstPath := filepath.Join(dst, entry.Name())
		if entry.IsDir() {
			if err := copyDir(srcPath, dstPath); err != nil {
				return err
			}
		} else {
			data, err := os.ReadFile(srcPath)
			if err != nil {
				return err
			}
			if err := os.WriteFile(dstPath, data, 0644); err != nil {
				return err
			}
		}
	}
	return nil
}

func atomicSwap(configDir, stageDir, backupDir string) error {
	// Create backup of current config if it exists
	if _, err := os.Stat(configDir); err == nil {
		backupName := fmt.Sprintf("backup-%s", time.Now().Format("20060102-150405"))
		backupPath := filepath.Join(backupDir, backupName)
		_ = os.MkdirAll(backupPath, 0755)
		_ = copyDir(configDir, backupPath)
		cleanOldBackups(backupDir, 3)
	}

	// Copy new config files into configDir
	if err := os.MkdirAll(configDir, 0755); err != nil {
		return err
	}
	if err := copyDir(stageDir, configDir); err != nil {
		return fmt.Errorf("failed to copy new config: %w", err)
	}

	return nil
}

func cleanOldBackups(backupDir string, keep int) {
	entries, err := os.ReadDir(backupDir)
	if err != nil {
		return
	}
	
	if len(entries) <= keep {
		return
	}
	
	// Sort by name (timestamp)
	// Simple approach: remove oldest
	for i := 0; i < len(entries)-keep; i++ {
		os.RemoveAll(filepath.Join(backupDir, entries[i].Name()))
	}
}

func rollback(configDir, backupDir string) error {
	// Find latest backup
	entries, err := os.ReadDir(backupDir)
	if err != nil || len(entries) == 0 {
		return fmt.Errorf("no backups available")
	}
	
	// Get latest backup
	latestBackup := entries[len(entries)-1].Name()
	backupPath := filepath.Join(backupDir, latestBackup)
	
	// Restore backup by copying files back
	if err := copyDir(backupPath, configDir); err != nil {
		return fmt.Errorf("failed to restore backup: %w", err)
	}
	
	fmt.Printf("Rolled back to backup: %s\n", latestBackup)
	return nil
}

func hotReloadVector(pidFile string) error {
	// Read Vector PID
	pidBytes, err := os.ReadFile(pidFile)
	if err != nil {
		return fmt.Errorf("failed to read PID file: %w", err)
	}
	
	pidStr := strings.TrimSpace(string(pidBytes))
	if pidStr == "" {
		return fmt.Errorf("empty PID file")
	}
	
	// Send SIGHUP
	cmd := exec.Command("kill", "-HUP", pidStr)
	if err := cmd.Run(); err != nil {
		return fmt.Errorf("failed to send SIGHUP: %w", err)
	}
	
	fmt.Printf("Sent SIGHUP to Vector PID %s\n", pidStr)
	return nil
}

func sendAck(client *http.Client, cfg *Config, sha, status, errMsg string) {
	ack := AckRequest{
		MachineID:     cfg.MachineID,
		SiteID:        cfg.SiteID,
		CollectorType: cfg.CollectorType,
		AppliedSHA:    sha,
		Status:        status,
		Error:         errMsg,
		Timestamp:     time.Now().UTC().Format(time.RFC3339),
	}
	
	body, _ := json.Marshal(ack)
	url := fmt.Sprintf("%s/ack", cfg.ConfigServerURL)
	
	req, _ := http.NewRequest("POST", url, bytes.NewReader(body))
	req.Header.Set("Authorization", "Bearer "+cfg.AgentToken)
	req.Header.Set("Content-Type", "application/json")
	
	resp, err := client.Do(req)
	if err != nil {
		fmt.Printf("Failed to send ack: %v\n", err)
		return
	}
	defer resp.Body.Close()
	
	if resp.StatusCode != http.StatusOK {
		fmt.Printf("Ack failed with status: %d\n", resp.StatusCode)
	}
}

func substituteEnvVars(content string, envVars map[string]string) string {
	for key, value := range envVars {
		// Replace ${KEY} and ${KEY:-default}
		content = strings.ReplaceAll(content, fmt.Sprintf("${%s}", key), value)
		content = strings.ReplaceAll(content, "$"+key, value)
	}
	return content
}

// mergeBundle merges all vector.yaml files in the bundle into a single vector.yaml
func mergeBundle(bundle *ConfigBundle) (string, error) {
	merged := make(map[string]interface{})
	
	// Define merge priority order
	priority := []string{
		"global/vector.yaml",
		fmt.Sprintf("sites/%s/%s/vector.yaml", bundle.SiteID, bundle.CollectorType),
		fmt.Sprintf("machines/%s/vector.yaml", bundle.MachineID),
	}
	
	for _, relPath := range priority {
		content, ok := bundle.Files[relPath]
		if !ok {
			continue
		}
		
		// Substitute env vars
		content = substituteEnvVars(content, bundle.EnvVars)
		
		var cfg map[string]interface{}
		if err := yaml.Unmarshal([]byte(content), &cfg); err != nil {
			return "", fmt.Errorf("failed to parse %s: %w", relPath, err)
		}
		
		merged = deepMerge(merged, cfg)
	}
	
	// Marshal back to YAML
	output, err := yaml.Marshal(merged)
	if err != nil {
		return "", err
	}
	
	return string(output), nil
}

// deepMerge merges two maps recursively
func deepMerge(dst, src map[string]interface{}) map[string]interface{} {
	result := make(map[string]interface{})
	
	// Copy dst
	for k, v := range dst {
		result[k] = v
	}
	
	// Merge src
	for k, v := range src {
		if existing, ok := result[k]; ok {
			// Both are maps -> deep merge
			if dstMap, ok := existing.(map[string]interface{}); ok {
				if srcMap, ok := v.(map[string]interface{}); ok {
					result[k] = deepMerge(dstMap, srcMap)
					continue
				}
			}
			// Both are slices -> append (for lists)
			if dstSlice, ok := existing.([]interface{}); ok {
				if srcSlice, ok := v.([]interface{}); ok {
					result[k] = append(dstSlice, srcSlice...)
					continue
				}
			}
		}
		// Otherwise replace
		result[k] = v
	}
	
	return result
}

func getEnv(key, defaultValue string) string {
	if value := os.Getenv(key); value != "" {
		return value
	}
	return defaultValue
}

func getDurationEnv(key string, defaultValue time.Duration) time.Duration {
	if value := os.Getenv(key); value != "" {
		if d, err := time.ParseDuration(value); err == nil {
			return d
		}
	}
	return defaultValue
}