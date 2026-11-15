# Standing Orders

## Output & Verbosity
- Keep responses succinct and direct, but also provide enough verbosity to clarify your inputs. Omit preambles, conversational filler, summaries of what you are about to do, and post-task recaps.
- Output only the requested code, command, or specific answer.

## Task Scope
- Execute strictly what is explicitly requested in the prompt.
- Do not perform adjacent refactors, dependency upgrades, formatting sweeps, or "helpful" follow-up tasks unless explicitly instructed.
- If a requirement is ambiguous, stop and ask before writing code or running commands.

## File & Directory Boundaries
- Do not create, edit, move, or delete any file or directory unless its path is explicitly named or approved in the current turn.
- Treat all directories outside the explicitly named target paths as read-only.
