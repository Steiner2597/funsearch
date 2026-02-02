# Sandbox Module (Best-Effort)

This sandbox is a **best-effort** subprocess isolation layer intended for
coursework/research experiments with untrusted LLM-generated code.

## Limitations

- **Not production security**: This is not a hardened sandbox.
- **Bypassable**: A determined adversary can escape or exploit this environment.
- **Best-effort only**: Resource limits and import blocking reduce risk, but do not
  guarantee safety.
- **No filesystem or network access** should be possible under the policy, but
  do not rely on this for real security.

Use only for controlled experiments and educational settings.
