# CodeDebugArena dashboard UI

This folder contains a dependency-free, static front-end prototype for the benchmark selection, execution, and results screens.

From the repository root, start a local static server:

```bash
python -m http.server 8000 --directory web
```

Then open `http://localhost:8000` in a browser.

The model execution and result values are sample data for the UI prototype. They are not connected to model provider APIs or the Python CLI. Use the repository's `runner.py` commands for actual challenge validation.
