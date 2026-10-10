## What changed

<!-- One or two sentences. Link the issue if there is one. -->

## Checklist

- [ ] `.\tasks.ps1 check` passes locally (dbt build, contracts, TMDL, report).
- [ ] New or changed measures have a `///` description, a display folder and a format string.
- [ ] The model is committed in **local** source mode with the placeholder `DataRoot` (`python scripts/set_model_source.py reset`).
- [ ] If a measure's meaning changed, its `///` description says so and `docs/data-dictionary.md` is regenerated (`.\tasks.ps1 dictionary`).
- [ ] Screenshot attached for any visual change.
