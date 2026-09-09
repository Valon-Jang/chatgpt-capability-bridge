package main

import (
    "fmt"
    "os"
    "strings"

    "github.com/kay-ws/ovba-writer/vbaproject"
)

func crlf(s string) string {
    s = strings.ReplaceAll(s, "\r\n", "\n")
    s = strings.ReplaceAll(s, "\r", "\n")
    return strings.ReplaceAll(s, "\n", "\r\n")
}

func main() {
    if len(os.Args) != 5 {
        panic("usage: patch_vba template.bin Module1.bas ThisWorkbook.cls output.bin")
    }
    raw, err := os.ReadFile(os.Args[1])
    if err != nil { panic(err) }
    moduleSrc, err := os.ReadFile(os.Args[2])
    if err != nil { panic(err) }
    workbookSrc, err := os.ReadFile(os.Args[3])
    if err != nil { panic(err) }

    proj, err := vbaproject.Read(raw)
    if err != nil { panic(err) }
    foundModule := false
    foundWorkbook := false
    for i := range proj.Modules {
        switch proj.Modules[i].Name {
        case "Module1":
            proj.Modules[i].Source = crlf(string(moduleSrc))
            foundModule = true
        case "ThisWorkbook":
            proj.Modules[i].Source = crlf(string(workbookSrc))
            foundWorkbook = true
        }
    }
    if !foundModule || !foundWorkbook {
        names := make([]string, 0, len(proj.Modules))
        for _, m := range proj.Modules { names = append(names, m.Name) }
        panic(fmt.Sprintf("required modules missing: Module1=%v ThisWorkbook=%v modules=%v", foundModule, foundWorkbook, names))
    }

    out, err := vbaproject.Write(proj)
    if err != nil { panic(err) }
    if err := os.WriteFile(os.Args[4], out, 0644); err != nil { panic(err) }

    check, err := vbaproject.Read(out)
    if err != nil { panic(err) }
    okCore := false
    okOpen := false
    for _, m := range check.Modules {
        if m.Name == "Module1" && strings.Contains(m.Source, "Public Sub InitNaming()") && strings.Contains(m.Source, "Public Sub ToggleVote") {
            okCore = true
        }
        if m.Name == "ThisWorkbook" && strings.Contains(m.Source, "Private Sub Workbook_Open()") && strings.Contains(m.Source, "Workbook_SheetFollowHyperlink") {
            okOpen = true
        }
    }
    if !okCore || !okOpen {
        panic(fmt.Sprintf("VBA readback failed: core=%v workbook=%v", okCore, okOpen))
    }
    fmt.Printf("VBA readback PASS: modules=%d bytes=%d\n", len(check.Modules), len(out))
}
