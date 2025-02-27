#!/usr/bin/env python3

"""
Pandoc filter that:
  - Detects a raw LaTeX block containing "\appendix"
  - For all headings AFTER that block, applies a custom letter/number scheme:
      Top-level headings: A, B, C, ...
      Subheadings: A.1, A.2, B.1, B.1.1, ...
  - Marks these headings "unnumbered" so that Pandoc's built-in numbering
    won't appear if you use --number-sections.
"""

from pandocfilters import toJSONFilter, Header, RawBlock, Str, Space
from typing import Any

def make_label(stack: list[int]) -> str:
    """
    Convert [x, y, z, ...] into "Letter.y.z..."
    where x is the 1-based letter index (1 => A, 2 => B, etc.)
    and y, z, ... are 1-based sublevels.
    """
    # Example: stack = [1, 2, 1] => "A.2.1"
    letter_index = stack[0]  # 1 => A, 2 => B, etc.
    letter = chr(ord('A') + letter_index - 1)
    if len(stack) == 1:
        return letter
    else:
        subs = ".".join(str(n) for n in stack[1:])
        return f"{letter}.{subs}"

# Class to typecheck function attributes, as suggested in https://github.com/python/mypy/issues/2087
class AppendixFilter:
    in_appendix: bool
    num_stack: list[int]
    def call(self, key: str, value: tuple[str, str], fmt: Any, meta: Any) -> "list[None] | Header":
        ...

appendix_filter: AppendixFilter
def appendix_filter(key: str, value: Any, fmt: Any, meta: Any) -> "list[None] | Header": # type: ignore[no-redef]
    if not hasattr(appendix_filter, "in_appendix"):
        appendix_filter.in_appendix = False
    if not hasattr(appendix_filter, "num_stack"):
        # This list will store counters for each heading level.
        appendix_filter.num_stack = []

    # 1) Detect \appendix
    if key == "RawBlock":
        raw_format, text = value
        if raw_format in ("tex", "latex") and r"\appendix" in text:
            appendix_filter.in_appendix = True
            # Remove the raw block so it doesn't appear in output
            return []

    # 2) If we're past \appendix, apply custom numbering
    if key == "Header" and appendix_filter.in_appendix:
        level, [identifier, classes, kvs], inlines = value
        
        # Make sure num_stack has exactly `level` items
        while len(appendix_filter.num_stack) > level:
            appendix_filter.num_stack.pop()
        while len(appendix_filter.num_stack) < level:
            appendix_filter.num_stack.append(0)

        # Increment the counter at this level
        appendix_filter.num_stack[-1] += 1

        # Construct the alphanumeric label (e.g., "A", "B.1", "C.2.3")
        label = make_label(appendix_filter.num_stack)

        # Prepend the label to the heading text
        new_inlines = [Str(label), Space()] + inlines

        # Mark unnumbered so Pandoc won't re-number them
        if "unnumbered" not in classes:
            classes.append("unnumbered")
        result = Header(level, [identifier, classes, kvs], new_inlines)
        return result
    return None

def main()-> None:
    toJSONFilter(appendix_filter)

if __name__ == "__main__":
    main()
