package auth

import (
	"net/http"
	"strings"
	"sync"

	"github.com/gin-gonic/gin"
)

// Manager handles authentication
type Manager struct {
	mu          sync.RWMutex
	agentTokens map[string]AgentToken // token -> AgentToken
	adminTokens map[string]bool       // token -> true
}

// AgentToken represents an agent's token and permissions
type AgentToken struct {
	Token      string
	MachineIDs []string
	SiteID     string
}

// NewManager creates a new auth manager
func NewManager() *Manager {
	return &Manager{
		agentTokens: make(map[string]AgentToken),
		adminTokens: make(map[string]bool),
	}
}

// AddAgentToken adds an agent token
func (m *Manager) AddAgentToken(token string, machineIDs []string, siteID string) {
	m.mu.Lock()
	defer m.mu.Unlock()
	m.agentTokens[token] = AgentToken{
		Token:      token,
		MachineIDs: machineIDs,
		SiteID:     siteID,
	}
}

// AddAdminToken adds an admin token
func (m *Manager) AddAdminToken(token string) {
	m.mu.Lock()
	defer m.mu.Unlock()
	m.adminTokens[token] = true
}

// IsAgentToken checks if a token is a valid agent token
func (m *Manager) IsAgentToken(token string) bool {
	m.mu.RLock()
	defer m.mu.RUnlock()
	_, ok := m.agentTokens[token]
	return ok
}

// IsAdminToken checks if a token is a valid admin token
func (m *Manager) IsAdminToken(token string) bool {
	m.mu.RLock()
	defer m.mu.RUnlock()
	return m.adminTokens[token]
}

// Middleware returns the authentication middleware
func (m *Manager) Middleware() gin.HandlerFunc {
	return func(c *gin.Context) {
		// Skip auth for health check
		if c.Request.URL.Path == "/health" {
			c.Next()
			return
		}

		token := extractToken(c)
		if token == "" {
			c.AbortWithStatusJSON(http.StatusUnauthorized, gin.H{"error": "missing authorization token"})
			return
		}

		m.mu.RLock()
		agentToken, isAgent := m.agentTokens[token]
		isAdmin := m.adminTokens[token]
		m.mu.RUnlock()

		if isAgent {
			c.Set("agent_token", &agentToken)
			c.Next()
			return
		}

		if isAdmin {
			c.Set("admin_token", true)
			c.Next()
			return
		}

		c.AbortWithStatusJSON(http.StatusUnauthorized, gin.H{"error": "invalid token"})
	}
}

// AdminMiddleware returns middleware that requires admin token
func (m *Manager) AdminMiddleware() gin.HandlerFunc {
	return func(c *gin.Context) {
		token := extractToken(c)
		if token == "" || !m.IsAdminToken(token) {
			c.AbortWithStatusJSON(http.StatusForbidden, gin.H{"error": "admin access required"})
			return
		}
		c.Next()
	}
}

// extractToken extracts the Bearer token from Authorization header
func extractToken(c *gin.Context) string {
	auth := c.GetHeader("Authorization")
	if auth == "" {
		return ""
	}

	parts := strings.SplitN(auth, " ", 2)
	if len(parts) != 2 || strings.ToLower(parts[0]) != "bearer" {
		return ""
	}

	return parts[1]
}