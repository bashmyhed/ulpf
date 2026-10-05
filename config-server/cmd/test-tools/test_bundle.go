package main

import (
	"fmt"
	"ulpf-config-server/internal/git"
)

func main() {
	repo, err := git.NewRepo("/home/paul/projects/sih2/config-repo")
	if err != nil {
		fmt.Println("Error opening repo:", err)
		return
	}
	
	head, _ := repo.HEADCommit()
	fmt.Println("HEAD:", head)
	
	files, err := repo.ListFilesAtCommit(head, "sites/")
	if err != nil {
		fmt.Println("Error listing files:", err)
		return
	}
	fmt.Println("Files under sites/:")
	for _, f := range files {
		fmt.Println("  ", f)
	}
	
	dirs, err := repo.GetConfigDirsAtCommit(head)
	if err != nil {
		fmt.Println("Error getting dirs:", err)
		return
	}
	fmt.Println("Config dirs:")
	for _, d := range dirs {
		fmt.Println("  ", d)
	}
	
	content, err := repo.GetFileAtCommit(head, "sites/kol-dc1/collector-a/vector.yaml")
	if err != nil {
		fmt.Println("Error getting file:", err)
	} else {
		fmt.Println("File content length:", len(content))
	}
}
