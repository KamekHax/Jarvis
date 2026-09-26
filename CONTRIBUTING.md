# Contributing to JARVIS Local

Thanks for improving the project. JARVIS Local is MIT-licensed; see `LICENSE` and `TERMS_OF_USE.md`.

## Forks and official inclusion

You may fork and rework the code under the MIT License, retaining its required notices. Changes made in a fork do not need maintainer approval to exist or be shared under that license. **Maintainer approval is required only for inclusion in the official repository, bundled addon catalog, or official release.** Do not describe an unreviewed fork or modified build as official.

## Addon proposals

Before an addon is included in the official catalog, submit its source, user-facing purpose, permission requirements, data/network behavior, and tests for maintainer review. Official addons must be opt-in when they access files, launch apps, write files, use the network, play local media, or connect to external services. Addons must not transmit conversation history or local files without an explicit, documented user command and permission. Include tests demonstrating both allowed and blocked behavior.

Keep optional bundled addons separate from automatically loaded built-in skills unless the maintainer explicitly approves a change to that policy. Include integrity-pin updates when a reviewed bundled module changes.

## Pull requests

Keep changes focused, update documentation and tests, and disclose new dependencies and any network, file, process, or permission side effects. Run `python -m unittest discover -s tests -v` and `python -m compileall .` before proposing a change. The maintainer decides whether a contribution is accepted into the official project.
