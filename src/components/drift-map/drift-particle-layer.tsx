"use client";

import * as React from "react";
import type { Map as MapLibreMap } from "maplibre-gl";
import type { DriftResult } from "@/lib/types";

interface Particle {
  progress: number;
  lat: number;
  lng: number;
  size: number;
  opacity: number;
}

/**
 * Canvas-based particle animation that renders backward-drift particles
 * along the actual sourcePoints trajectory from the backend.
 * Uses requestAnimationFrame to avoid React re-render overhead.
 */
export function DriftParticleLayer({
  map,
  drift,
  visible,
  animationProgress,
  speed,
}: {
  map: MapLibreMap | null;
  drift: DriftResult | null;
  visible: boolean;
  animationProgress: number;
  speed: number;
}) {
  const canvasRef = React.useRef<HTMLCanvasElement | null>(null);
  const particlesRef = React.useRef<Particle[]>([]);
  const animFrameRef = React.useRef<number>(0);
  const lastTimeRef = React.useRef<number>(0);

  // Build trajectory from sourcePoints
  const trajectory = React.useMemo(() => {
    if (!drift?.sourcePoints || drift.sourcePoints.length === 0) return [];
    // sourcePoints are [lat, lon] pairs from slick → source
    // We reverse them to animate source → slick (forward in time)
    return [...drift.sourcePoints].reverse().map((pt) => ({
      lat: pt[0],
      lng: pt[1],
    }));
  }, [drift]);

  // Initialize particles
  const initParticles = React.useCallback(() => {
    const count = Math.min(300, Math.max(80, trajectory.length * 15));
    const particles: Particle[] = [];
    for (let i = 0; i < count; i++) {
      particles.push({
        progress: Math.random(),
        lat: 0,
        lng: 0,
        size: 1 + Math.random() * 2.5,
        opacity: 0.3 + Math.random() * 0.7,
      });
    }
    particlesRef.current = particles;
  }, [trajectory.length]);

  // Interpolate position along trajectory
  const interpolate = React.useCallback(
    (progress: number): { lat: number; lng: number } | null => {
      if (trajectory.length < 2) return null;
      const p = Math.max(0, Math.min(1, progress));
      const segmentCount = trajectory.length - 1;
      const segment = Math.min(Math.floor(p * segmentCount), segmentCount - 1);
      const t = (p * segmentCount) - segment;
      const a = trajectory[segment];
      const b = trajectory[Math.min(segment + 1, trajectory.length - 1)];
      return {
        lat: a.lat + (b.lat - a.lat) * t,
        lng: a.lng + (b.lng - a.lng) * t,
      };
    },
    [trajectory]
  );

  // Get canvas coordinates from lat/lng
  const project = React.useCallback(
    (lat: number, lng: number): { x: number; y: number } | null => {
      if (!map) return null;
      try {
        const point = map.project([lng, lat]);
        return { x: point.x, y: point.y };
      } catch {
        return null;
      }
    },
    [map]
  );

  // Render loop
  React.useEffect(() => {
    if (!map || !canvasRef.current || !visible || trajectory.length < 2) {
      if (canvasRef.current) {
        const ctx = canvasRef.current.getContext("2d");
        if (ctx) ctx.clearRect(0, 0, canvasRef.current.width, canvasRef.current.height);
      }
      return;
    }

    const canvas = canvasRef.current;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    initParticles();

    const render = (time: number) => {
      const dt = lastTimeRef.current ? (time - lastTimeRef.current) / 1000 : 0.016;
      lastTimeRef.current = time;

      // Resize canvas to match container
      const parent = canvas.parentElement;
      if (parent) {
        const dpr = window.devicePixelRatio || 1;
        const w = parent.clientWidth;
        const h = parent.clientHeight;
        if (canvas.width !== w * dpr || canvas.height !== h * dpr) {
          canvas.width = w * dpr;
          canvas.height = h * dpr;
          canvas.style.width = `${w}px`;
          canvas.style.height = `${h}px`;
          ctx.scale(dpr, dpr);
        }
      }

      ctx.clearRect(0, 0, canvas.width, canvas.height);

      const particles = particlesRef.current;

      // Update and draw particles
      for (const p of particles) {
        // Advance particle
        p.progress += dt * speed * 0.08;
        if (p.progress > 1) p.progress -= 1;

        // Scale progress by animation controller
        const effectiveProgress = p.progress * animationProgress;

        const pos = interpolate(effectiveProgress);
        if (!pos) continue;

        const screen = project(pos.lat, pos.lng);
        if (!screen) continue;

        // Fade in/out at ends
        let fade = 1;
        if (effectiveProgress < 0.05) fade = effectiveProgress / 0.05;
        else if (effectiveProgress > 0.95) fade = (1 - effectiveProgress) / 0.05;

        const alpha = p.opacity * fade * 0.8;

        // Draw particle with glow
        ctx.beginPath();
        ctx.arc(screen.x, screen.y, p.size + 1, 0, Math.PI * 2);
        ctx.fillStyle = `rgba(56, 189, 248, ${alpha * 0.3})`;
        ctx.fill();

        ctx.beginPath();
        ctx.arc(screen.x, screen.y, p.size, 0, Math.PI * 2);
        ctx.fillStyle = `rgba(56, 189, 248, ${alpha})`;
        ctx.fill();
      }

      animFrameRef.current = requestAnimationFrame(render);
    };

    animFrameRef.current = requestAnimationFrame(render);

    return () => {
      if (animFrameRef.current) {
        cancelAnimationFrame(animFrameRef.current);
      }
    };
  }, [map, visible, trajectory, animationProgress, speed, initParticles, interpolate, project]);

  return (
    <div className="pointer-events-none absolute inset-0 z-[5]">
      <canvas ref={canvasRef} className="h-full w-full" />
    </div>
  );
}
