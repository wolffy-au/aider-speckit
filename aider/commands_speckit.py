import json
import os
import re
import subprocess
from datetime import datetime
from pathlib import Path

from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from aider.coders.base_coder import Coder
    from aider.io import InputOutput


def _load_coder_class():
    from aider.coders.base_coder import Coder

    return Coder


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
    coder: "Coder"
    io: "InputOutput"
    _add_read_only_directory: Callable[[str | os.PathLike, str | None], None]
    _add_read_only_file: Callable[[str | os.PathLike, str | None], None]

    def cmd_speckit_constitution(self, args):
        "Populate the speckit constitution template into .specify/memory."

        template_rel = ".aider/commands/speckit.constitution.md"
        template_path = self.coder.abs_root_path(template_rel)
        memory_rel = ".specify/memory/constitution.md"
        constitution_path = self.coder.abs_root_path(memory_rel)

        try:
            if not os.path.exists(template_path):
                self.io.tool_error(f"Template {template_rel} not found.")
                return
            template_content = self.io.read_text(template_path)
            if not template_content:
                self.io.tool_error(f"Template {template_rel} not found.")
                return

            prompt = template_content.replace("$ARGUMENTS", args or "")
            Coder = _load_coder_class()
            coder = Coder.create(
                io=self.io,
                from_coder=self.coder,
                edit_format=self.coder.main_model.edit_format,
                summarize_from_coder=False,
            )
            result = coder.run(prompt)
            os.makedirs(os.path.dirname(constitution_path), exist_ok=True)
            self.io.write_text(constitution_path, result)
        finally:
            self.coder.drop_rel_fname(constitution_path)

    def cmd_speckit_specify(self, args):
        "Create or update a feature specification via the speckit specify workflow."
        template_rel = ".aider/commands/speckit.specify.md"
        template_path = self.coder.abs_root_path(template_rel)
        if not os.path.exists(template_path):
            self.io.tool_error(f"Template {template_rel} not found.")
            return
        template_content = self.io.read_text(template_path)
        if not template_content:
            self.io.tool_error(f"Template {template_rel} not found.")
            return

        description = args or ""
        filled_template = template_content.replace("$ARGUMENTS", description)
        short_name = self._generate_short_name(description)
        feature_number = self._determine_next_feature_number(short_name)
        result = self._run_feature_creation_script(
            ".specify/scripts/bash/create-new-feature.sh",
            description,
            short_name,
            feature_number,
        )
        if not result:
            self.io.tool_error("Specification workspace creation failed.")
            return
        if "SPEC_FILE" not in result or "BRANCH_NAME" not in result:
            return

        spec_file = result["SPEC_FILE"]
        branch_name = result["BRANCH_NAME"]
        feature_name_hint = self._feature_name_from_branch(branch_name)

        placeholder_checklist = self._write_spec_checklist(spec_file, feature_name_hint)
        if placeholder_checklist:
            self._register_managed_file(placeholder_checklist)

        root = self.coder.root or os.getcwd()
        spec_rel = os.path.relpath(spec_file, root).replace(os.sep, "/")
        self._register_managed_file(spec_file)
        try:
            feature_number_str = f"{int(feature_number):03d}"
        except (TypeError, ValueError):
            feature_number_str = str(feature_number)

        spec_content = self.io.read_text(spec_file) or ""
        checklist_content = self.io.read_text(placeholder_checklist) or ""
        date_str = datetime.now().strftime("%B %d, %Y")
        metadata_replacements = {
            "[FEATURE NAME]": feature_name_hint,
            "[FEATURE SHORT NAME]": short_name,
            "[BRANCH NAME]": branch_name,
            "[FEATURE NUMBER]": feature_number_str,
            "[SPEC RELATIVE PATH]": spec_rel,
        }

        prompt = self._build_spec_generation_prompt(
            description,
            filled_template,
            metadata_replacements,
            branch_name,
            date_str,
            spec_content,
            checklist_content,
        )
        Coder = _load_coder_class()
        coder = Coder.create(
            io=self.io,
            from_coder=self.coder,
            edit_format=self.coder.main_model.edit_format,
            summarize_from_coder=False,
        )
        response = coder.run(prompt)
        if self._response_requests_spec_and_checklist(response):
            coder = Coder.create(
                io=self.io,
                from_coder=self.coder,
                edit_format=self.coder.main_model.edit_format,
                summarize_from_coder=False,
            )
            response = coder.run(prompt)

        trimmed = self._trim_to_feature_header(response or "")
        if not trimmed or not trimmed.lstrip().lower().startswith("# feature specification:"):
            self.io.tool_error(
                "Specification generation failed: assistant response did not start "
                "with '# Feature Specification:'."
            )
            self.io.tool_output("Assistant response:")
            self.io.tool_output(response or "")
            return

        self.io.write_text(spec_file, trimmed)
        self._register_managed_file(spec_file)

        final_feature_name = self._extract_feature_name(trimmed, feature_name_hint)
        final_checklist = self._write_spec_checklist(spec_file, final_feature_name)
        if final_checklist:
            self._register_managed_file(final_checklist)

    def cmd_speckit_analyze(self, args):
        (
            "Analyze an existing specification for completeness and quality, "
            "and generate a checklist of improvements."
        )
        # TODO: Implement the /speckit.analyze command to review an existing spec.md
        # TODO: and produce a requirements.md checklist.
        self.io.tool_output("The /speckit.analyze command is not implemented yet.")
        pass

    def cmd_speckit_checklist(self, args):
        (
            "Generate a checklist of requirements and quality gates based on the current "
            "specification, to guide the planning and implementation phases."
        )
        # TODO: Implement the /speckit.checklist command to create a requirements.md checklist
        # TODO: based on the current spec.md, ensuring it covers all necessary quality gates
        # TODO: and requirements for the feature.
        self.io.tool_output("The /speckit.checklist command is not implemented yet.")
        pass

    def cmd_speckit_clarify(self, args):
        (
            "Identify ambiguities, gaps, or areas needing further detail in the specification, "
            "and generate a list of clarification questions to address them."
        )
        # TODO: Implement the /speckit.clarify command to analyze the current spec.md for
        # TODO: any unclear or incomplete sections, and produce a list of specific
        # TODO: clarification questions that should be answered to improve the specification
        # TODO: before proceeding to planning.
        self.io.tool_output("The /speckit.clarify command is not implemented yet.")
        pass

    def cmd_speckit_implement(self, args):
        (
            "Generate implementation tasks and a recommended development workflow based on the "
            "current specification and checklist, to guide the engineering team in building the "
            "feature according to the defined requirements and quality gates."
        )
        # TODO: Implement the /speckit.implement command to create a set of actionable
        # TODO: implementation tasks and a suggested development workflow, derived from the
        # TODO: current spec.md and requirements.md, to assist engineers in executing the
        # TODO: feature development in alignment with the specified requirements and
        # TODO: quality standards.
        self.io.tool_output("The /speckit.implement command is not implemented yet.")
        pass

    def cmd_speckit_plan(self, args):
        (
            "Generate a high-level project plan and timeline for delivering the feature, based on "
            "the current specification, checklist, and implementation tasks, to assist in "
            "coordinating the work across teams and setting expectations for delivery."
        )
        # TODO: Implement the /speckit.plan command to produce a strategic project plan and
        # TODO: timeline for feature delivery, informed by the current spec.md, requirements.md,
        # TODO: and implementation tasks, to help project managers and stakeholders coordinate
        # TODO: efforts and establish clear expectations for the development process.
        self.io.tool_output("The /speckit.plan command is not implemented yet.")
        pass

    def cmd_speckit_tasks(self, args):
        (
            "Generate a set of actionable implementation tasks based on the current specification "
            "and checklist, to guide engineers in executing the feature development in alignment "
            "with the defined requirements and quality gates."
        )
        # TODO: Implement the /speckit.tasks command to create a detailed list of
        # TODO: implementation tasks derived from the current spec.md and requirements.md,
        # TODO: providing engineers with clear guidance on the specific work items needed
        # TODO: to build the feature according to the defined requirements
        # TODO: and quality standards.
        self.io.tool_output("The /speckit.tasks command is not implemented yet.")
        pass

    def cmd_speckit_tasktoissues(self, args):
        (
            "Convert the implementation tasks generated by /speckit.tasks into issues in the "
            "project's issue tracker, to facilitate tracking and management of the work items "
            "needed to deliver the feature."
        )
        # TODO: Implement the /speckit.tasktoissues command to take the actionable
        # TODO: implementation tasks produced by /speckit.tasks and create corresponding
        # TODO: issues in the project's issue tracking system, enabling better organization,
        # TODO: assignment, and monitoring of the work required for feature delivery.
        self.io.tool_output("The /speckit.tasktoissues command is not implemented yet.")
        pass

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
        template_content = None
        if os.path.exists(template_path):
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

    def _build_spec_generation_prompt(
        self,
        description,
        template,
        metadata_replacements,
        branch_name,
        date_str,
        existing_spec,
        existing_checklist,
    ):
        filled_template = template or ""
        for token, value in (metadata_replacements or {}).items():
            filled_template = filled_template.replace(token, value or "")
        feature_name = metadata_replacements.get("[FEATURE NAME]", branch_name)
        description_text = description.strip() or "[no description provided]"
        template_section = filled_template.strip() or "[spec template not available]"
        existing_spec_section = existing_spec or "[empty spec.md created by the script]"
        existing_checklist_section = (
            existing_checklist or "[empty checklist template created by the script]"
        )

        sections = [
            "Do not ask the user to upload spec.md or requirements.md.",
            (
                "You are writing the first version of the specification; ignore any previous "
                "requests for files and just emit the full final spec beginning with "
                "'# Feature Specification:'."
            ),
            "",
            "Feature details:",
            f"- Name: {feature_name}",
            f"- Branch: {branch_name}",
            f"- Date: {date_str}",
            f"- Description: {description_text}",
            "",
            "Spec template reference (fill in these sections):",
            template_section,
            "",
            "Existing spec.md content:",
            existing_spec_section,
            "",
            "Existing checklist (requirements.md) content:",
            existing_checklist_section,
            "",
            (
                "Use the template above and the feature context to write the "
                "complete feature specification now."
            ),
        ]
        return "\n".join(sections)

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

    def _remove_read_only(self, paths):
        try:
            abs_read_only = getattr(self.coder, "abs_read_only_fnames", None)
            if not abs_read_only:
                return

            def _matches(existing, target):
                if existing == target or existing == str(target):
                    return True
                try:
                    return os.path.samefile(existing, target)
                except OSError:
                    return False

            for target in paths:
                for existing in list(abs_read_only):
                    if _matches(existing, target):
                        try:
                            abs_read_only.discard(existing)
                        except AttributeError:
                            try:
                                abs_read_only.remove(existing)
                            except (ValueError, KeyError):
                                pass
        except Exception:
            pass

    @staticmethod
    def _sanitize_constitution_text(text):
        if text is None:
            return text
        match = re.search(r"(?m)^#{1,6}\s+.*", text)
        sanitized = text[match.start() :].lstrip("\n") if match else text
        sanitized = re.sub(r"\n*```+\s*$", "", sanitized)
        sanitized = sanitized.rstrip()
        sanitized = SpeckitCommandsMixin._strip_conflict_markers(sanitized)

        # If the assistant echoed an older constitution above the new one,
        # keep only the latest H1 section
        h1_matches = list(re.finditer(r"(?m)^#\s+.+$", sanitized))
        if len(h1_matches) > 1:
            sanitized = sanitized[h1_matches[-1].start() :].lstrip("\n")

        return sanitized

    @staticmethod
    def _trim_to_feature_header(text):
        if text is None:
            return text
        match = re.search(r"(?mi)^#\s+feature specification:", text)
        return text[match.start() :] if match else text

    @staticmethod
    def _feature_name_from_branch(branch_name):
        if not branch_name:
            return branch_name
        cleaned = re.sub(r"^\d+-", "", branch_name)
        parts = [part for part in re.split(r"[-_\s]+", cleaned) if part]
        if not parts:
            return branch_name
        return " ".join(part.capitalize() for part in parts)

    @staticmethod
    def _response_requests_spec_and_checklist(response):
        if not response:
            return False
        normalized = response.lower()
        return (
            "generated feature spec" in normalized
            and "quality checklist" in normalized
            and "specs/" in normalized
            and "checklists/requirements.md" in normalized
        )

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
            cleaned = cleaned[: match.start()] + match.group("theirs") + cleaned[match.end() :]
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

    def _extract_template_placeholders(self, template):
        seen = []
        for token in re.findall(r"\[([A-Z0-9_]+)\]", template):
            if token not in seen:
                seen.append(token)
        return seen

    def _parse_placeholder_inputs(self, raw_args):
        parsed = {}
        for part in re.split(r"[;\n]", raw_args or ""):
            segment = part.strip()
            if not segment or "=" not in segment:
                continue
            key, value = segment.split("=", 1)
            normalized = key.strip().upper()
            if not normalized:
                continue
            parsed[normalized] = value.strip()
        return parsed

    def _collect_document_contexts(self):
        doc_targets = [
            "README.md",
            "docs/README.md",
            ".specify/README.md",
            ".specify/templates/constitution-template.md",
        ]
        contexts = {}
        for rel in doc_targets:
            path = self.coder.abs_root_path(rel)
            if not os.path.exists(path):
                continue
            text = self.io.read_text(path)
            if text:
                contexts[path] = text
        return contexts

    def _build_placeholder_values(
        self,
        placeholders,
        user_inputs,
        existing_content,
        document_contexts,
    ):
        derived = {}
        manual = []
        existing_values = self._derive_existing_values(existing_content)
        for placeholder in placeholders:
            if placeholder in user_inputs:
                derived[placeholder] = user_inputs[placeholder]
                continue
            if placeholder in existing_values:
                derived[placeholder] = existing_values[placeholder]
                continue
            doc_value = self._extract_from_document_contexts(placeholder, document_contexts)
            if doc_value:
                derived[placeholder] = doc_value
                continue
            derived[placeholder] = self._default_value_for_placeholder(placeholder)
            manual.append(f"{placeholder} (fallback value applied)")
        return derived, manual

    def _derive_existing_values(self, existing_content):
        values = {}
        version = self._extract_existing_version(existing_content)
        if version:
            values["CONSTITUTION_VERSION"] = version
        ratified = self._extract_labelled_date(existing_content, "Ratified")
        if ratified:
            values["RATIFICATION_DATE"] = ratified
        amended = self._extract_labelled_date(existing_content, "Last Amended")
        if amended:
            values["LAST_AMENDED_DATE"] = amended
        principles = self._extract_principles_from_constitution(existing_content)
        for idx, (name, desc) in enumerate(principles, start=1):
            values[f"PRINCIPLE_{idx}_NAME"] = name
            values[f"PRINCIPLE_{idx}_DESCRIPTION"] = desc
        sections = self._extract_sections_from_constitution(existing_content)
        for idx, (name, content) in enumerate(sections, start=2):
            values[f"SECTION_{idx}_NAME"] = name
            values[f"SECTION_{idx}_CONTENT"] = content
        governance = self._extract_governance_rules(existing_content)
        if governance:
            values["GOVERNANCE_RULES"] = governance
        return values

    def _extract_labelled_date(self, text, label):
        pattern = re.compile(
            rf"\*\*{re.escape(label)}\*\*:\s*([0-9]{{4}}-[0-9]{{2}}-[0-9]{{2}})", re.IGNORECASE
        )
        match = pattern.search(text)
        if match:
            return match.group(1)
        return None

    def _extract_principles_from_constitution(self, text):
        match = re.search(r"(?ms)^##\s+Core Principles\s*(.*?)(?=^##\s+|\Z)", text)
        if not match:
            return []
        body = match.group(1)
        pattern = re.compile(r"(?ms)^###\s+(.+?)\s*(.*?)(?=^###\s+|\Z)")
        return [(m.group(1).strip(), m.group(2).strip()) for m in pattern.finditer(body)]

    def _extract_sections_from_constitution(self, text):
        matches = list(re.finditer(r"(?m)^##\s+(.+)", text))
        sections = []
        for idx, match in enumerate(matches):
            heading = match.group(1).strip()
            start = match.end()
            end = matches[idx + 1].start() if idx + 1 < len(matches) else len(text)
            body = text[start:end].strip()
            sections.append((heading, body))
        filtered = []
        for name, body in sections:
            if name in {"Core Principles", "Governance"}:
                continue
            filtered.append((name, body))
        return filtered

    def _extract_governance_rules(self, text):
        match = re.search(r"(?ms)^##\s+Governance\s*(.*?)(?=^##\s+|\Z)", text)
        if match:
            return match.group(1).strip()
        return ""

    def _extract_from_document_contexts(self, placeholder, contexts):
        needle = placeholder.replace("_", " ").lower()
        for content in contexts.values():
            for line in content.splitlines():
                normalized = line.strip()
                if not normalized:
                    continue
                if needle in normalized.lower() and ":" in normalized:
                    candidate = normalized.split(":", 1)[1].strip()
                    if candidate:
                        return candidate
        return None

    def _extract_placeholder_index(self, placeholder):
        match = re.search(r"_(\d+)_", placeholder)
        if match:
            return match.group(1)
        return None

    def _default_value_for_placeholder(self, placeholder):
        if placeholder == "PROJECT_NAME":
            root = self.coder.root or os.getcwd()
            return os.path.basename(root) or "Project"
        if placeholder.startswith("PRINCIPLE_") and placeholder.endswith("_NAME"):
            idx = self._extract_placeholder_index(placeholder)
            return f"Principle {idx}" if idx else "Principle"
        if placeholder.startswith("PRINCIPLE_") and placeholder.endswith("_DESCRIPTION"):
            idx = self._extract_placeholder_index(placeholder)
            label = f"Principle {idx}" if idx else "this principle"
            return f"Describe the focus and success guards for {label}."
        if placeholder.startswith("SECTION_") and placeholder.endswith("_NAME"):
            if "2" in placeholder:
                return "Additional Constraints"
            if "3" in placeholder:
                return "Development Workflow & Quality Gates"
        if placeholder.startswith("SECTION_") and placeholder.endswith("_CONTENT"):
            return (
                "Capture constraints, risks, and expectations that must be "
                "satisfied for the feature."
            )
        if placeholder == "GOVERNANCE_RULES":
            return (
                "Constitution changes require documented intent, peer validation, "
                "and explicit approval."
            )
        if placeholder in {"RATIFICATION_DATE", "LAST_AMENDED_DATE"}:
            return datetime.now().strftime("%Y-%m-%d")
        return placeholder.replace("_", " ").capitalize()

    def _fill_template(self, template, values):
        result = template
        for key, value in values.items():
            result = result.replace(f"[{key}]", value)
        return result

    def _validate_constitution_text(self, text):
        if not text.strip():
            raise ValueError("Constitution text is empty.")
        leftover = re.search(r"\[[A-Z0-9_]+\]", text)
        if leftover:
            raise ValueError(f"Unresolved placeholder {leftover.group(0)} remains.")
        return text.rstrip() + "\n"

    def _collect_principle_summary(self, placeholder_values):
        principles = []
        for idx in range(1, 6):
            name = placeholder_values.get(f"PRINCIPLE_{idx}_NAME")
            desc = (placeholder_values.get(f"PRINCIPLE_{idx}_DESCRIPTION") or "").strip()
            if not name and not desc:
                continue
            principles.append(
                {
                    "name": name or f"Principle {idx}",
                    "description": desc or f"Add precise guidance for Principle {idx}.",
                }
            )
        return principles

    def _format_principle_summary(self, principles):
        if not principles:
            return "- Not defined yet."
        lines = []
        for idx, principle in enumerate(principles, start=1):
            desc = principle.get("description", "").strip()
            suffix = f": {desc}" if desc else ""
            lines.append(f"- {idx}. {principle['name']}{suffix}")
        return "\n".join(lines)

    def _sync_dependent_templates(self, principles, version):
        auto = []
        manual = []
        principle_summary = self._format_principle_summary(principles)
        plan_summary = (
            f"Gates determined based on Constitution v{version}. Active principles:\n"
            f"{principle_summary}"
        )
        alignment_section = (
            "## Constitution Alignment\n\n"
            f"Based on Constitution v{version}, the active principles are:\n"
            f"{principle_summary}\n"
        )

        plan_path = self.coder.abs_root_path(".specify/templates/plan-template.md")
        if self._update_plan_template(plan_path, plan_summary):
            auto.append(plan_path)
        else:
            manual.append(
                f"{self._format_file_reference(plan_path)} needs manual constitution alignment."
            )

        for rel in [
            ".specify/templates/spec-template.md",
            ".specify/templates/tasks-template.md",
        ]:
            template_path = self.coder.abs_root_path(rel)
            if self._ensure_alignment_section(template_path, alignment_section):
                auto.append(template_path)
            else:
                manual.append(
                    f"{self._format_file_reference(template_path)} needs "
                    "manual constitution alignment."
                )

        commands_dir = self.coder.abs_root_path(".specify/templates/commands")
        if os.path.isdir(commands_dir):
            for path in sorted(Path(commands_dir).glob("*.md")):
                str_path = str(path)
                if self._ensure_alignment_section(str_path, alignment_section):
                    auto.append(str_path)
                else:
                    manual.append(
                        f"{self._format_file_reference(str_path)} needs "
                        "manual constitution alignment."
                    )
        else:
            manual.append("Command templates directory not found for automatic sync.")

        runtime_dir = self.coder.abs_root_path(".specify/runtime")
        if os.path.isdir(runtime_dir):
            for path in sorted(Path(runtime_dir).glob("*.md")):
                str_path = str(path)
                if self._ensure_alignment_section(str_path, alignment_section):
                    auto.append(str_path)
                else:
                    manual.append(
                        f"{self._format_file_reference(str_path)} needs "
                        "manual constitution alignment."
                    )
        else:
            manual.append("Runtime guidance docs directory not found for automatic sync.")

        return {"auto": auto, "manual": manual}

    def _update_plan_template(self, path, summary):
        if not os.path.exists(path):
            return False
        original = self.io.read_text(path)
        if original is None:
            return False
        placeholder = "[Gates determined based on constitution file]"
        new_content = original
        if placeholder in new_content:
            new_content = new_content.replace(placeholder, summary)
        elif "## Constitution Check" in new_content:
            before, after = new_content.split("## Constitution Check", 1)
            new_content = f"{before}## Constitution Check\n\n{summary}\n{after}"
        if new_content != original:
            self.io.write_text(path, new_content)
            self._register_managed_file(path)
            return True
        return False

    def _ensure_alignment_section(self, path, alignment_section):
        if not os.path.exists(path):
            return False
        original = self.io.read_text(path)
        if original is None:
            return False
        marker = "## Constitution Alignment"
        if marker in original:
            pattern = re.compile(r"(?ms)^## Constitution Alignment\s*.*?(?=\n## |\Z)")
            updated_section = alignment_section.rstrip() + "\n"
            new_content = pattern.sub(updated_section, original, count=1)
        else:
            new_content = f"{alignment_section}\n{original}"
        if new_content != original:
            self.io.write_text(path, new_content)
            self._register_managed_file(path)
            return True
        return False

    def _bump_semantic_version(self, current, bump_type):
        base = (current or "0.0.0").strip()
        parts = base.split(".")
        while len(parts) < 3:
            parts.append("0")
        try:
            major, minor, patch = (int(p) for p in parts[:3])
        except ValueError:
            major, minor, patch = 0, 0, 0
        if bump_type == "major":
            major += 1
            minor = 0
            patch = 0
        elif bump_type == "minor":
            minor += 1
            patch = 0
        else:
            patch += 1
        return f"{major}.{minor}.{patch}"

    def _normalize_iso_date(self, value, fallback):
        if not value:
            return fallback
        for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%m/%d/%Y"):
            try:
                parsed = datetime.strptime(value, fmt)
                return parsed.date().isoformat()
            except ValueError:
                continue
        try:
            parsed = datetime.fromisoformat(value)
            return parsed.date().isoformat()
        except ValueError:
            return fallback

    def _register_managed_file(self, path):
        try:
            rel = self.coder.get_rel_fname(path)
            if rel:
                self.coder.add_rel_fname(rel)
            else:
                abs_fnames = getattr(self.coder, "abs_fnames", None)
                if abs_fnames is None:
                    abs_fnames = set()
                    setattr(self.coder, "abs_fnames", abs_fnames)
                abs_fnames.add(path)
        except Exception:
            pass
        try:
            self.coder.check_added_files()
        except Exception:
            pass

    def _build_sync_report_comment(
        self,
        version,
        bump_type,
        old_version,
        principle_diffs,
        section_added,
        section_removed,
        governance_changed,
        auto_files,
        manual_followups,
        principles,
    ):
        date_iso = datetime.now().strftime("%Y-%m-%d")
        auto_unique = list(dict.fromkeys(auto_files))
        auto_desc = (
            ", ".join(self._format_file_reference(path) for path in auto_unique)
            or "none"
        )
        principle_lines = []
        for diff in principle_diffs or []:
            diff_type = diff.get("type")
            if diff_type == "added":
                principle_lines.append(f"- Added: {diff.get('name')}")
            elif diff_type == "removed":
                principle_lines.append(f"- Removed: {diff.get('name')}")
            elif diff_type == "modified":
                name = diff.get("name")
                principle_lines.append(
                    f"- Modified: {name} "
                    f"(was \"{diff.get('old')}\" → \"{diff.get('new')}\")"
                )
        if not principle_lines:
            principle_lines = ["- None"]
        principle_changes_section = "\n".join(principle_lines)
        section_added = section_added or []
        section_removed = section_removed or []
        sections_added_desc = ", ".join(section_added) or "none"
        sections_removed_desc = ", ".join(section_removed) or "none"
        manual_section = (
            "\n".join(f"- {item}" for item in manual_followups)
            if manual_followups
            else "- None"
        )
        principle_line = (
            "; ".join(f"{idx}. {item['name']}" for idx, item in enumerate(principles, start=1))
            or "not defined"
        )
        governance_status = "Yes" if governance_changed else "No"
        return (
            "<!-- Sync Impact Report\n"
            f"Version: {old_version or 'n/a'} → {version} ({bump_type} bump)\n"
            f"Date: {date_iso}\n"
            f"Governance changed: {governance_status}\n"
            "Principle changes:\n"
            f"{principle_changes_section}\n"
            f"Sections added: {sections_added_desc}\n"
            f"Sections removed: {sections_removed_desc}\n"
            f"Auto-updated templates (✅): {auto_desc}\n"
            "Manual follow-ups (⚠ Deferred TODOs):\n"
            f"{manual_section}\n"
            f"Active principles: {principle_line}\n"
            "-->\n\n"
        )

    def _format_file_reference(self, path):
        rel = self.coder.get_rel_fname(path)
        return rel or path

    def _build_sync_summary(
        self,
        old_version,
        new_version,
        bump_type,
        user_inputs,
        auto_files,
        manual_followups,
        principle_diffs,
        section_added,
        section_removed,
        governance_changed,
    ):
        auto_list = list(dict.fromkeys(auto_files))
        auto_desc = (
            ", ".join(self._format_file_reference(path) for path in auto_list) or "none"
        )
        reason = (
            "User requested the bump via VERSION_BUMP argument."
            if "VERSION_BUMP" in user_inputs
            else f"Automatic {bump_type} bump to capture the refreshed constitution."
        )
        principle_diffs = principle_diffs or []
        principle_changes_count = len(principle_diffs)
        change_parts = []
        if principle_changes_count:
            added_names = [
                diff["name"] for diff in principle_diffs if diff.get("type") == "added"
            ]
            removed_names = [
                diff["name"] for diff in principle_diffs if diff.get("type") == "removed"
            ]
            modified_names = [
                diff["name"] for diff in principle_diffs if diff.get("type") == "modified"
            ]
            if added_names:
                change_parts.append(f"added {len(added_names)} ({', '.join(added_names)})")
            if removed_names:
                change_parts.append(f"removed {len(removed_names)} ({', '.join(removed_names)})")
            if modified_names:
                change_parts.append(
                    f"modified {len(modified_names)} ({', '.join(modified_names)})"
                )
        if principle_changes_count:
            if change_parts:
                principle_summary = (
                    f"Principle changes: {principle_changes_count} ({'; '.join(change_parts)})."
                )
            else:
                principle_summary = f"Principle changes: {principle_changes_count}."
        else:
            principle_summary = "Principle changes: none."
        section_added = section_added or []
        section_removed = section_removed or []
        sections_added_desc = ", ".join(section_added) or "none"
        sections_removed_desc = ", ".join(section_removed) or "none"
        summary = [
            f"Constitution version: {old_version or '0.0.0'} → {new_version} ({bump_type} bump).",
            f"Version bump reason: {reason}.",
            principle_summary,
            f"Sections added: {sections_added_desc}; removed: {sections_removed_desc}.",
            f"Auto-updated files: {auto_desc}.",
            f"Governance changes detected: {'yes' if governance_changed else 'no'}.",
        ]
        if manual_followups:
            summary.append(
                f"Manual follow-up required for: {', '.join(manual_followups)}."
            )
        else:
            summary.append("Manual follow-up required for: none.")
        summary.append(
            f"Suggested commit message: chore: refresh constitution to v{new_version}"
        )
        return summary

    def _validate_governance_requirements(self, governance_text):
        if not governance_text or not governance_text.strip():
            raise ValueError("Governance section cannot be empty.")
        normalized = governance_text.lower()
        missing = []
        if "amend" not in normalized:
            missing.append("amendment procedure")
        if "version" not in normalized:
            missing.append("versioning policy")
        if not any(keyword in normalized for keyword in ("compliance", "audit", "review")):
            missing.append("compliance/review expectations")
        if missing:
            raise ValueError(
                "Governance section must mention " + ", ".join(missing) + "."
            )

    def _diff_principles(self, old, new):
        old = old or []
        new = new or []
        diffs = []
        old_map = {name: desc for name, desc in old}
        new_map = {name: desc for name, desc in new}
        for name, desc in new:
            if name not in old_map:
                diffs.append({"type": "added", "name": name})
            else:
                old_desc = old_map[name]
                if old_desc != desc:
                    diffs.append(
                        {"type": "modified", "name": name, "old": old_desc, "new": desc}
                    )
        for name, _ in old:
            if name not in new_map:
                diffs.append({"type": "removed", "name": name})
        return diffs

    def _diff_sections(self, old, new):
        old_names = [name for name, _ in (old or [])]
        new_names = [name for name, _ in (new or [])]
        added = [name for name in new_names if name not in old_names]
        removed = [name for name in old_names if name not in new_names]
        return added, removed
