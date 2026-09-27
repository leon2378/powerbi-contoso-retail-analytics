## What changed

<!-- One or two sentences. Link the issue if there is one. -->

## Checklist

- [ ] `.\tasks.ps1 check` passes locally (dbt build, contracts, TMDL, report).
- [ ] New or changed measures have a `///` description, a display folder and a format string.
- [ ] The model is committed in **local** source mode with the placeholder `DataRoot` (`python scripts/set_model_source.py reset`).
- [ ] KPI definitions in `docs/kpi-definitions.md` are updated if a measure's meaning changed.
- [ ] Screenshot attached for any visual change.
