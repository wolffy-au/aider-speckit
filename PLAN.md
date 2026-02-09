# PLAN

* **Add broader edge-case and failure-path tests**
  Cover missing spec-kit directories, malformed front matter, empty or missing placeholders, and `/spec` interactions with `self.coder.run` failure paths.

## TODO

* Watch templates/commands/
* Invalidate registry cache on change
* Or add /spec reload

Optionally inspect:

* Raw template text
* Rendered prompt
* Substitution map

---

## Feature: Spec-Kit Template Discovery

**Description**
The system discovers spec-kit command templates from a filesystem location and makes them available to the CLI.

**Capabilities**

* Resolve the spec-kit root directory from:

  * Explicit CLI arguments
  * Environment variables
  * Default repository layout
* Scan the `templates/commands/` directory (including supported subdirectories) for Markdown files
* Ignore non-Markdown files and unreadable files
* Detect when no valid templates are present

**Observable Behaviors**

* Templates are discovered lazily or on first access
* The system can report whether any templates exist
* Errors during discovery (missing directory, unreadable path) are surfaced as warnings or errors

---

## Feature: Markdown Template Parsing

**Description**
Each spec-kit Markdown file is parsed into a structured template representation.

**Capabilities**

* Read Markdown files containing optional YAML front matter
* Split front matter and body content reliably
* Parse YAML front matter using a safe loader, with fallback behavior if YAML parsing fails
* Capture and normalize metadata fields, including:

  * Identifier / id
  * Title
  * Description
  * Version
  * Arguments
  * Scripts
  * Handoffs
  * Aliases
* Deduplicate and trim list-like metadata fields
* Handle missing or malformed front matter gracefully

**Observable Behaviors**

* Malformed YAML produces a warning or error without crashing the process
* Missing optional metadata results in defaults
* Missing required metadata produces a validation warning (treated as non-fatal, see below)
* Parsed templates expose both raw and derived attributes

---

## Feature: Placeholder Detection and Validation

**Description**
Templates may declare placeholders that must be replaced at execution time.

**Capabilities**

* Detect placeholders in the template body (e.g. `$ARGUMENTS`, `$FOO`)
* Record which placeholders are present per template
* Distinguish between required and optional placeholders
* Validate whether required placeholders are provided at render time

**Observable Behaviors**

* Missing required placeholders generate warnings or errors before execution
* Extra user input that is not consumed by placeholders is either ignored or warned about
* Empty placeholder values can be detected and flagged

---

## Feature: Template Rendering

**Description**
A parsed template can be rendered into a final prompt for execution.

**Capabilities**

* Replace placeholders with user-provided arguments
* Preserve all non-placeholder content verbatim
* Cache rendered results per template + input combination if enabled
* Re-render deterministically for the same inputs

**Observable Behaviors**

* Rendering produces a complete prompt string
* Rendering failures are reported clearly and not treated as fatal
* Cached renders avoid repeated parsing work when invoked multiple times

---

## Feature: Spec-Kit Registry Lookup

**Description**
All parsed templates are indexed and retrievable via multiple identifiers.

**Capabilities**

* Build a registry index keyed by:

  * Template id
  * Slugified filename
  * Relative path
  * Aliases
* Perform case-insensitive lookups
* Detect and handle identifier collisions
* Provide a sorted list of templates for display

**Observable Behaviors**

* Looking up a valid identifier returns the expected template
* Looking up an unknown identifier produces a user-facing error
* Listing templates returns stable, predictable ordering

---

## Feature: `/spec` Command – Listing Templates

**Description**
Users can list available spec-kit templates via the CLI.

**Capabilities**

* `/spec` or `/spec list` displays all discovered templates
* Each entry includes identifier and description (if present)
* Handles empty registries gracefully

**Observable Behaviors**

* The list output is visible via standard CLI output
* Templates without descriptions are still listed with a fallback label
* Errors during registry loading are surfaced

---

## Feature: `/spec` Command – Executing a Template

**Description**
Users can execute a spec-kit template through the `/spec` command.

**Capabilities**

* Accept a template identifier and optional argument string
* Validate that the identifier exists
* Render the template with provided arguments
* Validate required metadata (e.g. scripts, handoffs) before execution
* Warn about missing or malformed inputs
* Invoke `self.coder.run()` with the rendered prompt

**Observable Behaviors**

* Invalid identifiers result in immediate user-facing errors
* Validation warnings are shown before execution
* The rendered prompt is executed through the standard coder flow
* Execution failures are surfaced clearly

---

## Feature: Metadata Reporting After Execution

**Description**
After a template is executed, relevant metadata is reported back to the user.

**Capabilities**

* Display scripts to run, handoffs to trigger, and version information
* Include the template’s source file path when appropriate
* Summarize execution results (e.g. next steps)

**Observable Behaviors**

* Metadata is output via `tool_output` or equivalent UI channel
* Missing metadata is omitted without errors
* Output appears after execution completes

---

## Feature: CLI Autocomplete and Help Integration

**Description**
Spec-kit templates are discoverable via CLI help and autocomplete.

**Capabilities**

* Include `/spec` in general help output
* Show available template identifiers in autocomplete
* Optionally expose template descriptions in help text

**Observable Behaviors**

* `/help` mentions `/spec` and how to use it
* Autocomplete suggestions reflect the current registry state
* Changes in templates are reflected after reload or restart

---

## Feature: Error Handling and Diagnostics

**Description**
The system provides actionable diagnostics for spec-kit failures.

**Capabilities**

* Log or surface errors for:

  * Missing spec-kit directories
  * Unreadable files
  * Malformed front matter
  * YAML parsing failures
* Distinguish between warnings and fatal errors
* Treat absence of required metadata as warnings

**Observable Behaviors**

* Users receive clear messages without needing to rerun commands
* Non-fatal errors do not prevent other templates from loading
* Fatal errors stop execution cleanly

---

## Feature: Testing and Failure Path Coverage

**Description**
The implementation is covered by automated tests for both success and failure scenarios.

**Capabilities**

* Unit tests for:

  * Template parsing
  * Metadata normalization
  * Placeholder rendering
  * Registry lookup and listing
* Integration tests for:

  * `/spec` command workflow
  * Interaction with `self.coder.run`
* Mocked dependencies where appropriate

**Observable Behaviors**

* Error paths (missing directories, malformed templates, empty placeholders) are explicitly tested
* Command behavior is validated independently of actual coder execution

---
