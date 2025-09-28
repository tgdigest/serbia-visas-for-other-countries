from enum import Enum


class HunkState(Enum):
    CONTEXT_BEFORE = 'context_before'
    CHANGES = 'changes'
    CONTEXT_AFTER = 'context_after'


class DiffParser:
    """Parser for abbreviated diff format from OpenAI."""

    def apply(self, content: str, diff: str) -> str:
        """Apply an abbreviated diff to content."""
        lines = content.splitlines(keepends=True)
        diff_lines = diff.splitlines()

        i = 0
        while i < len(diff_lines):
            line = diff_lines[i]

            if line.startswith('@@'):
                i += 1
                hunk_lines = []

                while i < len(diff_lines) and not diff_lines[i].startswith(('@@', '---', '+++')):
                    hunk_lines.append(diff_lines[i])
                    i += 1

                lines = self._apply_hunk(lines, hunk_lines)
            else:
                i += 1

        return ''.join(lines)

    def _find_last_context(self, hunk_lines: list[str]) -> int:
        """Find index of last context line before changes."""
        last_context_idx = -1
        for i, line in enumerate(hunk_lines):
            if line.startswith(('+', '-')):
                break
            if line.startswith(' '):
                last_context_idx = i
        return last_context_idx

    def _process_hunk_line(self, hunk_line: str, lines: list[str], insert_pos: int) -> int:
        """Process a single hunk line and return new insert position."""
        if hunk_line.startswith('-'):
            removed_text = hunk_line[1:].strip()
            for j in range(insert_pos, len(lines)):
                if removed_text in lines[j]:
                    lines.pop(j)
                    break
            return insert_pos
        if hunk_line.startswith('+'):
            addition = hunk_line[1:]
            if not addition.endswith('\n'):
                addition += '\n'
            if insert_pos > 0 and not lines[insert_pos - 1].endswith('\n'):
                lines[insert_pos - 1] += '\n'
            lines.insert(insert_pos, addition)
            return insert_pos + 1
        if hunk_line.startswith(' '):
            return insert_pos + 1
        return insert_pos

    def _apply_context_based_changes(self, lines: list[str], hunk_lines: list[str],
                                      last_context_idx: int) -> list[str]:
        """Apply changes based on context position."""
        context_line = hunk_lines[last_context_idx][1:].strip()

        for file_idx, file_line in enumerate(lines):
            if context_line in file_line:
                insert_pos = file_idx + 1
                for hunk_line in hunk_lines[last_context_idx + 1:]:
                    insert_pos = self._process_hunk_line(hunk_line, lines, insert_pos)

                return lines

        return lines

    def _apply_replacements(self, lines: list[str], removals: list[str],
                            additions: list[str]) -> list[str]:
        """Apply replacement changes."""
        for i, file_line in enumerate(lines):
            if removals[0] in file_line:
                all_match = True
                for j, removal in enumerate(removals):
                    if i + j >= len(lines) or removal not in lines[i + j]:
                        all_match = False
                        break

                if all_match:
                    for _ in removals:
                        lines.pop(i)
                    insert_idx = i
                    for addition in additions:
                        new_line = addition
                        if not new_line.endswith('\n'):
                            new_line += '\n'
                        lines.insert(insert_idx, new_line)
                        insert_idx += 1

                    return lines

        return lines

    def _apply_hunk(self, lines: list[str], hunk_lines: list[str]) -> list[str]:
        """Apply a single hunk to the lines."""

        last_context_idx = self._find_last_context(hunk_lines)
        if last_context_idx >= 0:
            return self._apply_context_based_changes(lines, hunk_lines, last_context_idx)

        removals = []
        additions = []

        for line in hunk_lines:
            if line.startswith('-'):
                removals.append(line[1:].strip())
            elif line.startswith('+'):
                additions.append(line[1:])

        if removals:
            return self._apply_replacements(lines, removals, additions)

        return lines
