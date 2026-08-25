"use client";

import { useEffect, useRef } from "react";
import { spriteCell } from "./sprite-matrix";
import { spritePath, type BaseSlug, type ChairSlug, type ShapeSlug } from "./catalog";

type V3 = { x: number; y: number; z: number };
type P2 = { x: number; y: number; depth: number };
type Bounds = { x: number; y: number; width: number; height: number };
type Seat = { origin: V3; yaw: number; layer: "far" | "near" };

const CAMERA = { position: { x: -120, y: 95, z: -138 }, target: { x: 0, y: 28, z: 0 }, fov: 48 };
const CHAIR_SHEET = "/chairs/geometry/chair-perspectives-transparent.png";
const CHAIR_STYLE_COLUMN: Record<Exclude<ChairSlug, "none">, number> = {
  "curved-back": 0,
  "ladder-back": 1,
  "spindle-back": 2,
};
const ALPHA_BOUNDS_CACHE = new Map<string, Bounds>();

function sub(a: V3, b: V3): V3 { return { x: a.x - b.x, y: a.y - b.y, z: a.z - b.z }; }
function dot(a: V3, b: V3) { return a.x * b.x + a.y * b.y + a.z * b.z; }
function cross(a: V3, b: V3): V3 { return { x: a.y * b.z - a.z * b.y, y: a.z * b.x - a.x * b.z, z: a.x * b.y - a.y * b.x }; }
function unit(v: V3): V3 { const magnitude = Math.hypot(v.x, v.y, v.z) || 1; return { x: v.x / magnitude, y: v.y / magnitude, z: v.z / magnitude }; }

function projector(width: number, height: number) {
  const forward = unit(sub(CAMERA.target, CAMERA.position));
  const right = unit(cross(forward, { x: 0, y: 1, z: 0 }));
  const up = unit(cross(right, forward));
  const focal = (height * .5) / Math.tan((CAMERA.fov * Math.PI / 180) / 2);
  return (point: V3): P2 => {
    const relative = sub(point, CAMERA.position);
    const depth = dot(relative, forward);
    return {
      x: width / 2 + dot(relative, right) * focal / depth,
      y: height / 2 - dot(relative, up) * focal / depth,
      depth,
    };
  };
}

function rotate(point: V3, origin: V3, yaw: number): V3 {
  const cosine = Math.cos(yaw), sine = Math.sin(yaw);
  const x = point.x - origin.x, z = point.z - origin.z;
  return { x: origin.x + x * cosine - z * sine, y: point.y, z: origin.z + x * sine + z * cosine };
}

function projectedBounds(points: V3[], project: (point: V3) => P2): Bounds {
  const projected = points.map(project);
  const xs = projected.map((point) => point.x), ys = projected.map((point) => point.y);
  const left = Math.min(...xs), top = Math.min(...ys);
  return { x: left, y: top, width: Math.max(...xs) - left, height: Math.max(...ys) - top };
}

function boxCorners(origin: V3, halfWidth: number, height: number, halfDepth: number, yaw = 0) {
  const points: V3[] = [];
  for (const x of [-halfWidth, halfWidth]) for (const y of [0, height]) for (const z of [-halfDepth, halfDepth]) {
    points.push(rotate({ x: origin.x + x, y, z: origin.z + z }, origin, yaw));
  }
  return points;
}

function alphaBounds(image: HTMLImageElement, source: Bounds): Bounds {
  const cacheKey = `${image.currentSrc}|${source.x}|${source.y}|${source.width}|${source.height}`;
  const cached = ALPHA_BOUNDS_CACHE.get(cacheKey);
  if (cached) return cached;
  const canvas = document.createElement("canvas");
  canvas.width = Math.max(1, Math.round(source.width));
  canvas.height = Math.max(1, Math.round(source.height));
  const context = canvas.getContext("2d", { willReadFrequently: true });
  if (!context) return { x: 0, y: 0, width: source.width, height: source.height };
  context.drawImage(image, source.x, source.y, source.width, source.height, 0, 0, canvas.width, canvas.height);
  const data = context.getImageData(0, 0, canvas.width, canvas.height).data;
  const count = canvas.width * canvas.height;
  const occupied = new Uint8Array(count), visited = new Uint8Array(count);
  for (let index = 0; index < count; index++) occupied[index] = data[index * 4 + 3] >= 32 ? 1 : 0;
  let winner = { size: 0, left: 0, right: canvas.width - 1, top: 0, bottom: canvas.height - 1 };
  const queue = new Int32Array(count);
  for (let start = 0; start < count; start++) {
    if (!occupied[start] || visited[start]) continue;
    let head = 0, tail = 0, size = 0;
    let left = canvas.width, right = -1, top = canvas.height, bottom = -1;
    queue[tail++] = start; visited[start] = 1;
    while (head < tail) {
      const index = queue[head++], x = index % canvas.width, y = Math.floor(index / canvas.width);
      size++; left = Math.min(left, x); right = Math.max(right, x); top = Math.min(top, y); bottom = Math.max(bottom, y);
      const neighbors = [index - 1, index + 1, index - canvas.width, index + canvas.width];
      for (const next of neighbors) {
        if (next < 0 || next >= count || visited[next] || !occupied[next]) continue;
        if ((next === index - 1 || next === index + 1) && Math.floor(next / canvas.width) !== y) continue;
        visited[next] = 1; queue[tail++] = next;
      }
    }
    if (size > winner.size) winner = { size, left, right, top, bottom };
  }
  const result = winner.size
    ? { x: winner.left, y: winner.top, width: winner.right - winner.left + 1, height: winner.bottom - winner.top + 1 }
    : { x: 0, y: 0, width: canvas.width, height: canvas.height };
  ALPHA_BOUNDS_CACHE.set(cacheKey, result);
  return result;
}

function drawFitted(context: CanvasRenderingContext2D, image: HTMLImageElement, source: Bounds, target: Bounds) {
  const visible = alphaBounds(image, source);
  const scaleX = target.width / visible.width, scaleY = target.height / visible.height;
  context.save();
  context.beginPath();
  context.rect(target.x - 8, target.y - 8, target.width + 16, target.height + 16);
  context.clip();
  context.drawImage(
    image,
    source.x, source.y, source.width, source.height,
    target.x - visible.x * scaleX,
    target.y - visible.y * scaleY,
    source.width * scaleX,
    source.height * scaleY,
  );
  context.restore();
}

function seatFacingTable(origin: V3): Seat {
  const direction = sub({ x: 0, y: 0, z: 0 }, origin);
  const yaw = Math.atan2(direction.x, -direction.z);
  const forward = unit(sub(CAMERA.target, CAMERA.position));
  const centerDepth = dot(sub({ x: 0, y: 0, z: 0 }, CAMERA.position), forward);
  const layer = dot(sub(origin, CAMERA.position), forward) > centerDepth ? "far" : "near";
  return { origin, yaw, layer };
}

function rectangleSeats(length: number, width: number): Seat[] {
  const count = length <= 84 ? 2 : length <= 102 ? 3 : 4;
  const halfLength = length / 2, halfWidth = width / 2, offset = 13, usable = length - 30;
  const seats: Seat[] = [];
  for (let index = 0; index < count; index++) {
    const z = count === 1 ? 0 : -usable / 2 + index * (usable / (count - 1));
    seats.push(seatFacingTable({ x: -halfWidth - offset, y: 0, z }));
    seats.push(seatFacingTable({ x: halfWidth + offset, y: 0, z }));
  }
  seats.push(seatFacingTable({ x: 0, y: 0, z: -halfLength - offset }));
  seats.push(seatFacingTable({ x: 0, y: 0, z: halfLength + offset }));
  return seats;
}

function roundSeats(diameter: number): Seat[] {
  const count = diameter <= 48 ? 6 : diameter <= 60 ? 8 : 10;
  const radius = diameter / 2 + 13;
  return Array.from({ length: count }, (_, index) => {
    const angle = -Math.PI / 2 + index * Math.PI * 2 / count;
    const origin = { x: Math.cos(angle) * radius, y: 0, z: Math.sin(angle) * radius };
    return seatFacingTable(origin);
  });
}

function chairRow(seat: Seat) {
  const toCamera = sub(CAMERA.position, seat.origin);
  const cosine = Math.cos(-seat.yaw), sine = Math.sin(-seat.yaw);
  const localX = toCamera.x * cosine - toCamera.z * sine;
  const localZ = toCamera.x * sine + toCamera.z * cosine;
  if (Math.abs(localX) > Math.abs(localZ) * 1.75) return localX < 0 ? 4 : 5;
  if (localZ < 0) return localX < 0 ? 0 : 1;
  return localX < 0 ? 2 : 3;
}

function loadImage(source: string) {
  return new Promise<HTMLImageElement>((resolve, reject) => {
    const image = new Image();
    image.onload = () => resolve(image); image.onerror = reject; image.src = source;
  });
}

export function GeometryComposition({
  shape, base, edgeColumn, row, length, width, diameter, chair, label,
}: {
  shape: ShapeSlug; base: BaseSlug; edgeColumn: number; row: number;
  length: number; width: number; diameter: number; chair: ChairSlug; label: string;
}) {
  const reference = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = reference.current;
    if (!canvas) return;
    let cancelled = false;
    const tableSource = spritePath(shape, base);

    Promise.all([loadImage(tableSource), chair === "none" ? Promise.resolve(null) : loadImage(CHAIR_SHEET)]).then(([tableImage, chairImage]) => {
      if (cancelled) return;
      const rectangle = canvas.getBoundingClientRect();
      const dpr = Math.min(2, window.devicePixelRatio || 1);
      canvas.width = Math.round(rectangle.width * dpr); canvas.height = Math.round(rectangle.height * dpr);
      const context = canvas.getContext("2d"); if (!context) return;
      context.scale(dpr, dpr); context.clearRect(0, 0, rectangle.width, rectangle.height);
      const project = projector(rectangle.width, rectangle.height);
      const tableLength = shape === "circle" ? diameter : length;
      const tableWidth = shape === "circle" ? diameter : width;
      const seats = chair === "none" ? [] : shape === "circle" ? roundSeats(diameter) : rectangleSeats(tableLength, tableWidth);
      const chairCellWidth = chairImage ? chairImage.naturalWidth / 3 : 0;
      const chairCellHeight = chairImage ? chairImage.naturalHeight / 6 : 0;

      const drawSeats = (layer: "far" | "near") => {
        if (!chairImage || chair === "none") return;
        seats.filter((seat) => seat.layer === layer)
          .sort((a, b) => project(b.origin).depth - project(a.origin).depth)
          .forEach((seat) => {
            const source = { x: CHAIR_STYLE_COLUMN[chair] * chairCellWidth, y: chairRow(seat) * chairCellHeight, width: chairCellWidth, height: chairCellHeight };
            const target = projectedBounds(boxCorners(seat.origin, 9.5, 38, 9, seat.yaw), project);
            drawFitted(context, chairImage, source, target);
          });
      };

      drawSeats("far");
      const cell = spriteCell(shape, base, edgeColumn, row);
      const tableCell = { x: cell.x * tableImage.naturalWidth, y: cell.y * tableImage.naturalHeight, width: cell.width * tableImage.naturalWidth, height: cell.height * tableImage.naturalHeight };
      const tableBounds = projectedBounds(boxCorners({ x: 0, y: 0, z: 0 }, tableWidth / 2, 30, tableLength / 2), project);
      drawFitted(context, tableImage, tableCell, tableBounds);
      drawSeats("near");
    }).catch(() => undefined);

    return () => { cancelled = true; };
  }, [shape, base, edgeColumn, row, length, width, diameter, chair]);

  return <canvas ref={reference} className="geometry-composition" role="img" aria-label={label}/>;
}

export const geometryChairAssetPaths = [CHAIR_SHEET];
