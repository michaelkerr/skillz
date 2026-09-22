# Zero-to-one GTM

A Cursor skill for a founder-led search from a rough product idea toward a repeatable first ten customers. Stages are Frame, Discover, Design, Validate, Commit, Activate, and Learn. Gates are checklists. The evidence for each product lives in its own folder, copied from `templates/`.

This directory is the source. Cursor runs the installed copy at `~/.cursor/skills/zero-to-one-gtm`. After changing the source, install it again:

```bash
rm -rf ~/.cursor/skills/zero-to-one-gtm
cp -R . ~/.cursor/skills/zero-to-one-gtm
```

Run that from this directory. Edits made only in the Cursor copy can be copied back here the same way, in reverse.

## Start a product folder

```bash
mkdir -p ~/Projects/<product>-gtm
cp -R templates/. ~/Projects/<product>-gtm/
```

Then work in that folder. `~/Projects/gtm` is the first one, still in Frame.
