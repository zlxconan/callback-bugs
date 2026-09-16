# Ops Agent CodeBuddy Plugin

This distributable plugin contains generated copies of the six canonical Built-in Method Skills and
one Runtime MCP connection. Product and Troubleshooting Skills stay on the Ops Agent server.

Do not edit files under `skills/` directly. Rebuild them from `skills/builtin/` with:

```bash
.venv/bin/python scripts/build_codebuddy_plugin.py
```

Check that generated files are current without changing them:

```bash
.venv/bin/python scripts/build_codebuddy_plugin.py --check
```
