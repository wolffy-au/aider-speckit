import os


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
