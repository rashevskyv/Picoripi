# Default Plugin Template

`default_plugin` is a small, fully loadable Picoripi plugin and the template new plugins are created from:

```powershell
.\venv\Scripts\python.exe tools/new_plugin.py <your_plugin_name> "<Display Name>" --prefix XX
```

The guide for plugin authors is [docs/wiki/3_Plugin_Developer_Guide.md](../../docs/wiki/3_Plugin_Developer_Guide.md);
every hook is listed in the generated [docs/PLUGIN_CONTRACT.md](../../docs/PLUGIN_CONTRACT.md).
`AI_PLUGIN_ASSISTANT_PROMPT.md` in this folder is a prompt you can paste to an AI assistant to write a plugin
with it.
