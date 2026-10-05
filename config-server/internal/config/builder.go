package config

import (
	"fmt"
	"os"
	"path/filepath"
	"strings"

	"ulpf-config-server/internal/git"
	"ulpf-config-server/internal/models"
	"ulpf-config-server/pkg/vector"

	"gopkg.in/yaml.v3"
)

// BundleBuilder builds configuration bundles from the git repo
type BundleBuilder struct {
	repo       *git.Repo
	secretsDir string
}

// NewBundleBuilder creates a new bundle builder
func NewBundleBuilder(repo *git.Repo, secretsDir string) *BundleBuilder {
	return &BundleBuilder{
		repo:       repo,
		secretsDir: secretsDir,
	}
}

// BuildBundle builds a config bundle for a specific machine
func (b *BundleBuilder) BuildBundle(commitHash, siteID, machineID, collectorType string) (*models.ConfigBundle, error) {
	// Determine the config paths to include
	// Priority: global -> sites/<site>/<collector> -> machines/<machine>
	
	files := make(map[string]string)
	envVars := make(map[string]string)
	
	// 1. Global base config (if exists)
	globalFiles, _ := b.repo.ListFilesAtCommit(commitHash, "global/")
	for _, f := range globalFiles {
		content, err := b.repo.GetFileAtCommit(commitHash, f)
		if err == nil {
			files[f] = content
		}
	}
	
	// 2. Site-specific config
	siteCollectorPath := fmt.Sprintf("sites/%s/%s/", siteID, collectorType)
	siteFiles, _ := b.repo.ListFilesAtCommit(commitHash, siteCollectorPath)
	for _, f := range siteFiles {
		content, err := b.repo.GetFileAtCommit(commitHash, f)
		if err == nil {
			files[f] = content
		}
	}
	
	// 3. Machine-specific overrides
	machinePath := fmt.Sprintf("machines/%s/", machineID)
	machineFiles, _ := b.repo.ListFilesAtCommit(commitHash, machinePath)
	for _, f := range machineFiles {
		content, err := b.repo.GetFileAtCommit(commitHash, f)
		if err == nil {
			files[f] = content
		}
	}
	
	// Load secrets and add to envVars
	b.loadSecrets(envVars)
	
	// Add standard env vars
	envVars["KAFKA_BOOTSTRAP"] = "kafka:9092"
	envVars["MINIO_ENDPOINT"] = "http://minio:9000"
	envVars["MINIO_BUCKET"] = "ulpf-data-lake"
	envVars["MINIO_ROOT_USER"] = "minioadmin"
	envVars["MINIO_ROOT_PASSWORD"] = "minioadmin"
	envVars["OPENSEARCH_ENDPOINT"] = "http://opensearch:9200"
	envVars["VECTOR_LOG"] = "info"
	
	commitTime, _ := b.repo.GetCommitTime(commitHash)
	
	return &models.ConfigBundle{
		SHA:           commitHash,
		SiteID:        siteID,
		MachineID:     machineID,
		CollectorType: collectorType,
		Files:         files,
		EnvVars:       envVars,
		GeneratedAt:   commitTime,
	}, nil
}

// loadSecrets loads secrets from files in the secrets directory
func (b *BundleBuilder) loadSecrets(envVars map[string]string) {
	if b.secretsDir == "" {
		return
	}
	
	entries, err := os.ReadDir(b.secretsDir)
	if err != nil {
		return
	}
	
	for _, entry := range entries {
		if entry.IsDir() {
			continue
		}
		path := filepath.Join(b.secretsDir, entry.Name())
		content, err := os.ReadFile(path)
		if err != nil {
			continue
		}
		// Secret file name becomes env var name (uppercase)
		key := strings.ToUpper(strings.TrimSuffix(entry.Name(), filepath.Ext(entry.Name())))
		envVars[key] = strings.TrimSpace(string(content))
	}
}

// ValidateBundle validates a bundle using vector validate
func (b *BundleBuilder) ValidateBundle(bundle *models.ConfigBundle) error {
	// Create a temporary directory with the bundle files
	tmpDir, err := os.MkdirTemp("", "bundle-validation-*")
	if err != nil {
		return err
	}
	defer os.RemoveAll(tmpDir)
	
	// For validation, we need a complete Vector config at the root.
	// Merge all vector.yaml files into a single vector.yaml at the root.
	mergedYAML, err := b.MergeBundle(bundle)
	if err != nil {
		return fmt.Errorf("failed to merge bundle: %w", err)
	}
	
	// DEBUG: Print merged YAML
	fmt.Printf("=== Merged YAML for validation ===\n%s\n=== End ===\n", mergedYAML)
	
	// Write merged vector.yaml at root
	if err := os.WriteFile(filepath.Join(tmpDir, "vector.yaml"), []byte(mergedYAML), 0644); err != nil {
		return err
	}
	
	// Write .env file for Vector
	envContent := ""
	for k, v := range bundle.EnvVars {
		envContent += fmt.Sprintf("%s=%s\n", k, v)
	}
	if err := os.WriteFile(filepath.Join(tmpDir, ".env"), []byte(envContent), 0644); err != nil {
		return err
	}
	
	// Run vector validate
	return vector.Validate(tmpDir)
}

// MergeBundle merges the bundle files into a single vector.yaml for the agent
func (b *BundleBuilder) MergeBundle(bundle *models.ConfigBundle) (string, error) {
	// Start with empty config
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

// substituteEnvVars replaces ${VAR:-default} and ${VAR} with values from envVars
func substituteEnvVars(content string, envVars map[string]string) string {
	for key, value := range envVars {
		// Replace ${KEY:-default} and ${KEY}
		patterns := []string{
			fmt.Sprintf("${%s}", key),
			fmt.Sprintf("${%s:-", key), // This won't work for all defaults, but handles basic case
		}
		for _, pattern := range patterns {
			content = strings.ReplaceAll(content, pattern, value)
		}
		// Also handle $KEY
		content = strings.ReplaceAll(content, "$"+key, value)
	}
	return content
}
// DebugBundle prints debug info about a bundle
func (b *BundleBuilder) DebugBundle(bundle *models.ConfigBundle) {
	fmt.Printf("=== Bundle Debug ===\n")
	fmt.Printf("SHA: %s\n", bundle.SHA)
	fmt.Printf("SiteID: %s\n", bundle.SiteID)
	fmt.Printf("MachineID: %s\n", bundle.MachineID)
	fmt.Printf("CollectorType: %s\n", bundle.CollectorType)
	fmt.Printf("Files count: %d\n", len(bundle.Files))
	for k := range bundle.Files {
		fmt.Printf("  File: %s (len=%d)\n", k, len(bundle.Files[k]))
	}
	fmt.Printf("EnvVars count: %d\n", len(bundle.EnvVars))
	for k := range bundle.EnvVars {
		fmt.Printf("  Env: %s\n", k)
	}
}
