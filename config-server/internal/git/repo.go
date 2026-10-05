package git

import (
	"fmt"
	"os"
	"path/filepath"
	"strings"
	"time"

	"github.com/go-git/go-git/v5"
	"github.com/go-git/go-git/v5/plumbing"
	"github.com/go-git/go-git/v5/plumbing/object"
)

// Repo wraps a git repository for config operations
type Repo struct {
	path string
	repo *git.Repository
}

// NewRepo opens a git repository at the given path
func NewRepo(path string) (*Repo, error) {
	r, err := git.PlainOpen(path)
	if err != nil {
		return nil, fmt.Errorf("failed to open repo at %s: %w", path, err)
	}
	return &Repo{path: path, repo: r}, nil
}

// HEADCommit returns the current HEAD commit hash
func (r *Repo) HEADCommit() (string, error) {
	head, err := r.repo.Head()
	if err != nil {
		return "", fmt.Errorf("failed to get HEAD: %w", err)
	}
	return head.Hash().String(), nil
}

// GetFileAtCommit returns the content of a file at a specific commit
func (r *Repo) GetFileAtCommit(commitHash, filePath string) (string, error) {
	commit, err := r.repo.CommitObject(plumbing.NewHash(commitHash))
	if err != nil {
		return "", fmt.Errorf("failed to get commit %s: %w", commitHash, err)
	}

	tree, err := commit.Tree()
	if err != nil {
		return "", fmt.Errorf("failed to get tree: %w", err)
	}

	file, err := tree.File(filePath)
	if err != nil {
		return "", fmt.Errorf("file %s not found at commit %s: %w", filePath, commitHash, err)
	}

	return file.Contents()
}

// ListFilesAtCommit lists all files at a specific commit matching a pattern
func (r *Repo) ListFilesAtCommit(commitHash, prefix string) ([]string, error) {
	commit, err := r.repo.CommitObject(plumbing.NewHash(commitHash))
	if err != nil {
		return nil, fmt.Errorf("failed to get commit %s: %w", commitHash, err)
	}

	tree, err := commit.Tree()
	if err != nil {
		return nil, fmt.Errorf("failed to get tree: %w", err)
	}

	var files []string
	err = tree.Files().ForEach(func(f *object.File) error {
		if strings.HasPrefix(f.Name, prefix) && strings.HasSuffix(f.Name, ".yaml") {
			files = append(files, f.Name)
		}
		return nil
	})
	if err != nil {
		return nil, err
	}
	return files, nil
}

// GetConfigDirsAtCommit returns the config directories (site/collector combinations) at a commit
func (r *Repo) GetConfigDirsAtCommit(commitHash string) ([]string, error) {
	files, err := r.ListFilesAtCommit(commitHash, "sites/")
	if err != nil {
		return nil, err
	}

	dirs := make(map[string]bool)
	for _, f := range files {
		// Extract directory path: sites/kol-dc1/collector-a/vector.yaml -> sites/kol-dc1/collector-a
		parts := strings.Split(f, "/")
		if len(parts) >= 3 {
			dir := strings.Join(parts[:len(parts)-1], "/")
			dirs[dir] = true
		}
	}

	result := make([]string, 0, len(dirs))
	for d := range dirs {
		result = append(result, d)
	}
	return result, nil
}

// CheckoutToDir checks out a commit to a temporary directory for validation
func (r *Repo) CheckoutToDir(commitHash, destDir string) error {
	// Just copy files manually
	return r.copyFilesToDir(commitHash, destDir)
}

// copyFilesToDir copies all files from a commit to a directory
func (r *Repo) copyFilesToDir(commitHash, destDir string) error {
	commit, err := r.repo.CommitObject(plumbing.NewHash(commitHash))
	if err != nil {
		return err
	}

	tree, err := commit.Tree()
	if err != nil {
		return err
	}

	return tree.Files().ForEach(func(f *object.File) error {
		destPath := filepath.Join(destDir, f.Name)
		if err := os.MkdirAll(filepath.Dir(destPath), 0755); err != nil {
			return err
		}
		content, err := f.Contents()
		if err != nil {
			return err
		}
		return os.WriteFile(destPath, []byte(content), 0644)
	})
}

// GetCommitTime returns the commit timestamp
func (r *Repo) GetCommitTime(commitHash string) (time.Time, error) {
	commit, err := r.repo.CommitObject(plumbing.NewHash(commitHash))
	if err != nil {
		return time.Time{}, err
	}
	return commit.Committer.When, nil
}