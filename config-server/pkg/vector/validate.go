package vector

import (
	"fmt"
	"os/exec"
	"strings"
)

// Validate runs vector validate on a config directory
func Validate(configDir string) error {
	// Find vector binary
	vectorBin := findVectorBinary()
	if vectorBin == "" {
		return fmt.Errorf("vector binary not found in PATH")
	}
	
	// Run vector validate --no-environment --config-dir <dir>
	cmd := exec.Command(vectorBin, "validate", "--no-environment", "--config-dir", configDir)
	cmd.Dir = configDir
	output, err := cmd.CombinedOutput()
	
	if err != nil {
		return fmt.Errorf("vector validate failed: %w\nOutput: %s", err, string(output))
	}
	
	// Check output for validation errors
	outStr := string(output)
	if strings.Contains(outStr, "Failed to load") || strings.Contains(outStr, "Invalid") {
		return fmt.Errorf("vector validation failed: %s", outStr)
	}
	
	return nil
}

// findVectorBinary locates the vector binary
func findVectorBinary() string {
	paths := []string{
		"/home/paul/.vector/bin/vector",
		"/usr/local/bin/vector",
		"/usr/bin/vector",
		"/opt/vector/bin/vector",
	}
	
	for _, p := range paths {
		if _, err := exec.LookPath(p); err == nil {
			return p
		}
	}
	
	// Try PATH
	if path, err := exec.LookPath("vector"); err == nil {
		return path
	}
	
	return ""
}