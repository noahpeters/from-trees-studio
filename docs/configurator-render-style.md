# From Trees configurator rendering style

This visual specification is intentionally separate from
`configurator-geometry.json`. Geometry defines physical relationships; this
file defines how those relationships are drawn.

The current renderer is a warm architectural-pencil study:

- warm brown-gray lines rather than black or green outlines
- softly irregular primary and secondary strokes
- pale opaque wood surfaces with warmer shading on vertical faces
- restrained, irregular wood-grain marks rather than glue-line-like full-length
  stripes or photorealistic texture
- true transparency outside furniture and through legitimate open spaces
- no background color baked into any asset

The machine-readable palette and stroke settings live in
`configurator-render-style.json`. Another renderer can replace pencil with ink,
watercolor, marker, or a more detailed hand sketch while reading the unchanged
geometry contract.

Furniture silhouettes remain fully opaque. There are no free-floating
construction marks outside the furniture. Texture lines never extend beyond
the corresponding wood surface. The website never recolors, rotates, shears,
or rescales an individual furniture element at display time.
