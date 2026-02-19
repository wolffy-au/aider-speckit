from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass
class ChatChunks:
    system: List = field(default_factory=list)
    examples: List = field(default_factory=list)
    done: List = field(default_factory=list)
    repo: List = field(default_factory=list)
    readonly_files: List = field(default_factory=list)
    chat_files: List = field(default_factory=list)
    cur: List = field(default_factory=list)
    reminder: List = field(default_factory=list)

    def all_messages(self):
        return (
            self.system
            + self.examples
            + self.readonly_files
            + self.repo
            + self.done
            + self.chat_files
            + self.cur
            + self.reminder
        )

    def add_cache_control_headers(self):
        if self.examples:
            self.add_cache_control(self.examples)
        else:
            self.add_cache_control(self.system)

        if self.repo:
            # this will mark both the readonly_files and repomap chunk as cacheable
            self.add_cache_control(self.repo)
        else:
            # otherwise, just cache readonly_files if there are any
            self.add_cache_control(self.readonly_files)

        self.add_cache_control(self.chat_files)

    def add_cache_control(self, messages):
        if not messages:
            return

        content_value = messages[-1]["content"]
        if isinstance(content_value, str):
            content: Dict[str, Any] = {
                "type": "text",
                "text": content_value,
            }
        else:
            content = content_value

        content["cache_control"] = {"type": "ephemeral"}

        messages[-1]["content"] = content

    def cacheable_messages(self):
        messages = self.all_messages()
        for i, message in enumerate(reversed(messages)):
            if isinstance(message.get("content"), list) and message["content"][0].get(
                "cache_control"
            ):
                return messages[: len(messages) - i]
        return messages
