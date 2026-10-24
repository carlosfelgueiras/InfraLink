{{rules}}

---

## Diagnostic to assess

- Repository: `{{repo}}`
- Commit: `{{commit}}`
- Module entrypoint: `{{module_dir}}`
- Source (the resource that should depend on the target): `{{node}}`
- Target (the resource it should depend on): `{{target}}`

Description:

{{message}}

---

## Your environment

- The current working directory is a snapshot of the repository at the commit above. It contains only the file tree, with no git history. The module entrypoint path is relative to this directory.
- Resource addresses are relative to the module entrypoint. `:resource.<type>.<name>` is declared directly in the entrypoint. `module.<call>:resource.<type>.<name>` is declared inside the module that `module "<call>"` instantiates (follow its `source`).
- You can use web search and web fetch for external information, such as provider documentation. Do not look at this repository's history or later versions (commits, pull requests, issues, or other branches after commit `{{commit}}`).
- End your final message with a single line containing exactly one word, either `Correct` or `Incorrect`.
