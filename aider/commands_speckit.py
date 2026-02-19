import json
import os
import re
import subprocess
from datetime import datetime
from pathlib import Path

SHORT_NAME_STOP_WORDS = {
    "i",
    "a",
    "an",
    "the",
    "to",
    "for",
    "of",
    "in",
    "on",
    "at",
    "by",
    "with",
    "from",
    "is",
    "are",
    "was",
    "were",
    "be",
    "been",
    "being",
    "have",
    "has",
    "had",
    "do",
    "does",
    "did",
    "will",
    "would",
    "should",
    "could",
    "can",
    "may",
    "might",
    "must",
    "shall",
    "this",
    "that",
    "these",
    "those",
    "my",
    "your",
    "our",
    "their",
    "want",
    "need",
    "add",
    "get",
    "set",
}


class SpeckitCommandsMixin:
    def cmd_speckit_constitution(self, args):
        "Populate the speckit constitution template into .specify/memory."

        template_rel = ".aider/commands/speckit.constitution.md"
        template_path = self.coder.abs_root_path(template_rel)

        read_only_targets = [
            template_path,
            self.coder.abs_root_path(".specify/templates/plan-template.md"),
            self.coder.abs_root_path(".specify/templates/spec-template.md"),
            self.coder.abs_root_path(".specify/templates/tasks-template.md"),
        ]
        for target in read_only_targets:
            self._add_read_only(target)

        if not os.path.exists(template_path):
            self.io.tool_error("Template .aider/commands/speckit.constitution.md not found.")
            return

        try:
            with open(template_path, "r", encoding=self.io.encoding) as f:
                template = f.read()
        except Exception as err:
            self.io.tool_error(f"Unable to read {template_rel}: {err}")
            return

        arguments = args.strip()
        prompt = template.replace("$ARGUMENTS", arguments)

        constitution_path = self.coder.abs_root_path(".specify/memory/constitution.md")
        if os.path.exists(constitution_path):
            try:

                rel_constitution = self.coder.get_rel_fname(constitution_path)
                if rel_constitution:
                    self.coder.add_rel_fname(rel_constitution)
                elif constitution_path not in self.coder.abs_fnames:
                    self.coder.abs_fnames.add(constitution_path)
                self.coder.check_added_files()

                with open(constitution_path, "r", encoding=self.io.encoding) as f:
                    existing_content = f.read()
                prompt += f"\n\nExisting constitution content:\n\n{existing_content}"
            except Exception as err:
                self.io.tool_error(f"Unable to read existing constitution: {err}")

        from aider.coders.base_coder import Coder

        coder = Coder.create(
            io=self.io,
            from_coder=self.coder,
            edit_format=self.coder.main_model.edit_format,
            summarize_from_coder=False,
        )
        response = coder.run(prompt)

        if not response:
            self.io.tool_error("Unable to generate constitution from template.")
            return

        sanitized_response = self._sanitize_constitution_text(response)

        memory_dir = self.coder.abs_root_path(".specify/memory")
        os.makedirs(memory_dir, exist_ok=True)

        constitution_path = self.coder.abs_root_path(".specify/memory/constitution.md")
        self.io.write_text(constitution_path, sanitized_response)

        rel_constitution = self.coder.get_rel_fname(constitution_path)
        if rel_constitution:
            self.coder.add_rel_fname(rel_constitution)
        elif constitution_path not in getattr(self.coder, "abs_fnames", set()):
            self.coder.abs_fnames.add(constitution_path)
        self.coder.check_added_files()

        self.io.tool_output("Updated .specify/memory/constitution.md with the assistant response.")

        self.coder.cur_messages += [
            dict(role="user", content=prompt),
            dict(role="assistant", content=sanitized_response),
        ]

    def cmd_speckit_specify(self, args):
        "Create or update a feature specification via the speckit specify workflow."

        template_rel = ".aider/commands/speckit.specify.md"
        template_path = self.coder.abs_root_path(template_rel)

        read_only_targets = [
            template_path,
            self.coder.abs_root_path(".specify/scripts/bash/create-new-feature.sh"),
            self.coder.abs_root_path(".specify/templates/spec-template.md"),
            self.coder.abs_root_path(".specify/templates/checklist-template.md"),
        ]
        for target in read_only_targets:
            self._add_read_only(target)

        if not os.path.exists(template_path):
            self.io.tool_error("Template .aider/commands/speckit.specify.md not found.")
            return

        description = args.strip()
        if not description:
            self.io.tool_error("Please provide a feature description for /speckit.specify.")
            return

        template = self.io.read_text(template_path)
        if template is None:
            self.io.tool_error(f"Unable to read {template_rel}.")
            return

        short_name = self._generate_short_name(description)
        feature_number = self._determine_next_feature_number(short_name)

        script_rel = ".specify/scripts/bash/create-new-feature.sh"
        script_path = self.coder.abs_root_path(script_rel)
        if not os.path.exists(script_path):
            self.io.tool_error("Script .specify/scripts/bash/create-new-feature.sh not found.")
            return

        spec_info = self._run_feature_creation_script(
            script_path,
            description,
            short_name,
            feature_number,
        )
        if not spec_info:
            return

        spec_file = spec_info.get("SPEC_FILE")
        branch_name = spec_info.get("BRANCH_NAME")
        if not spec_file:
            self.io.tool_error("Feature creation script did not return a spec file path.")
            return
        if not branch_name:
            self.io.tool_error("Feature creation script did not return a branch name.")
            return

        spec_file = os.path.abspath(spec_file)

        date_str = datetime.now().strftime("%B %d, %Y")
        headline = description.strip().rstrip(".")
        if not headline:
            headline = "Feature"

        prompt = template.replace("$ARGUMENTS", description)
        metadata_replacements = {
            "[FEATURE NAME]": headline,
            "[###-feature-name]": branch_name,
            "[DATE]": date_str,
        }
        for token, value in metadata_replacements.items():
            prompt = prompt.replace(token, value)

        from aider.coders.base_coder import Coder

        helper_coder = Coder.create(
            io=self.io,
            from_coder=self.coder,
            edit_format=self.coder.main_model.edit_format,
            summarize_from_coder=False,
        )
        spec_body = helper_coder.run(prompt)
        if not spec_body:
            self.io.tool_error("Unable to generate the specification content.")
            return
        spec_body_raw = spec_body
        spec_body = self._sanitize_constitution_text(spec_body)
        spec_body = f"{spec_body.rstrip()}\n"

        if not spec_body.strip().startswith("# Feature Specification:"):
            self.io.tool_error(
                "Specification generation failed: assistant response did not start with "
                "'# Feature Specification:'."
            )
            self.io.tool_output("Assistant response:")
            self.io.tool_output(spec_body_raw)
            return

        self.io.write_text(spec_file, spec_body)
        self.coder.abs_fnames.add(spec_file)

        feature_name = self._extract_feature_name(spec_body, branch_name)
        checklist_path = self._write_spec_checklist(spec_file, feature_name)
        self.coder.abs_fnames.add(checklist_path)
        self.coder.check_added_files()

        root = self.coder.root or os.getcwd()
        spec_rel = os.path.relpath(spec_file, root).replace(os.sep, "/")
        checklist_rel = os.path.relpath(checklist_path, root).replace(os.sep, "/")

        self.io.tool_output(f"Specification written to {spec_rel}")
        self.io.tool_output(f"Checklist created at {checklist_rel}")
        self.io.tool_output(f"Branch created: {branch_name} ({feature_name})")
        self.io.tool_output("Specification ready for /speckit.clarify or /speckit.plan.")

        self.coder.cur_messages += [
            dict(role="user", content=prompt),
            dict(role="assistant", content=spec_body),
        ]

    @staticmethod
    def _generate_short_name(description):
        tokens = re.findall(r"[A-Za-z0-9]+(?:'[A-Za-z0-9]+)?", description)
        meaningful = []
        for token in tokens:
            normalized = token.lower().strip("'")
            if not normalized or normalized in SHORT_NAME_STOP_WORDS:
                continue
            if len(normalized) >= 3:
                meaningful.append(normalized)
        if len(meaningful) < 2:
            fallback = [
                token.lower().strip("'") for token in tokens if token and token.lower().strip("'")
            ]
            meaningful = fallback
        candidates = meaningful[:4]
        if not candidates:
            candidates = ["feature"]
        return SpeckitCommandsMixin._clean_branch_suffix("-".join(candidates))

    @staticmethod
    def _clean_branch_suffix(name):
        cleaned = re.sub(r"[^a-z0-9]+", "-", name.lower())
        cleaned = re.sub(r"-{2,}", "-", cleaned).strip("-")
        return cleaned or "feature"

    def _determine_next_feature_number(self, short_name):
        root = self.coder.root or os.getcwd()
        numbers = set()
        self._git_fetch_all(root)
        branch_listing = self._run_git_command(["git", "branch", "-a"], root)
        numbers.update(self._extract_branch_numbers(branch_listing, short_name))
        remote_listing = self._run_git_command(["git", "ls-remote", "--heads", "origin"], root)
        numbers.update(self._extract_remote_numbers(remote_listing, short_name))
        specs_dir = os.path.join(root, "specs")
        numbers.update(self._extract_specs_numbers(specs_dir, short_name))
        return max(numbers, default=0) + 1

    def _git_fetch_all(self, root):
        try:
            subprocess.run(
                ["git", "fetch", "--all", "--prune"],
                cwd=root,
                capture_output=True,
                text=True,
                check=True,
            )
        except (subprocess.CalledProcessError, FileNotFoundError):
            self.io.tool_warning(
                "Unable to refresh remote branch information; proceeding with existing data."
            )

    def _run_git_command(self, cmd, root):
        try:
            proc = subprocess.run(
                cmd,
                cwd=root,
                capture_output=True,
                text=True,
                check=True,
            )
            return proc.stdout
        except (subprocess.CalledProcessError, FileNotFoundError):
            return ""

    @staticmethod
    def _extract_branch_numbers(listing, short_name):
        numbers = set()
        if not listing:
            return numbers
        pattern = re.compile(rf"^(\d+)-{re.escape(short_name)}$")
        for line in listing.splitlines():
            cleaned = re.sub(r"^[* ]+", "", line.strip())
            cleaned = re.sub(r"^remotes/[^/]+/", "", cleaned)
            if not cleaned:
                continue
            match = pattern.match(cleaned)
            if match:
                numbers.add(int(match.group(1)))
        return numbers

    @staticmethod
    def _extract_remote_numbers(listing, short_name):
        numbers = set()
        if not listing:
            return numbers
        pattern = re.compile(rf"^(\d+)-{re.escape(short_name)}$")
        for line in listing.splitlines():
            parts = line.strip().split()
            if len(parts) < 2:
                continue
            ref = parts[1]
            branch = ref[len("refs/heads/") :] if ref.startswith("refs/heads/") else ref
            match = pattern.match(branch)
            if match:
                numbers.add(int(match.group(1)))
        return numbers

    @staticmethod
    def _extract_specs_numbers(specs_dir, short_name):
        numbers = set()
        if not os.path.isdir(specs_dir):
            return numbers
        pattern = re.compile(rf"^(\d+)-{re.escape(short_name)}$")
        for entry in os.listdir(specs_dir):
            path = os.path.join(specs_dir, entry)
            if not os.path.isdir(path):
                continue
            match = pattern.match(entry)
            if match:
                numbers.add(int(match.group(1)))
        return numbers

    def _run_feature_creation_script(self, script_path, description, short_name, number):
        root = self.coder.root or os.getcwd()
        script_path_posix = Path(script_path).as_posix()
        try:
            proc = subprocess.run(
                [
                    "bash",
                    script_path_posix,
                    "--json",
                    "--number",
                    str(number),
                    "--short-name",
                    short_name,
                    description,
                ],
                cwd=root,
                capture_output=True,
                text=True,
                check=True,
            )
        except subprocess.CalledProcessError as err:
            self.io.tool_error("Unable to create specification workspace.")
            stderr = (err.stderr or "").strip()
            stdout = (err.stdout or "").strip()
            if stderr:
                self.io.tool_output(stderr)
            if stdout:
                self.io.tool_output(stdout)
            return None
        except FileNotFoundError:
            self.io.tool_error("Unable to run create-new-feature.sh; bash is not available.")
            return None

        stderr = proc.stderr.strip()
        if stderr:
            self.io.tool_warning(stderr)

        stdout = proc.stdout.strip()
        if not stdout:
            self.io.tool_error("Feature creation script produced no JSON output.")
            return None

        try:
            return json.loads(stdout)
        except json.JSONDecodeError:
            self.io.tool_error("Unexpected output from the feature creation script.")
            if stdout:
                self.io.tool_output(stdout)
            return None

    def _write_spec_checklist(self, spec_file, feature_name):
        root = self.coder.root or os.getcwd()
        spec_rel = os.path.relpath(spec_file, root).replace(os.sep, "/")
        date_str = datetime.now().strftime("%B %d, %Y")
        checklist_dir = os.path.join(os.path.dirname(spec_file), "checklists")
        os.makedirs(checklist_dir, exist_ok=True)
        checklist_path = os.path.join(checklist_dir, "requirements.md")
        template_path = self.coder.abs_root_path(".specify/templates/checklist-template.md")
        template_content = self.io.read_text(template_path)
        checklist_content = None

        if template_content:
            checklist_content = template_content
            replacements = {
                "[CHECKLIST TYPE]": "Specification Quality",
                "[FEATURE NAME]": feature_name,
                "[Brief description of what this checklist covers]": (
                    "Validate specification completeness and quality before proceeding to planning"
                ),
                "[DATE]": date_str,
                "[Link to spec.md or relevant documentation]": f"[spec.md]({spec_rel})",
            }
            for token, value in replacements.items():
                checklist_content = checklist_content.replace(token, value)

        if checklist_content is None:
            checklist_content = (
                f"# Specification Quality Checklist: {feature_name}\n\n"
                "**Purpose**: Validate specification completeness and quality "
                "before proceeding to planning\n"
                f"**Created**: {date_str}\n"
                f"**Feature**: [spec.md]({spec_rel})\n\n"
                "## Content Quality\n\n"
                "- [ ] No implementation details (languages, frameworks, APIs)\n"
                "- [ ] Focused on user value and business needs\n"
                "- [ ] Written for non-technical stakeholders\n"
                "- [ ] All mandatory sections completed\n\n"
                "## Requirement Completeness\n\n"
                "- [ ] No [NEEDS CLARIFICATION] markers remain\n"
                "- [ ] Requirements are testable and unambiguous\n"
                "- [ ] Success criteria are measurable\n"
                "- [ ] Success criteria are technology-agnostic (no implementation details)\n"
                "- [ ] All acceptance scenarios are defined\n"
                "- [ ] Edge cases are identified\n"
                "- [ ] Scope is clearly bounded\n"
                "- [ ] Dependencies and assumptions identified\n\n"
                "## Feature Readiness\n\n"
                "- [ ] All functional requirements have clear acceptance criteria\n"
                "- [ ] User scenarios cover primary flows\n"
                "- [ ] Feature meets measurable outcomes defined in Success Criteria\n"
                "- [ ] No implementation details leak into specification\n\n"
                "## Notes\n\n"
                "- Items marked incomplete require spec updates before "
                "`/speckit.clarify` or `/speckit.plan`\n"
            )
        self.io.write_text(checklist_path, checklist_content)
        return checklist_path

    def _add_read_only(self, path):
        if not os.path.exists(path):
            return

        # Avoid duplicate additions if already marked read-only
        try:
            for existing in self.coder.abs_read_only_fnames:
                if existing == path or existing == str(path):
                    return
                try:
                    if os.path.samefile(existing, path):
                        return
                except OSError:
                    continue
        except Exception:
            pass

        rel_name = self.coder.get_rel_fname(path)
        if os.path.isdir(path):
            self._add_read_only_directory(path, rel_name)
            return

        self._add_read_only_file(path, rel_name)

    @staticmethod
    def _sanitize_constitution_text(text):
        if text is None:
            return text
        match = re.search(r"(?m)^#{1,6}\s+.*", text)
        sanitized = text[match.start() :].lstrip("\n") if match else text
        sanitized = re.sub(r"\n*```+\s*$", "", sanitized)
        sanitized = sanitized.rstrip()
        sanitized = SpeckitCommandsMixin._strip_conflict_markers(sanitized)
        return sanitized

    @staticmethod
    def _strip_conflict_markers(text):
        if text is None:
            return text
        conflict_pattern = re.compile(
            r"(?ms)(?:<<<<<<<[^\n]*\n)?=======\n(?P<theirs>.*?)(?:\n>>>>>>>[^\n]*\n?)"
        )
        cleaned = text
        while True:
            match = conflict_pattern.search(cleaned)
            if not match:
                break
            cleaned = cleaned[: match.start()] + match.group("theirs") + cleaned[match.end():]
        cleaned = re.sub(r"(?m)^<<<<<<<.*\n?", "", cleaned)
        cleaned = re.sub(r"(?m)^=======.*\n?", "", cleaned)
        cleaned = re.sub(r"(?m)^>>>>>>>.*\n?", "", cleaned)
        return cleaned.strip()

    @staticmethod
    def _extract_feature_name(spec_body, fallback):
        for line in spec_body.splitlines():
            stripped = line.strip()
            if not stripped.startswith("#"):
                continue
            header = stripped.lstrip("#").strip()
            if not header:
                continue
            if header.lower().startswith("feature specification:"):
                header = header.split(":", 1)[1].strip()
            if header:
                return header
        return fallback
