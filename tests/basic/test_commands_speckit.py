import os
from pathlib import Path
from unittest import TestCase, mock

from aider.coders import Coder
from aider.commands import Commands
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
            with mock.patch.object(
                io, "tool_error"
            ) as mock_tool_error:
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

                dummy_coder.run.assert_called_once_with("Constitution definition: Emphasise testing")
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
                any(
                    os.path.samefile(constitution_path, fname)
                    for fname in coder.abs_fnames
                )
            )
