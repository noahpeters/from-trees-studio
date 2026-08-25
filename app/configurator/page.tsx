"use client";

/* eslint-disable react-hooks/set-state-in-effect */

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import {
  basesForShape,
  chairLayerPath,
  chairs,
  edgesForShape,
  shapes,
  spritePath,
  type BaseSlug,
  type ChairSlug,
  type EdgeSlug,
  type ShapeSlug,
} from "./catalog";
import { backgroundForCell, spriteCell } from "./sprite-matrix";

const timbers = [
  { name: "White oak", slug: "white-oak", color: "#c3a579" },
  { name: "Black walnut", slug: "black-walnut", color: "#594334" },
  { name: "Hard maple", slug: "hard-maple", color: "#d0b891" },
];

const activeShapes = shapes;
const baseUrlSlugs: Partial<Record<BaseSlug, string>> = { "curved-slab-frame": "curved-slab" };
const preloadedSprites = new Set<string>();

function baseUrlSlug(base: BaseSlug) {
  return baseUrlSlugs[base] ?? base;
}

function baseFromUrl(slug: string) {
  return (Object.entries(baseUrlSlugs).find(([, value]) => value === slug)?.[0] ?? slug) as BaseSlug;
}

function rowForSize(shape: ShapeSlug, size: number) {
  if (shape === "circle") return size <= 48 ? 0 : size <= 60 ? 1 : 2;
  return size <= 84 ? 0 : size <= 102 ? 1 : 2;
}

export default function Configurator() {
  const [shape, setShape] = useState<ShapeSlug>("rectangle");
  const [timber, setTimber] = useState(timbers[0]);
  const [length, setLength] = useState(84);
  const [diameter, setDiameter] = useState(54);
  const [width, setWidth] = useState(40);
  const [edge, setEdge] = useState<EdgeSlug>("soft-square");
  const [base, setBase] = useState<BaseSlug>("curved-slab-frame");
  const [chair, setChair] = useState<ChairSlug>("none");
  const [urlReady, setUrlReady] = useState(false);

  const availableEdges = edgesForShape(shape);
  const availableBases = basesForShape(shape);
  const selectedEdge = availableEdges.find((item) => item.slug === edge) ?? availableEdges[0];
  const selectedBase = availableBases.find((item) => item.slug === base) ?? availableBases[0];
  const size = shape === "circle" ? diameter : length;
  const row = rowForSize(shape, size);
  const dimension = shape === "circle" ? `${diameter}\u2033 diameter` : `${length}\u2033 \u00d7 ${width}\u2033`;
  const seats = useMemo(() => chair === "none"
    ? (shape === "circle" ? Math.max(4, Math.round(diameter / 10)) : Math.max(6, Math.floor(length / 24) * 2))
    : [6, 8, 10][row], [chair, shape, diameter, length, row]);

  function chooseShape(nextShape: ShapeSlug) {
    const nextEdges = edgesForShape(nextShape);
    const nextBases = basesForShape(nextShape);
    setShape(nextShape);
    if (!nextEdges.some((item) => item.slug === edge)) setEdge(nextEdges[0].slug);
    if (!nextBases.some((item) => item.slug === base)) setBase(nextBases[0].slug);
  }

  function preloadStudy(nextShape: ShapeSlug, nextBase: BaseSlug) {
    const source = spritePath(nextShape, nextBase);
    if (preloadedSprites.has(source)) return;
    const image = new window.Image();
    image.src = source;
    preloadedSprites.add(source);
  }

  function preloadChair(nextShape: ShapeSlug, nextChair: ChairSlug) {
    if (nextChair === "none") return;
    (["back", "front"] as const).forEach((layer) => {
      const source = chairLayerPath(nextShape, nextChair, layer);
      if (preloadedSprites.has(source)) return;
      const image = new window.Image();
      image.src = source;
      preloadedSprites.add(source);
    });
  }

  function preloadShape(nextShape: ShapeSlug) {
    const nextBases = basesForShape(nextShape);
    const nextBase = nextBases.some((item) => item.slug === selectedBase.slug)
      ? selectedBase.slug
      : nextBases[0].slug;
    preloadStudy(nextShape, nextBase);
    preloadChair(nextShape, chair);
  }

  useEffect(() => {
    const encoded = window.location.search.slice(1).replace(/=$/, "");
    if (!encoded) {
      setUrlReady(true);
      return;
    }
    const parts = encoded.split("--").map(decodeURIComponent);
    const nextShape = parts[0] as ShapeSlug;
    if (!activeShapes.some((item) => item.slug === nextShape)) {
      setUrlReady(true);
      return;
    }
    const nextTimber = timbers.find((item) => item.slug === parts[1]);
    const nextSize = Number(parts[2]);
    const edgeIndex = nextShape === "circle" ? 3 : 4;
    const baseIndex = nextShape === "circle" ? 4 : 5;
    const chairIndex = nextShape === "circle" ? 5 : 6;
    const nextEdge = parts[edgeIndex] as EdgeSlug;
    const nextBase = baseFromUrl(parts[baseIndex] ?? "");
    const nextChair = parts[chairIndex] as ChairSlug;
    setShape(nextShape);
    if (nextTimber) setTimber(nextTimber);
    if (Number.isFinite(nextSize)) {
      if (nextShape === "circle") setDiameter(Math.min(72, Math.max(42, nextSize)));
      else setLength(Math.min(120, Math.max(72, nextSize)));
    }
    if (nextShape !== "circle") {
      const nextWidth = Number(parts[3]);
      if ([36, 40, 42, 44].includes(nextWidth)) setWidth(nextWidth);
    }
    if (edgesForShape(nextShape).some((item) => item.slug === nextEdge)) setEdge(nextEdge);
    if (basesForShape(nextShape).some((item) => item.slug === nextBase)) setBase(nextBase);
    else setBase(basesForShape(nextShape)[0].slug);
    if (chairs.some((item) => item.slug === nextChair)) setChair(nextChair);
    setUrlReady(true);
  }, []);

  useEffect(() => {
    if (!urlReady) return;
    const parts = shape === "circle"
      ? [shape, timber.slug, String(diameter), edge, baseUrlSlug(selectedBase.slug), chair]
      : [shape, timber.slug, String(length), String(width), edge, baseUrlSlug(selectedBase.slug), chair];
    window.history.replaceState(null, "", `/configurator?${parts.join("--")}`);
  }, [urlReady, shape, timber.slug, diameter, length, width, edge, selectedBase.slug, chair]);

  const cell = spriteCell(shape, selectedBase.slug, selectedEdge.column, row);
  // A dining table does not get taller when it gets longer, and its chairs do
  // not change size. Only the horizontal table footprint and chair spacing do.
  const tableScaleX = [0.68, 0.78, 0.86][row];
  const tableScaleY = 0.76;
  const compositionScale = [1.12, 1.04, 0.98][row];
  // Position atlases already contain perspective-correct chair sizing. Never
  // scale the completed layer: doing so drags every anchored chair toward the
  // center of the image and destroys the seating arrangement.
  const chairScale = 1;
  const spriteStyle = {
    backgroundImage: `url(${spritePath(shape, selectedBase.slug)})`,
    ...backgroundForCell(cell),
    transform: `scaleX(${tableScaleX * compositionScale}) scaleY(${tableScaleY * compositionScale})`,
  };
  const chairCellStyle = {
    ...backgroundForCell({ x: 0, y: row / 3, width: 1, height: 1 / 3 }),
  };
  const chairBackStyle = chair === "none" ? undefined : { backgroundImage: `url(${chairLayerPath(shape, chair, "back")})`, ...chairCellStyle, transform: `scale(${chairScale})` };
  const chairFrontStyle = chair === "none" ? undefined : { backgroundImage: `url(${chairLayerPath(shape, chair, "front")})`, ...chairCellStyle, transform: `scale(${chairScale})` };
  const chairName = chairs.find((item) => item.slug === chair)?.name ?? "None";

  const subject = `Table study \u2014 ${shape}, ${timber.name}, ${dimension}`;
  const body = `I\u2019d like to discuss a ${dimension} ${shape} table in ${timber.name}, with a ${selectedEdge.name.toLowerCase()} edge, ${selectedBase.name.toLowerCase()} base, and ${chair === "none" ? "no chair study" : `${chairName.toLowerCase()} chairs`}.`;

  return <main className="config-page">
    <header className="config-header"><Link className="brand" href="/"><img className="brand-tree" src="/from-trees-tree.png" alt=""/><span>from trees</span></Link><Link href="/">Back to the studio</Link></header>
    <section className="config-page-intro"><p className="eyebrow">Table configurator</p><h1>Begin with<br/><em>a line.</em></h1><p>Explore the broad strokes of your table through a working concept study. This is the beginning of a conversation, not a final design or quote.<br/><Link className="geometry-link" href="/configurator/geometry">View the dimensioned spatial study →</Link></p></section>
    <section className="sketch-config">
      <div className="sketch-board">
        <div className="sketch-label"><span>Concept study</span><span>{selectedBase.name}</span></div>
        <div className="rendered-study"><div className="rendered-stage" role="img" aria-label={`${selectedEdge.name} ${shape} table with a ${selectedBase.name} base${chair === "none" ? "" : ` and ${chairName.toLowerCase()} chairs`}`}>
          {chair !== "none" && <div className="rendered-layer chair-layer chairs-occluded" style={chairBackStyle}/>}
          <div className="rendered-layer table-layer" style={spriteStyle}/>
          {chair !== "none" && <div className="rendered-layer chair-layer chairs-unoccluded" style={chairFrontStyle}/>}
        </div></div>
        <div className="study-spec"><strong>{dimension}</strong><span>{timber.name} / {selectedEdge.name}</span></div>
        <div className="sketch-caption"><span>Seats approximately {seats}</span><span>Concept only · not to scale</span></div>
      </div>
      <form className="controls" onSubmit={(event) => event.preventDefault()}>
        <fieldset><legend>Table shape</legend><div className="choice-row">{activeShapes.map((item) => <button type="button" className={shape === item.slug ? "active" : ""} onPointerEnter={() => preloadShape(item.slug)} onFocus={() => preloadShape(item.slug)} onClick={() => chooseShape(item.slug)} key={item.slug}>{item.name}</button>)}</div></fieldset>
        <fieldset><legend>Timber</legend><div className="choice-row timber-row">{timbers.map((item) => <button type="button" className={timber.name === item.name ? "active" : ""} onClick={() => setTimber(item)} key={item.name}><i style={{background:item.color}}/>{item.name}</button>)}</div></fieldset>
        {shape === "circle" ? <fieldset><legend>Diameter</legend><div className="range-wrap"><input aria-label="Table diameter" type="range" min="42" max="72" step="6" value={diameter} onChange={(event) => setDiameter(Number(event.target.value))}/><div><span>42&quot;</span><strong>{diameter}&quot;</strong><span>72&quot;</span></div></div></fieldset> : <>
          <fieldset><legend>Length</legend><div className="range-wrap"><input aria-label="Table length" type="range" min="72" max="120" step="6" value={length} onChange={(event) => setLength(Number(event.target.value))}/><div><span>72&quot;</span><strong>{length}&quot;</strong><span>120&quot;</span></div></div></fieldset>
          <fieldset><legend>Width</legend><div className="choice-row">{[36,40,42,44].map((item) => <button type="button" className={width === item ? "active" : ""} onClick={() => setWidth(item)} key={item}>{item}&quot;</button>)}</div></fieldset>
        </>}
        <fieldset><legend>Edge profile</legend><div className="choice-row">{availableEdges.map((item) => <button type="button" className={edge === item.slug ? "active" : ""} onClick={() => setEdge(item.slug)} key={item.slug}>{item.name}</button>)}</div></fieldset>
        <fieldset><legend>Base study</legend><div className="choice-row base-options">{availableBases.map((item) => <button type="button" className={base === item.slug ? "active" : ""} onPointerEnter={() => preloadStudy(shape, item.slug)} onFocus={() => preloadStudy(shape, item.slug)} onClick={() => setBase(item.slug)} key={item.slug}>{item.name}</button>)}</div></fieldset>
        <fieldset><legend>Chair study</legend><div className="choice-row chair-options">{chairs.map((item) => <button type="button" className={chair === item.slug ? "active" : ""} onPointerEnter={() => preloadChair(shape, item.slug)} onFocus={() => preloadChair(shape, item.slug)} onClick={() => setChair(item.slug)} key={item.slug}>{item.name}</button>)}</div></fieldset>
        <a className="inquiry-button" href={`mailto:furniture@from-trees.com?subject=${encodeURIComponent(subject)}&body=${encodeURIComponent(body)}`}>Send this study <span>↗</span></a>
        <p className="fine-print">We’ll confirm proportion, joinery, timber availability, finish, timing, and all final details together. No prices or purchasing are shown here.</p>
      </form>
    </section>
  </main>;
}
