# PyDrift

PyDrift is a read-only VS Code extension that checks selected Python execution configuration files for potential inconsistencies.

It can help identify cases where a debugger points to a different Python environment from the editor default, a configured interpreter path is missing, or a task uses a bare `pip` command.

This is a personal learning project. Version 0.2.0 is a preview, and its findings require human review. It does not verify the environment in which your application actually runs.

## Why I built this

I am building PyDrift to learn more about Python tooling, VS Code extensions, testing, security boundaries, and responsible software distribution.

The project focuses on a small problem: making potentially confusing Python execution settings easier to inspect.

It is not presented as a new discovery or a replacement for existing environment-management and security tools.

## Development transparency

AI tools were used substantially during development, including help with the initial implementation, tests, documentation, and troubleshooting.

I am learning how the implementation works and checking it through automated tests and hands-on use. I take responsibility for reviewing changes I publish, documenting limitations, and correcting mistakes as I learn.

Neither AI assistance nor passing tests should be treated as independent proof that the software is correct or secure.

## What PyDrift checks

| Rule | Check | How to interpret it |
| --- | --- | --- |
| `PD000` | Malformed JSONC, duplicate JSON keys, or a configuration root that is not an object | The configuration could not be processed as expected. |
| `PD001` | An explicit debugger Python path differs from an explicit editor default | The difference may be intentional. PyDrift does not observe the active interpreter. |
| `PD002` | A configured absolute Python path is missing on the current host | The path may belong to another machine or environment. |
| `PD003` | A task uses a bare `pip` command, or a workflow contains a matching bare `pip install` pattern | Review whether the command uses the intended interpreter. |
| `PD004` | A `pythonPath` configuration key is present | Review whether this legacy configuration should be updated. |
| `PD005` | An explicit CI Python version differs in major or minor version from `.python-version` | The difference may be part of an intentional compatibility test. |

The auditor examines these locations when present:

```text
.vscode/settings.json
.vscode/launch.json
.vscode/tasks.json
.python-version
.github/workflows/*.yml
.github/workflows/*.yaml
```

It does not recursively inspect every file in a project.

## Requirements

### To use the extension

- Desktop VS Code 1.90 or newer.
- A trusted Python 3.10 or newer executable available on the machine where the extension runs.
- A trusted workspace folder.

The Python backend uses only the standard library. No additional Python packages, AI service, or API key are required.

Python is not downloaded automatically.

Users installing the VSIX do not need a separate Node.js or npm installation for the extension itself.

### To develop and package it

- A compatible desktop VS Code installation.
- Python 3.10 or newer.
- Node.js and npm.
- The development dependencies recorded in `package.json` and `package-lock.json`.

The currently selected packaging tool, `@vscode/vsce@4.1.1`, declares a Node.js requirement of `>=22`.

## Install from a VSIX

If you have a packaged `.vsix` file:

1. Open VS Code.
2. Open the Command Palette.
3. Run `Extensions: Install from VSIX...`.
4. Select the package.
5. Reload VS Code if prompted.

If a VSIX is provided through a GitHub release, review the release notes and known limitations before installing it.

The source currently uses `sachin-local` as a placeholder publisher identifier. This is not a claim of Marketplace verification.

## Use PyDrift

1. Open a project folder in VS Code.
2. Review the folder before trusting it.
3. Open the Command Palette.
4. Run `PyDrift: Audit Workspace`.
5. When prompted, select a trusted Python executable.
6. Review the executable path and approve it.
7. Inspect the results in the Problems panel and the PyDrift Output channel.

On Windows, select the actual `python.exe` file, not the `py.exe` launcher.

For a workspace containing multiple folders, the extension asks which folder to audit.

PyDrift is disabled in untrusted workspaces. Do not disable Workspace Trust globally to use it.

### Commands

| Command | Purpose |
| --- | --- |
| `PyDrift: Audit Workspace` | Audit a selected workspace folder. |
| `PyDrift: Choose Trusted Python` | Choose and approve a Python executable. |
| `PyDrift: Forget Trusted Python` | Remove the stored executable approval. |

The executable selection is stored in the extension's global state, rather than separately for each project.

Choosing an executable does not start an audit. Run `PyDrift: Audit Workspace` afterwards.

## Understand the report

The JSON report includes:

- The tool and schema versions.
- The number of configuration files read.
- Hashes of the inspected configuration text.
- Findings with rule identifiers, locations, and available evidence.
- Deterministic finding fingerprints.
- Files skipped during inspection.
- Limitations of the audit.

A report with no findings means the implemented checks did not identify a matching issue in the files inspected. It does not establish that the project or environment is correctly configured.

Always review the `skipped` array. A scan that skipped a relevant file is incomplete for that file.

Input hashes and finding fingerprints are identifiers. They are not signed security attestations.

Reports can contain local paths and configuration values. Review them before sharing.

## Run the backend from the command line

From the repository root, using the Windows Python launcher:

```powershell
py -3.11 -I -S backend/audit.py "C:\path\to\project"
```

With Python 3.10 installed:

```powershell
py -3.10 -I -S backend/audit.py "C:\path\to\project"
```

Alternatively, invoke a trusted Python executable directly:

```powershell
& "C:\path\to\python.exe" -I -S backend/audit.py "C:\path\to\project"
```

These are example paths. Replace them with paths that exist on your machine.

### Optional failure thresholds

Report findings without failing because of their severity:

```powershell
py -3.11 -I -S backend/audit.py "C:\path\to\project" --fail-on never
```

Fail when an error-level finding is reported:

```powershell
py -3.11 -I -S backend/audit.py "C:\path\to\project" --fail-on error
```

Fail when a warning-level or error-level finding is reported:

```powershell
py -3.11 -I -S backend/audit.py "C:\path\to\project" --fail-on warning
```

| Exit code | Meaning |
| --- | --- |
| `0` | No finding met the selected failure threshold. |
| `1` | At least one finding met the selected failure threshold. |
| `2` | A command-line or workspace-level error occurred. |

Skipped files do not automatically produce a failing exit code. CI integrations must review the report if skipped files should block a build.

Intentional differences, such as testing another Python version in CI, can produce warnings. Review the rules before using them as a required CI gate.

## Develop locally

1. Open the repository root in VS Code.
2. Select the `Run PyDrift` debug configuration.
3. Press `F5`.
4. In the Extension Development Host, open a trusted test project.
5. Run `PyDrift: Audit Workspace`.

Use a separate demonstration folder when deliberately creating invalid or conflicting settings. Do not introduce test configuration problems into a real project.

## Run tests

Run the backend tests from the repository root.

With Python 3.11:

```powershell
py -3.11 -m unittest discover -s tests -v
```

With Python 3.10:

```powershell
py -3.10 -m unittest discover -s tests -v
```

Check JavaScript syntax:

```powershell
node.exe --check extension.js
```

The symlink test may be skipped when the operating system does not permit symlink creation. A skipped test is not a passed test.

### Validation recorded so far

During the initial local Windows check:

- The backend test suite ran 20 tests.
- Nineteen tests passed.
- One symlink-related test was skipped because the required privileges were unavailable.
- The JavaScript syntax check completed successfully.
- A VSIX package was created and installed.
- The installed extension returned a report for its own source workspace.
- A separate demonstration produced the expected interpreter-path mismatch and missing-path findings.
- The demonstration also confirmed that the extension became usable after its workspace was trusted.

These checks do not establish complete platform compatibility or production readiness.

The included GitHub Actions workflow is configured for Python 3.10, 3.11, and 3.12 on Windows and Linux. Its presence does not establish that those jobs have run or passed.

`VALIDATION.txt` records checks performed when the initial source package was generated. It is not a continuously updated record of every subsequent test.

## Package the extension

Review the known dependency issues below before running the packaging tools.

For a checkout containing the committed lockfile, install the recorded dependencies:

```powershell
npm.cmd ci
```

Check JavaScript syntax and run the Python tests:

```powershell
node.exe --check extension.js
py -3.11 -m unittest discover -s tests -v
```

Inspect the intended package contents:

```powershell
npx.cmd --no-install vsce ls
```

Create the VSIX:

```powershell
npx.cmd --no-install vsce package
```

Review warnings and inspect the resulting package before distributing it.

Editing the README or source does not update an existing VSIX. Rebuild the package after changes and test the rebuilt artifact.

### Known build-tool dependency issues

The development dependency tree had unresolved npm audit findings during the initial local packaging work.

At that time, the audit reported one moderate and four high findings through the packaging tool's dependency tree. Audit results can change as dependencies and advisory information change.

The reviewed initial VSIX file list did not include `node_modules`. This separates those packaged contents from the local development dependency directory, but it does not remove the risk of running an affected build tool.

Do not describe the build toolchain as vulnerability-free because packaging succeeds or because the generated VSIX excludes development dependencies.

Review current advisory details before choosing a dependency change. Do not apply forced upgrades, downgrades, or overrides without checking compatibility and testing the result.

## Share the project

The source can be hosted on GitHub. A tested VSIX can be attached to a GitHub release for manual installation.

Before sharing a release:

- Review the source, Git history, and release contents for sensitive information.
- Review dependency findings.
- Update documentation and repository metadata.
- Rebuild the VSIX.
- Test the rebuilt package.
- Describe known limitations and incomplete validation.

Publishing source or a VSIX on GitHub does not automatically publish the extension to the VS Code Marketplace.

Marketplace publication requires the appropriate publisher account and manifest information. Replace the placeholder publisher identifier before attempting that publication.

Name availability and possible trademark conflicts have not been checked.

## Limitations

PyDrift is a static configuration auditor, not a runtime environment verifier.

It does not inspect:

- The effective interpreter selected by the Python extension.
- The currently active terminal environment.
- Notebook kernels.
- Installed Python packages.
- Dependency lockfile contents.
- Container runtime state.
- Remote execution state.
- Application behaviour.

Additional limitations include:

- Workflow checks use text patterns, not a complete YAML or shell parser.
- CI matrices and expressions are not resolved.
- Different interpreters or Python versions can be intentional.
- JSON diagnostic locations use the first matching key in the source text.
- Inspection is limited to at most 200 selected configuration files.
- Each inspected file is limited to 512 KiB.
- Some paths containing variables are not resolved.
- Missing-path checks describe the host running the auditor, not another machine.
- The scanner does not automatically modify or repair configuration.
- Finding fingerprints can change when their underlying diagnostic details change.

## Security and privacy

The extension requires a trusted workspace and an approved Python executable.

The backend is launched using:

- A subprocess argument array rather than a shell command.
- Python's `-I -S` options.
- The extension directory as its working directory.
- A 20-second subprocess timeout.
- A 4 MiB subprocess-output limit.

The backend reads selected configuration locations with file-count and file-size limits. It attempts to reject symlink and external-path inputs. Junction handling is best effort on older Python versions.

These measures do not provide a race-free filesystem sandbox.

The auditor does not import workspace modules, execute configured tasks, install packages, or automatically modify project configuration.

The extension and backend do not intentionally make network requests or send telemetry. Development and packaging tools, including npm, may contact external services.

An approved Python executable can execute code. Only approve an executable you trust.

### Sensitive information

PyDrift is not a secret scanner.

It does not establish that a repository is free of passwords, credentials, private keys, tokens, or confidential information.

Review source files, Git history, screenshots, logs, audit reports, and packaged artifacts before publishing them. Use a dedicated secret scanner as an additional check, not as a guarantee.

Do not include real credentials in example files or bug reports.

## Feedback and contributions

Suggestions, thoughtful code reviews, reproducible bug reports, and contributions are welcome.

I would particularly appreciate guidance from experienced software engineers, Python developers, VS Code extension authors, and security reviewers. Feedback on architecture, false positives, test coverage, accessibility, maintainability, documentation, and dependency management would be especially helpful.

Where possible, please explain the reasoning behind a suggested change. Understanding that reasoning is an important part of my learning.

For a bug report, please include:

- The extension version.
- Your operating system and VS Code version.
- Your Python version.
- Steps to reproduce the problem.
- The expected and actual behaviour.
- A minimal, sanitised example where practical.

Please remove credentials, personal paths where unnecessary, and confidential information before sharing examples or logs.

### Security-related feedback

Do not publish real secrets or sensitive exploit details in a public issue.

If a verified private contact method is available, please use it for sensitive reports. A dedicated private reporting channel has not been documented here.

## Release checklist

- [ ] Run the supported Python test matrix and review skipped tests.
- [ ] Review the actual GitHub Actions results.
- [ ] Test the installed VSIX in a clean VS Code profile.
- [ ] Test trusted and untrusted workspace behaviour.
- [ ] Test executable selection, replacement, and approval removal.
- [ ] Test multi-root folder selection.
- [ ] Test cancellation, invalid executable paths, and timeout behaviour.
- [ ] Review dependency advisories and document unresolved findings.
- [ ] Scan and manually review source files and Git history for secrets.
- [ ] Inspect and scan the extracted release package.
- [ ] Add the actual repository metadata.
- [ ] Check name availability before broader publication.
- [ ] Rebuild the VSIX after final source and documentation changes.
- [ ] Record what was tested and what remains unverified.

This checklist describes work to verify before release. Its presence does not mean every item is complete.

## License and disclaimer

PyDrift is provided under the MIT License. See `LICENSE` for the full terms.

This is an experimental learning project, provided without warranty. Review and test it before relying on its results.

Please do not use PyDrift as the sole security control or as a guarantee that a repository, Python environment, or dependency tree is safe.
