import json
import os
import subprocess
from datetime import datetime


class SpeckitCommandsMixin:
    def cmd_speckit_constitution(self, args):
        "Populate the speckit constitution template into .specify/memory."

        template_rel = ".aider/commands/speckit.constitution.md"
        template_path = self.coder.abs_root_path(template_rel)

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

        memory_dir = self.coder.abs_root_path(".specify/memory")
        os.makedirs(memory_dir, exist_ok=True)

        constitution_path = self.coder.abs_root_path(".specify/memory/constitution.md")
        self.io.write_text(constitution_path, response)

        if constitution_path not in self.coder.abs_fnames:
            self.coder.abs_fnames.add(constitution_path)
        self.coder.check_added_files()

        self.io.tool_output("Updated .specify/memory/constitution.md with the assistant response.")

        self.coder.cur_messages += [
            dict(role="user", content=prompt),
            dict(role="assistant", content=response),
        ]

    def cmd_speckit_specify(self, args):
        "Create or update a feature specification via the speckit specify workflow."

        template_rel = ".aider/commands/speckit.specify.md"
        template_path = self.coder.abs_root_path(template_rel)

        if not os.path.exists(template_path):
            self.io.tool_error("Template .aider/commands/speckit.specify.md not found.")
            return

        arguments = args.strip()
        if not arguments:
            self.io.tool_error("Please provide a feature description for /speckit.specify.")
            return

        try:
            with open(template_path, "r", encoding=self.io.encoding) as f:
                template = f.read()
        except Exception as err:
            self.io.tool_error(f"Unable to read {template_rel}: {err}")
            return

        prompt = template.replace("$ARGUMENTS", arguments)

        script_rel = ".specify/scripts/bash/create-new-feature.sh"
        script_path = self.coder.abs_root_path(script_rel)
        if not os.path.exists(script_path):
            self.io.tool_error("Script .specify/scripts/bash/create-new-feature.sh not found.")
            return

        proc = subprocess.run(
            ["bash", script_path, "--json", arguments],
            cwd=self.coder.root,
            capture_output=True,
            text=True,
        )

        if proc.returncode != 0:
            self.io.tool_error("Unable to create specification workspace.")
            stderr = proc.stderr.strip()
            stdout = proc.stdout.strip()
            if stderr:
                self.io.tool_output(stderr)
            if stdout:
                self.io.tool_output(stdout)
            return

        stderr = proc.stderr.strip()
        if stderr:
            self.io.tool_warning(stderr)

        try:
            spec_info = json.loads(proc.stdout.strip())
        except json.JSONDecodeError:
            self.io.tool_error("Unexpected output from the feature creation script.")
            stdout = proc.stdout.strip()
            if stdout:
                self.io.tool_output(stdout)
            return

        spec_file = spec_info.get("SPEC_FILE")
        if not spec_file:
            self.io.tool_error("Feature creation script did not return a spec file path.")
            return

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

        self.io.write_text(spec_file, spec_body)
        self.coder.abs_fnames.add(spec_file)

        feature_name = spec_info.get("BRANCH_NAME", "")
        spec_lines = [line for line in spec_body.splitlines() if line.strip()]
        if spec_lines:
            first_line = spec_lines[0].strip()
            if first_line.startswith("# Feature Specification:"):
                feature_name = first_line.replace("# Feature Specification:", "").strip()
            elif first_line.startswith("#"):
                feature_name = first_line.lstrip("#").strip()
        if not feature_name:
            branch_name = spec_info.get("BRANCH_NAME", "")
            if "-" in branch_name:
                feature_name = branch_name.split("-", 1)[1].replace("-", " ").strip()
            else:
                feature_name = branch_name
        if not feature_name:
            feature_name = "Specification"

        feature_dir = os.path.dirname(spec_file)
        checklist_dir = os.path.join(feature_dir, "checklists")
        os.makedirs(checklist_dir, exist_ok=True)
        checklist_path = os.path.join(checklist_dir, "requirements.md")

        spec_rel = os.path.relpath(spec_file, self.coder.root)
        spec_display = spec_rel.replace(os.sep, "/")
        checklist_rel = os.path.relpath(checklist_path, self.coder.root)
        checklist_display = checklist_rel.replace(os.sep, "/")
        date_str = datetime.now().strftime("%Y-%m-%d")

        checklist_content = (
            f"# Specification Quality Checklist: {feature_name}\n\n"
            f"**Purpose**: Validate specification completeness and quality before proceeding to planning\n"
            f"**Created**: {date_str}\n"
            f"**Feature**: [spec.md]({spec_display})\n\n"
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
            "- Items marked incomplete require spec updates before `/speckit.clarify` or `/speckit.plan`\n"
        )

        self.io.write_text(checklist_path, checklist_content)
        self.coder.abs_fnames.add(checklist_path)

        self.coder.check_added_files()

        self.io.tool_output(f"Specification written to {spec_display}")
        self.io.tool_output(f"Checklist created at {checklist_display}")

        self.coder.cur_messages += [
            dict(role="user", content=prompt),
            dict(role="assistant", content=spec_body),
        ]
