import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const root = new URL("../", import.meta.url);

function pngDimensions(buffer) {
  assert.deepEqual(
    buffer.subarray(0, 8),
    Buffer.from([137, 80, 78, 71, 13, 10, 26, 10]),
    "asset must be a PNG",
  );
  return [buffer.readUInt32BE(16), buffer.readUInt32BE(20)];
}

test("declares production-safe local favicon metadata", async () => {
  const layout = await readFile(new URL("app/layout.tsx", root), "utf8");

  assert.match(layout, /https:\/\/new\.fromtrees\.studio/);
  assert.doesNotMatch(layout, /localhost/);
  assert.match(layout, /"\/favicon-32x32\.png"/);
  assert.match(layout, /"\/favicon\.png"/);
  assert.match(layout, /"\/apple-touch-icon\.png"/);
});

test("favicon assets are valid PNGs at their declared sizes", async () => {
  const assets = new Map([
    ["public/favicon-32x32.png", [32, 32]],
    ["public/favicon.png", [512, 512]],
    ["public/apple-touch-icon.png", [180, 180]],
  ]);

  for (const [path, dimensions] of assets) {
    const image = await readFile(new URL(path, root));
    assert.deepEqual(pngDimensions(image), dimensions, path);
    assert.ok(image.includes(Buffer.from("IHDR")), `${path} has an IHDR chunk`);
    assert.ok(image.includes(Buffer.from("IDAT")), `${path} has image data`);
    assert.ok(image.includes(Buffer.from("IEND")), `${path} is complete`);
  }
});
