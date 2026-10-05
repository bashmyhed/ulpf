package main

import (
	"flag"
	"fmt"
	"os"

	"ulpf-config-server/internal/auth"
	"ulpf-config-server/internal/config"
	"ulpf-config-server/internal/git"
	"ulpf-config-server/internal/http"
)

func main() {
	// Command line flags
	repoPath := flag.String("repo", "/opt/ulpf-config.git", "Path to bare git repository")
	secretsDir := flag.String("secrets", "/etc/ulpf/secrets", "Directory containing secret files")
	addr := flag.String("addr", ":8080", "HTTP listen address")
	statusFile := flag.String("status-file", "/data/fleet-status.json", "Fleet status JSON file")
	flag.Parse()
	
	// Open git repository
	repo, err := git.NewRepo(*repoPath)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Failed to open repo: %v\n", err)
		os.Exit(1)
	}
	
	// Get initial HEAD
	head, err := repo.HEADCommit()
	if err != nil {
		fmt.Fprintf(os.Stderr, "Failed to get HEAD: %v\n", err)
		os.Exit(1)
	}
	fmt.Printf("Config server starting with HEAD: %s\n", head)
	
	// Create bundle builder
	bundleBuilder := config.NewBundleBuilder(repo, *secretsDir)
	
	// Create auth manager
	authManager := auth.NewManager()
	
	// Load tokens from environment or files
	loadTokens(authManager)
	
	// Create and start server
	server := http.NewServer(repo, bundleBuilder, authManager, *statusFile)
	
	fmt.Printf("Starting config server on %s\n", *addr)
	if err := server.Start(*addr); err != nil {
		fmt.Fprintf(os.Stderr, "Server error: %v\n", err)
		os.Exit(1)
	}
}

// loadTokens loads authentication tokens from environment
func loadTokens(m *auth.Manager) {
	// Admin token from env
	if adminToken := os.Getenv("ADMIN_TOKEN"); adminToken != "" {
		m.AddAdminToken(adminToken)
		fmt.Println("Loaded admin token from environment")
	}
	
	// Agent tokens from env (comma-separated: token:machine_id1,machine_id2:site_id)
	if agentTokens := os.Getenv("AGENT_TOKENS"); agentTokens != "" {
		// Format: token1:machine1,machine2:site1;token2:machine3:site2
		// For simplicity, we'll use a basic format
		fmt.Println("AGENT_TOKENS parsing not fully implemented, using defaults")
	}
	
	// Default tokens for development
	m.AddAgentToken("collector-a-token", []string{"collector-a-01"}, "kol-dc1")
	m.AddAgentToken("collector-b-token", []string{"collector-b-01"}, "kol-dc1")
	m.AddAgentToken("collector-c-token", []string{"collector-c-01"}, "kol-dc1")
	m.AddAgentToken("central-token", []string{"central-01"}, "kol-dc1")
	m.AddAdminToken("admin-token")
	
	fmt.Println("Loaded default development tokens")
}