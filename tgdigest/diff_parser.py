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
    
    def _apply_hunk(self, lines: list[str], hunk_lines: list[str]) -> list[str]:
        """Apply a single hunk to the lines."""
        
        # Find the last context line before changes
        last_context_idx = -1
        for i, line in enumerate(hunk_lines):
            if line.startswith(('+', '-')):
                break
            if line.startswith(' '):
                last_context_idx = i
        
        # If we have context, use it to find position
        if last_context_idx >= 0:
            context_line = hunk_lines[last_context_idx][1:].strip()
            
            # Find this context in the original
            for file_idx, file_line in enumerate(lines):
                if context_line in file_line:
                    # Found context, now apply changes after it
                    insert_pos = file_idx + 1
                    
                    # Process the changes
                    for hunk_line in hunk_lines[last_context_idx + 1:]:
                        if hunk_line.startswith('-'):
                            # Find and remove this line
                            removed_text = hunk_line[1:].strip()
                            for j in range(insert_pos, len(lines)):
                                if removed_text in lines[j]:
                                    lines.pop(j)
                                    break
                        elif hunk_line.startswith('+'):
                            # Add new line
                            addition = hunk_line[1:]
                            if not addition.endswith('\n'):
                                addition += '\n'
                            # Make sure previous line has newline
                            if insert_pos > 0 and not lines[insert_pos - 1].endswith('\n'):
                                lines[insert_pos - 1] += '\n'
                            lines.insert(insert_pos, addition)
                            insert_pos += 1
                        elif hunk_line.startswith(' '):
                            # Context line, just skip ahead
                            insert_pos += 1
                    
                    return lines
        
        # No context found, try to handle replacements
        removals = []
        additions = []
        
        for line in hunk_lines:
            if line.startswith('-'):
                removals.append(line[1:].strip())
            elif line.startswith('+'):
                additions.append(line[1:])
        
        if removals:
            # Find and replace
            for i, file_line in enumerate(lines):
                if removals[0] in file_line:
                    # Check if all removals match consecutive lines
                    all_match = True
                    for j, removal in enumerate(removals):
                        if i + j >= len(lines) or removal not in lines[i + j]:
                            all_match = False
                            break
                    
                    if all_match:
                        # Remove old lines
                        for _ in removals:
                            lines.pop(i)
                        
                        # Insert new lines
                        for addition in additions:
                            if not addition.endswith('\n'):
                                addition += '\n'
                            lines.insert(i, addition)
                            i += 1
                        
                        return lines
        
        return lines