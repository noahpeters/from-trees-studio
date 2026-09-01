# From Trees configurator geometry

The configurator is built from one renderer-independent physical model. The
authoritative machine-readable specification is `configurator-geometry.json`.
Changing the visual style must not change the measurements, camera, anchors, or
layer order in that file.

## Coordinate system

- Measurements are inches.
- The floor is `y = 0`.
- The table is centered at the world origin.
- `x` runs along the table length.
- `z` runs across the table width. Negative `z` is the camera side.
- Positive `y` is upward.
- A chair's local forward direction is negative `z`. Every occupied chair is
  rotated so that forward points toward the table center.

## Camera and stage

All assets use a 600 × 600 transparent stage, the same fixed camera, a 34°
vertical field of view, and the same projection. The projection is shifted 36
stage pixels left to retain a safety margin around the longest ten-chair scene.
The camera is part of the
geometry contract. A new visual renderer may change line quality, color,
texture, or shading, but it must use the documented camera unchanged unless a
new geometry-version is created.

The three rectangular render bands are canonical physical studies, not browser
scaling targets:

- small: 72 × 42 inches, used for selected lengths 72–84 inches
- medium: 96 × 42 inches, used for selected lengths 90–102 inches
- large: 120 × 42 inches, used for selected lengths 108–120 inches

For example, a selected 84-inch table intentionally uses the 72-inch study.
Adding exact-length artwork later only adds another generated cell; the camera,
chair dimensions, anchors, and occlusion layers remain unchanged.

## Physical furniture dimensions

Tables are 30 inches high with a 1.5-inch top. Rectangular and oval studies are
currently 42 inches wide and use 72-, 96-, and 120-inch canonical lengths.

Chairs have an 18 × 18-inch seat, an 18-inch seat height, and a 38-inch overall
height. The front of a chair seat is three inches beyond the table edge. These
dimensions—not pixel measurements—determine its apparent scale.

## Chair anchors

The atlas contains 26 named reusable locations:

- 12 rectangular-family anchors: five near-side positions, five far-side
  positions, and one position at each end. Rectangles and ovals share this
  relationship model.
- 14 round-family anchors distributed around the table center.

Current rectangular seating subsets use two long-side chairs per side at 72
inches, three per side at 96 inches, and four per side at 120 inches, plus both
end chairs. The chosen subset changes; the physical chair dimensions do not.

## Occlusion and exported layers

Every configuration is exported as three transparent raster layers:

1. Far chairs
2. An opaque table, including the complete tabletop and base
3. Near chairs

Open areas within chair backs and bases remain transparent. Wood surfaces are
opaque. No masks are inferred in the browser.

## Rendering contract

Projection, rotation, sizing, occlusion classification, and object placement
happen during asset generation. The website only selects sprite cells and
draws them at the same stage coordinates. It must not rotate, shear, stretch,
or independently fit chairs and tables at display time.

High-fidelity table masters are normalized offline to the projected bounding
envelope of the measured table for each canonical size. For chairs, the same
physical renderer first creates the exact per-position envelope at the final
3D anchor and yaw. A direction-specific approved chair master (front, rear, or
end view) is then fitted into that envelope and baked into the far or near
atlas layer. The exported pixels therefore already contain the exact scale,
seat direction, layer, and camera relationship for that 18 × 18 × 38-inch
chair. The browser never transforms a generic chair image.

Master selection begins with the fixed camera vector transformed into each
chair's local coordinates after its inward-facing yaw is applied. The resulting
front, rear, or end viewpoint is then resolved through the approved mapping for
that chair family and physical anchor; generated viewpoint labels are not
assumed to mean the same thing across visually different chair families. The
projected envelope is never borrowed or altered, and table length never
introduces an image-width correction: perspective is the only source of
apparent size variation between otherwise identical chairs.

Table bases and tabletop edge treatments are independent artwork layers. A
base master is reused without alteration while the selected profile supplies
its own hand-drawn tabletop: soft-square has lightly eased corners, bullnose
has a fully rounded edge, and rectangular live-edge tops have an irregular
natural perimeter. Each profile is a complete table drawing, never a tabletop
layer composited over another table. Changing the edge must not distort or
erase the approved base.

This separation allows the complete configurator to be regenerated as pencil,
ink, watercolor, technical linework, or another visual language while
preserving identical spatial relationships.
