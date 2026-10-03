"use client";

import * as React from "react";
import type { Map as MapLibreMap } from "maplibre-gl";
import type { EnvironmentalGrid } from "@/lib/types";

interface WindParticle {
  x: number;
  y: number;
  vx: number;
  vy: number;
  life: number;
  maxLife: number;
  speed: number;
}

/**
 * Bilinear interpolation on a regular grid.
 * Returns null if the query point is outside the grid.
 */
function bilinearInterpolate(
  grid: (number | null)[][],
  lats: number[],
  lons: number[],
  queryLat: number,
  queryLon: number,
): number | null {
  if (lats.length < 2 || lons.length < 2) return null;

  // Find bounding indices
  let latIdx = lats.findIndex((v) => v >= queryLat);
  let lonIdx = lons.findIndex((v) => v >= queryLon);

  if (latIdx === -1) latIdx = lats.length - 1;
  if (lonIdx === -1) lonIdx = lons.length - 1;

  if (latIdx === 0) latIdx = 1;
  if (lonIdx === 0) lonIdx = 1;

  const i0 = latIdx - 1;
  const i1 = latIdx;
  const j0 = lonIdx - 1;
  const j1 = lonIdx;

  const lat0 = lats[i0];
  const lat1 = lats[i1];
  const lon0 = lons[j0];
  const lon1 = lons[j1];

  if (lat1 === lat0 || lon1 === lon0) return null;

  const dlat = (queryLat - lat0) / (lat1 - lat0);
  const dlon = (queryLon - lon0) / (lon1 - lon0);

  const v00 = grid[i0]?.[j0];
  const v01 = grid[i0]?.[j1];
  const v10 = grid[i1]?.[j0];
  const v11 = grid[i1]?.[j1];

  if (v00 == null || v01 == null || v10 == null || v11 == null) return null;

  const val =
    v00 * (1 - dlat) * (1 - dlon) +
    v01 * (1 - dlat) * dlon +
    v10 * dlat * (1 - dlon) +
    v11 * dlat * dlon;

  return val;
}

/**
 * Canvas-based environmental flow visualization (Windy-style).
 * Renders flowing wind/current particles using requestAnimationFrame.
 *
 * When grid data is provided, uses real environmental vectors.
 * When grid data is null, uses a simulated flow field (DEMO mode).
 */
export function EnvironmentalFlowLayer({
  map,
  visible,
  type,
  speed,
  grid,
}: {
  map: MapLibreMap | null;
  visible: boolean;
  type: "wind" | "current";
  speed: number;
  grid: EnvironmentalGrid | null;
}) {
  const canvasRef = React.useRef<HTMLCanvasElement | null>(null);
  const particlesRef = React.useRef<WindParticle[]>([]);
  const animFrameRef = React.useRef<number>(0);

  // Get vector at pixel position using grid data or fallback
  const getFieldVector = React.useCallback(
    (x: number, y: number): { vx: number; vy: number } => {
      if (!map) {
        return { vx: 0, vy: 0 };
      }

      // Convert pixel to geographic coordinates
      const bounds = map.getBounds();
      if (!bounds) return { vx: 0, vy: 0 };

      const canvas = canvasRef.current;
      if (!canvas) return { vx: 0, vy: 0 };

      const w = canvas.clientWidth || canvas.width;
      const h = canvas.clientHeight || canvas.height;
      if (w === 0 || h === 0) return { vx: 0, vy: 0 };

      const lon = bounds.getWest() + (x / w) * (bounds.getEast() - bounds.getWest());
      const lat = bounds.getNorth() - (y / h) * (bounds.getNorth() - bounds.getSouth());

      const uGrid = type === "wind" ? grid?.windU : grid?.currentU;
      const vGrid = type === "wind" ? grid?.windV : grid?.currentV;

      if (uGrid && vGrid && grid?.lats && grid?.lons) {
        const u = bilinearInterpolate(uGrid, grid.lats, grid.lons, lat, lon);
        const v = bilinearInterpolate(vGrid, grid.lats, grid.lons, lat, lon);

        if (u !== null && v !== null) {
          // Convert m/s to pixel velocity (scale for visual appeal)
          const scale = type === "wind" ? 8.0 : 15.0;
          return { vx: u * scale, vy: -v * scale }; // negative v because screen y is flipped
        }
      }

      // Fallback: sinusoidal flow field (DEMO mode)
      const scale = 0.003;
      const angle =
        type === "wind"
          ? Math.sin(x * scale) * 0.6 + Math.cos(y * scale * 1.3) * 0.4 + 2.4
          : Math.cos(x * scale * 0.8) * 0.5 + Math.sin(y * scale) * 0.7 + 0.8;

      const magnitude = type === "wind" ? 40 : 20;
      return {
        vx: Math.cos(angle) * magnitude,
        vy: Math.sin(angle) * magnitude,
      };
    },
    [map, type, grid]
  );

  // Initialize particles
  const initParticles = React.useCallback(
    (width: number, height: number) => {
      const count = 200;
      const particles: WindParticle[] = [];
      for (let i = 0; i < count; i++) {
        const x = Math.random() * width;
        const y = Math.random() * height;
        const vec = getFieldVector(x, y);
        particles.push({
          x,
          y,
          vx: vec.vx,
          vy: vec.vy,
          life: Math.random() * 80,
          maxLife: 60 + Math.random() * 40,
          speed: 0.5 + Math.random() * 0.5,
        });
      }
      particlesRef.current = particles;
    },
    [getFieldVector]
  );

  React.useEffect(() => {
    if (!map || !canvasRef.current || !visible) {
      if (canvasRef.current) {
        const ctx = canvasRef.current.getContext("2d");
        if (ctx) ctx.clearRect(0, 0, canvasRef.current.width, canvasRef.current.height);
      }
      return;
    }

    const canvas = canvasRef.current;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const parent = canvas.parentElement;
    const width = parent?.clientWidth ?? 800;
    const height = parent?.clientHeight ?? 600;

    initParticles(width, height);

    const render = (time: number) => {
      const dpr = window.devicePixelRatio || 1;
      if (canvas.width !== width * dpr || canvas.height !== height * dpr) {
        canvas.width = width * dpr;
        canvas.height = height * dpr;
        canvas.style.width = `${width}px`;
        canvas.style.height = `${height}px`;
        ctx.scale(dpr, dpr);
      }

      // Fade existing trails
      ctx.globalCompositeOperation = "destination-out";
      ctx.fillStyle = "rgba(0, 0, 0, 0.06)";
      ctx.fillRect(0, 0, width, height);
      ctx.globalCompositeOperation = "source-over";

      const particles = particlesRef.current;
      const baseColor =
        type === "wind"
          ? { r: 148, g: 163, b: 184 } // slate-400
          : { r: 56, g: 189, b: 248 }; // cyan-400

      for (const p of particles) {
        const vec = getFieldVector(p.x, p.y);
        p.vx = p.vx * 0.9 + vec.vx * 0.1;
        p.vy = p.vy * 0.9 + vec.vy * 0.1;

        const prevX = p.x;
        const prevY = p.y;

        p.x += p.vx * dt * speed * p.speed;
        p.y += p.vy * dt * speed * p.speed;
        p.life += dt * speed * 30;

        // Reset if out of bounds or expired
        if (
          p.x < -10 || p.x > width + 10 ||
          p.y < -10 || p.y > height + 10 ||
          p.life > p.maxLife
        ) {
          p.x = Math.random() * width;
          p.y = Math.random() * height;
          p.life = 0;
          p.maxLife = 60 + Math.random() * 40;
          continue;
        }

        const lifeFrac = p.life / p.maxLife;
        const alpha = Math.sin(lifeFrac * Math.PI) * 0.5;

        ctx.beginPath();
        ctx.moveTo(prevX, prevY);
        ctx.lineTo(p.x, p.y);
        ctx.strokeStyle = `rgba(${baseColor.r}, ${baseColor.g}, ${baseColor.b}, ${alpha})`;
        ctx.lineWidth = 1;
        ctx.stroke();
      }

      animFrameRef.current = requestAnimationFrame(render);
    };

    let dt = 0.016;
    let lastTime = 0;

    const wrappedRender = (time: number) => {
      dt = lastTime ? Math.min((time - lastTime) / 1000, 0.05) : 0.016;
      lastTime = time;
      animFrameRef.current = requestAnimationFrame(wrappedRender);
    };

    animFrameRef.current = requestAnimationFrame(wrappedRender);

    return () => {
      if (animFrameRef.current) cancelAnimationFrame(animFrameRef.current);
    };
  }, [map, visible, type, speed, initParticles, getFieldVector]);

  return (
    <div className="pointer-events-none absolute inset-0 z-[4]">
      <canvas ref={canvasRef} className="h-full w-full" />
    </div>
  );
}
