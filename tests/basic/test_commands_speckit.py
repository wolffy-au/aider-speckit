import os
from pathlib import Path
from unittest import TestCase, mock

from aider.coders import Coder
from aider.commands import Commands
from aider.commands_speckit import SpeckitCommandsMixin
from aider.io import InputOutput
from aider.models import Model
from aider.utils import GitTemporaryDirectory


class TestSpeckitCommands(TestCase):
    def setUp(self):
        self.model = Model("gpt-3.5-turbo")
        self.original_cwd = os.getcwd()

    def tearDown(self):
        os.chdir(self.original_cwd)

    def _make_commands(self, repo_dir):
        io = InputOutput(pretty=False, fancy_input=False, yes=True)
        coder = Coder.create(self.model, None, io)
        coder.root = repo_dir
        return Commands(io, coder), io, coder

    def test_cmd_speckit_constitution_requires_template(self):
        with GitTemporaryDirectory() as repo_dir:
            os.chdir(repo_dir)
            commands, io, _ = self._make_commands(repo_dir)
            with mock.patch.object(io, "tool_error") as mock_tool_error:
                commands.cmd_speckit_constitution("Focus on testing")
            mock_tool_error.assert_called_once_with(
                "Template .aider/commands/speckit.constitution.md not found."
            )

    def test_cmd_speckit_constitution_writes_constitution_file(self):
        with GitTemporaryDirectory() as repo_dir:
            os.chdir(repo_dir)
            template_path = Path(repo_dir) / ".aider" / "commands" / "speckit.constitution.md"
            template_path.parent.mkdir(parents=True, exist_ok=True)
            template_path.write_text("Constitution definition: $ARGUMENTS")
            commands, _, coder = self._make_commands(repo_dir)

            with mock.patch("aider.coders.base_coder.Coder.create") as mock_create:
                dummy_coder = mock.Mock()
                dummy_coder.run.return_value = "Generated constitution"
                mock_create.return_value = dummy_coder

                commands.cmd_speckit_constitution("Emphasise testing")

                dummy_coder.run.assert_called_once_with(
                    "Constitution definition: Emphasise testing"
                )
                mock_create.assert_called_once_with(
                    io=commands.io,
                    from_coder=coder,
                    edit_format=coder.main_model.edit_format,
                    summarize_from_coder=False,
                )

            constitution_path = Path(repo_dir) / ".specify" / "memory" / "constitution.md"

            self.assertTrue(constitution_path.exists())
            self.assertEqual("Generated constitution", constitution_path.read_text())
            self.assertTrue(
                any(os.path.samefile(constitution_path, fname) for fname in coder.abs_fnames)
            )

    def test_cmd_speckit_specify_requires_template(self):
        with GitTemporaryDirectory() as repo_dir:
            os.chdir(repo_dir)
            commands, io, _ = self._make_commands(repo_dir)
            with mock.patch.object(io, "tool_error") as mock_tool_error:
                commands.cmd_speckit_specify("Create photo albums")
            mock_tool_error.assert_called_once_with(
                "Template .aider/commands/speckit.specify.md not found."
            )

    def test_cmd_speckit_specify_generates_spec_and_checklist(self):
        with GitTemporaryDirectory() as repo_dir:
            os.chdir(repo_dir)
            template_path = Path(repo_dir) / ".aider" / "commands" / "speckit.specify.md"
            template_path.parent.mkdir(parents=True, exist_ok=True)
            template_path.write_text("# Feature Specification: $ARGUMENTS\n\n## Scenarios\n")

            script_path = Path(repo_dir) / ".specify" / "scripts" / "bash" / "create-new-feature.sh"
            script_path.parent.mkdir(parents=True, exist_ok=True)
            script_path.write_text("#!/usr/bin/env bash\n")

            spec_dir = Path(repo_dir) / "specs" / "001-photo-organizer"
            spec_dir.mkdir(parents=True, exist_ok=True)
            spec_file = spec_dir / "spec.md"

            spec_body = "# Feature Specification: Photo Organizer\n\n## Content\n"

            commands, _, coder = self._make_commands(repo_dir)
            dummy_coder = mock.Mock()
            dummy_coder.run.return_value = spec_body

            with mock.patch(
                "aider.coders.base_coder.Coder.create", return_value=dummy_coder
            ) as mock_create:
                with mock.patch.object(
                    SpeckitCommandsMixin, "_generate_short_name", return_value="photo-organizer"
                ):
                    with mock.patch.object(
                        SpeckitCommandsMixin,
                        "_determine_next_feature_number",
                        return_value=1,
                    ):
                        with mock.patch.object(
                            SpeckitCommandsMixin,
                            "_run_feature_creation_script",
                            return_value={
                                "SPEC_FILE": str(spec_file),
                                "BRANCH_NAME": "001-photo-organizer",
                            },
                        ) as mock_run_script:
                            commands.cmd_speckit_specify("Create organizational spec")

            mock_create.assert_called_once_with(
                io=commands.io,
                from_coder=coder,
                edit_format=coder.main_model.edit_format,
                summarize_from_coder=False,
            )
            mock_run_script.assert_called_once()

            self.assertTrue(spec_file.exists())
            self.assertEqual(spec_body, spec_file.read_text())

            checklist_path = spec_dir / "checklists" / "requirements.md"
            self.assertTrue(checklist_path.exists())
            checklist_contents = checklist_path.read_text()
            self.assertIn("# Specification Quality Checklist: Photo Organizer", checklist_contents)
            self.assertIn("spec.md", checklist_contents)

            self.assertTrue(any(os.path.samefile(spec_file, fname) for fname in coder.abs_fnames))
            self.assertTrue(
                any(os.path.samefile(checklist_path, fname) for fname in coder.abs_fnames)
            )

    def test_cmd_speckit_specify_rejects_malformed_response(self):
        with GitTemporaryDirectory() as repo_dir:
            os.chdir(repo_dir)
            template_path = Path(repo_dir) / ".aider" / "commands" / "speckit.specify.md"
            template_path.parent.mkdir(parents=True, exist_ok=True)
            template_path.write_text("# Feature Specification: $ARGUMENTS\n\n## Scenarios\n")

            script_path = Path(repo_dir) / ".specify" / "scripts" / "bash" / "create-new-feature.sh"
            script_path.parent.mkdir(parents=True, exist_ok=True)
            script_path.write_text("#!/usr/bin/env bash\n")

            spec_dir = Path(repo_dir) / "specs" / "001-photo-organizer"
            spec_dir.mkdir(parents=True, exist_ok=True)
            spec_file = spec_dir / "spec.md"
            initial_content = "Initial placeholder spec\n"
            spec_file.write_text(initial_content)

            commands, io, coder = self._make_commands(repo_dir)
            malformed_response = (
                "<bad>I'll create a feature specification for the photo album organization "
                "application based on the user's description."
            )

            dummy_coder = mock.Mock()
            dummy_coder.run.return_value = malformed_response

            with mock.patch("aider.coders.base_coder.Coder.create", return_value=dummy_coder):
                with mock.patch.object(
                    SpeckitCommandsMixin, "_generate_short_name", return_value="photo-organizer"
                ):
                    with mock.patch.object(
                        SpeckitCommandsMixin,
                        "_determine_next_feature_number",
                        return_value=1,
                    ):
                        with mock.patch.object(
                            SpeckitCommandsMixin,
                            "_run_feature_creation_script",
                            return_value={
                                "SPEC_FILE": str(spec_file),
                                "BRANCH_NAME": "001-photo-organizer",
                            },
                        ):
                            with mock.patch.object(io, "tool_error") as mock_tool_error:
                                with mock.patch.object(io, "tool_output") as mock_tool_output:
                                    commands.cmd_speckit_specify("Create organizational spec")

            mock_tool_error.assert_called_once_with(
                "Specification generation failed: assistant response did not start "
                "with '# Feature Specification:'."
            )
            mock_tool_output.assert_any_call("Assistant response:")
            mock_tool_output.assert_any_call(malformed_response)

            self.assertEqual(initial_content, spec_file.read_text())
            self.assertFalse(any(os.path.samefile(spec_file, fname) for fname in coder.abs_fnames))
