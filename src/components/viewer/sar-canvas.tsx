"use client";

import * as React from "react";
import type { Incident } from "@/lib/types";
import { LEVEL_COLORS } from "@/components/map/spill-style";

export type ViewerMode = "sar" | "prediction" | "overlay";

function mulberry32(seed: number) {
  let a = seed;
  return () => {
    a |= 0;
    a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

interface Viewport {
  ox: number;
  oy: number;
  w: number;
  h: number;
}

function projectRing(
  ring: [number, number][],
  cw: number,
  ch: number,
  pad = 56
): { pts: [number, number][]; vp: Viewport } {
  let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
  for (const [lon, lat] of ring) {
    minX = Math.min(minX, lon); maxX = Math.max(maxX, lon);
    minY = Math.min(minY, lat); maxY = Math.max(maxY, lat);
  }
  const spanX = Math.max(maxX - minX, 1e-6);
  const spanY = Math.max(maxY - minY, 1e-6);
  const availW = cw - pad * 2;
  const availH = ch - pad * 2;
  const scale = Math.min(availW / spanX, availH / spanY);
  const w = spanX * scale;
  const h = spanY * scale;
  const ox = (cw - w) / 2 - minX * scale;
  const oy = (ch - h) / 2 - minY * scale;
  const pts = ring.map(([lon, lat]) => [lon * scale + ox, lat * scale + oy] as [number, number]);
  return { pts, vp: { ox, oy, w, h } };
}

function tracePath(ctx: CanvasRenderingContext2D, pts: [number, number][]) {
  ctx.beginPath();
  ctx.moveTo(pts[0][0], pts[0][1]);
  for (let i = 1; i < pts.length; i++) ctx.lineTo(pts[i][0], pts[i][1]);
  ctx.closePath();
}

/** Deterministic synthetic Sentinel-1-like GRD image. */
export function SarCanvas({
  incident,
  mode,
  maskOpacity,
}: {
  incident: Incident;
  mode: ViewerMode;
  maskOpacity: number;
}) {
  const canvasRef = React.useRef<HTMLCanvasElement>(null);

  React.useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    const cw = canvas.clientWidth;
    const ch = canvas.clientHeight;
    canvas.width = Math.round(cw * dpr);
    canvas.height = Math.round(ch * dpr);
    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    ctx.scale(dpr, dpr);

    const seed = incident.id.split("").reduce((a, c) => a + c.charCodeAt(0) * 7, 11);
    const rand = mulberry32(seed);
    const ring = incident.geometry.coordinates[0];
    const { pts } = projectRing(ring, cw, ch);

    /* ---- base water ---- */
    const grad = ctx.createLinearGradient(0, 0, cw, ch);
    grad.addColorStop(0, "#11161c");
    grad.addColorStop(1, "#0b1015");
    ctx.fillStyle = grad;
    ctx.fillRect(0, 0, cw, ch);

    /* ---- speckle field ---- */
    const imgData = ctx.getImageData(0, 0, canvas.width, canvas.height);
    // operate on raw pixels at device resolution
    const px = imgData.data;
    for (let i = 0; i < px.length; i += 4) {
      if (rand() < 0.62) continue; // keep some pixels untouched for smoother look
      const n = rand();
      const v = n < 0.9 ? rand() * 22 : 40 + rand() * 70; // mostly faint, few bright speckles
      px[i] = Math.min(255, px[i] + v);
      px[i + 1] = Math.min(255, px[i + 1] + v);
      px[i + 2] = Math.min(255, px[i + 2] + v * 1.05);
    }
    ctx.putImageData(imgData, 0, 0);

    /* ---- land mass (top-left diagonal coastline) ---- */
    const landPath = () => {
      ctx.beginPath();
      ctx.moveTo(-10, -10);
      ctx.lineTo(cw * 0.42, -10);
      ctx.bezierCurveTo(cw * 0.34, ch * 0.16, cw * 0.3, ch * 0.24, cw * 0.18, ch * 0.4);
      ctx.bezierCurveTo(cw * 0.12, ch * 0.5, cw * 0.05, ch * 0.52, -10, ch * 0.55);
      ctx.closePath();
    };
    landPath();
    ctx.fillStyle = "#232a31";
    ctx.fill();

    // land speckle highlight
    ctx.save();
    landPath();
    ctx.clip();
    for (let i = 0; i < 2600; i++) {
      const x = rand() * cw * 0.5;
      const y = rand() * ch;
      const v = rand() * 60;
      ctx.fillStyle = `rgba(${90 + v},${95 + v},${95 + v},0.25)`;
      ctx.fillRect(x, y, 1.6, 1.6);
    }
    ctx.restore();
    landPath();
    ctx.strokeStyle = "rgba(180,200,210,0.5)";
    ctx.lineWidth = 1.4;
    ctx.stroke();

    /* ---- oil slick (smooth, radar-dark region) ---- */
    tracePath(ctx, pts);
    // dampen speckle inside the slick
    ctx.save();
    ctx.clip();
    ctx.fillStyle = "rgba(8,10,13,0.82)";
    ctx.fillRect(0, 0, cw, ch);
    // faint internal streaks
    for (let i = 0; i < 60; i++) {
      const x = pts.reduce((m, p) => Math.min(m, p[0]), Infinity);
      const y = rand() * ch;
      ctx.fillStyle = `rgba(20,26,32,${0.15 + rand() * 0.2})`;
      ctx.fillRect(x, y, cw, 1 + rand() * 2);
    }
    ctx.restore();

    tracePath(ctx, pts);
    ctx.strokeStyle = "rgba(120,140,150,0.35)";
    ctx.lineWidth = 1;
    ctx.stroke();

    /* ---- graticule + frame ---- */
    ctx.strokeStyle = "rgba(80,100,120,0.14)";
    ctx.lineWidth = 1;
    for (let x = 0; x <= cw; x += Math.round(cw / 8)) {
      ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x, ch); ctx.stroke();
    }
    for (let y = 0; y <= ch; y += Math.round(ch / 5)) {
      ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(cw, y); ctx.stroke();
    }

    /* ---- prediction mask ---- */
    if (mode === "prediction" || mode === "overlay") {
      const color = LEVEL_COLORS[incident.level];
      const alpha = mode === "overlay" ? maskOpacity : 1;
      ctx.save();
      tracePath(ctx, pts);
      ctx.clip();
      const mgrad = ctx.createLinearGradient(pts[0][0], pts[0][1], pts[Math.floor(pts.length / 2)][0], pts[Math.floor(pts.length / 2)][1]);
      mgrad.addColorStop(0, `${color.fill}`);
      mgrad.addColorStop(1, color.line);
      ctx.globalAlpha = alpha * 0.75;
      ctx.fillStyle = mgrad;
      ctx.fillRect(0, 0, cw, ch);
      // segmentation confidence texture
      ctx.globalAlpha = alpha * 0.35;
      const mrand = mulberry32(seed + 99);
      for (let i = 0; i < 900; i++) {
        const x = mrand() * cw;
        const y = mrand() * ch;
        ctx.fillStyle = "#ffffff";
        ctx.fillRect(x, y, 1.2, 1.2);
      }
      ctx.restore();

      tracePath(ctx, pts);
      ctx.globalAlpha = alpha;
      ctx.strokeStyle = color.line;
      ctx.lineWidth = 2.2;
      ctx.setLineDash([7, 4]);
      ctx.stroke();
      ctx.setLineDash([]);
      ctx.globalAlpha = 1;

      // centroid marker
      const cx = pts.reduce((s, p) => s + p[0], 0) / pts.length;
      const cy = pts.reduce((s, p) => s + p[1], 0) / pts.length;
      ctx.strokeStyle = "#e6edf5";
      ctx.lineWidth = 1.2;
      ctx.beginPath(); ctx.arc(cx, cy, 6, 0, Math.PI * 2); ctx.stroke();
      ctx.beginPath(); ctx.moveTo(cx - 10, cy); ctx.lineTo(cx - 3, cy);
      ctx.moveTo(cx + 3, cy); ctx.lineTo(cx + 10, cy);
      ctx.moveTo(cx, cy - 10); ctx.lineTo(cx, cy - 3);
      ctx.moveTo(cx, cy + 3); ctx.lineTo(cx, cy + 10);
      ctx.stroke();
    }

    /* ---- HUD annotations ---- */
    ctx.font = "10px ui-monospace, monospace";
    ctx.fillStyle = "rgba(147,164,189,0.85)";
    ctx.fillText(`${incident.satellite} · ${incident.sceneId}`, 12, ch - 12);
    ctx.textAlign = "right";
    ctx.fillText(
      mode === "prediction"
        ? "PREDICTED SLICK MASK"
        : mode === "overlay"
          ? `SAR + PREDICTION · α=${Math.round(maskOpacity * 100)}%`
          : "ORIGINAL SAR GRD",
      cw - 12,
      ch - 12
    );
    ctx.fillText(`INCIDENT ${incident.id}`, cw - 12, 20);
    ctx.textAlign = "left";
    ctx.fillText("VV+VH · IW", 12, 20);
  }, [incident, mode, maskOpacity]);

  return (
    <canvas
      ref={canvasRef}
      className="h-full w-full rounded border border-line bg-base-950"
      role="img"
      aria-label={`Synthetic ${mode} visualization for incident ${incident.id}`}
    />
  );
}
