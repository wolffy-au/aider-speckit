# PLAN

When I type the command:
`/speckit.constitution Create principles focused on code quality, testing standards, user experience consistency, and performance requirements`

Aider should refer to the Aider specific markdown template for this command found in `.aider/commands/speckit.constitution.md` and consider the text after `/speckit.constitution` to be provided to the `$ARGUMENTS` part of the speckit.constitution.md template.

This populated template should be then fed into Aider as chat text.

The file that should be updated as a result of this activity is `.specify/memory/constitution.md`. This is the equivalent to `/add .specify/memory/constitution.md` as part of the `/speckit.constitution` command.