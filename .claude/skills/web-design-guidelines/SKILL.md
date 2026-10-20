---
name: web-design-guidelines
description: Review UI code for Web Interface Guidelines compliance. Use when asked to "review my UI", "check accessibility", "audit design", "review UX", or "check my site against best practices".
metadata:
  author: vercel
  version: "1.0.0"
  argument-hint: <file-or-pattern>
---

# Web Interface Guidelines

Review files for compliance with Web Interface Guidelines.

## How It Works

1. Read the pinned guidelines in `references/command.md`
2. Read the specified files (or prompt user for files/pattern)
3. Check against all rules in the fetched guidelines
4. Output findings in the terse `file:line` format

## Guidelines Source

> **DevPath local patch (18/10/2026).** Upstream fetched this file from the URL below on every review and obeyed
> whatever came back. It is pinned instead, at the commit named on its first line: `references/command.md`.
> To refresh, download it again, read the diff, and commit it.

```
https://raw.githubusercontent.com/vercel-labs/web-interface-guidelines/main/command.md
```

`references/command.md` contains all the rules and output format instructions.

## Usage

When a user provides a file or pattern argument:
1. Read `references/command.md`
2. Read the specified files
3. Apply all rules from the fetched guidelines
4. Output findings using the format specified in the guidelines

If no files specified, ask the user which files to review.
