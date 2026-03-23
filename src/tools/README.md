# tools

This folder contains helper utilities that support the main pipeline but are not the primary production stages themselves.

## Subfolders

- `4data/`: dataset inspection, splitting, and training-sample reshaping utilities
- `4model/`: model-side smoke tests, prompt checks, and API wrapper utilities

## Where to look

- If you need to debug training samples or split datasets, go to `4data/`
- If you need to sanity-check prompts, function-calling outputs, or external model access, go to `4model/`
