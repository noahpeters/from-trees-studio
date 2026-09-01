# From Trees Studio agent instructions

- Preserve the approved hand-sketched furniture artwork and its warm wood shading. Never replace it with crude vector, CSS, or simplified procedural drawings.
- Table and chair geometry is defined in `configurator-geometry.json` and documented in `docs/configurator-geometry.md`. Keep physical relationships in the shared inch model.
- Chair size, orientation, position, and layering are baked into offline sprites. Do not transform individual chairs at display time.
- Every table edge profile uses a complete table image. Do not layer a replacement tabletop over another table image.
- Tabletop surfaces are opaque. Only the true background and legitimate open spaces between furniture members are transparent.
- Rectangle is the production-ready table shape. Circle and oval stay feature-flagged until their artwork is explicitly approved.
- Preserve query-string feature overrides using `env_enable` and `env_disable`.
- Run `npm run verify` before proposing a change. For sprite changes, install `requirements-dev.txt`, run `npm run verify:assets`, and inspect the rendered result plus affected transparent assets against a contrasting background.
- Never push directly to `main`, merge a pull request, or deploy from a Metis coding task. Pull-request merges are human-only, and production deployment must run through GitHub Actions after merge.
