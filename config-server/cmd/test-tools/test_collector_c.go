package main

import (
	"fmt"
	"ulpf-config-server/internal/config"
	"ulpf-config-server/internal/git"
)

func main() {
	repo, _ := git.NewRepo("/home/paul/projects/sih2/config-repo")
	builder := config.NewBundleBuilder(repo, "/home/paul/projects/sih2/config-server/secrets")
	
	bundle, err := builder.BuildBundle("f02d2bb64311d8155d83a13544eb0d0f1dff9ceb", "kol-dc1", "collector-c-01", "collector-c")
	if err != nil {
		fmt.Println("BuildBundle error:", err)
		return
	}
	
	fmt.Printf("Bundle files: %d\n", len(bundle.Files))
	for k, v := range bundle.Files {
		fmt.Printf("  %s: %d bytes\n", k, len(v))
	}
	
	merged, err := builder.MergeBundle(bundle)
	if err != nil {
		fmt.Println("Merge error:", err)
		return
	}
	
	fmt.Printf("Merged YAML:\n%s\n", merged)
}
