import { useEffect, useRef } from 'react';

interface Particle {
  x: number;
  y: number;
  vx: number;
  vy: number;
  color: string;
  size: number;
  speed: number;
}

export default function CircuitCanvas() {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    let animationFrameId: number;

    const handleResize = () => {
      canvas.width = window.innerWidth;
      canvas.height = window.innerHeight;
    };
    handleResize();
    window.addEventListener('resize', handleResize);

    const gridSize = 50;
    const colors = ['#64748b', '#94a3b8', '#cbd5e1', '#475569', '#334155'];
    const numParticles = 20;

    const createParticle = (): Particle => {
      const isHorizontal = Math.random() > 0.5;
      const gridX = Math.floor(Math.random() * Math.ceil(window.innerWidth / gridSize)) * gridSize;
      const gridY = Math.floor(Math.random() * Math.ceil(window.innerHeight / gridSize)) * gridSize;
      const speed = 1 + Math.random() * 1.5;

      return {
        x: gridX,
        y: gridY,
        vx: isHorizontal ? (Math.random() > 0.5 ? speed : -speed) : 0,
        vy: !isHorizontal ? (Math.random() > 0.5 ? speed : -speed) : 0,
        color: colors[Math.floor(Math.random() * colors.length)],
        size: 2 + Math.random() * 1.5,
        speed
      };
    };

    const particles: Particle[] = Array.from({ length: numParticles }, createParticle);

    const render = () => {
      ctx.clearRect(0, 0, canvas.width, canvas.height);

      // Draw Grid Lines (Ultra subtle minimalist dark grid)
      ctx.strokeStyle = 'rgba(255, 255, 255, 0.018)';
      ctx.lineWidth = 1;

      for (let x = 0; x <= canvas.width; x += gridSize) {
        ctx.beginPath();
        ctx.moveTo(x, 0);
        ctx.lineTo(x, canvas.height);
        ctx.stroke();
      }

      for (let y = 0; y <= canvas.height; y += gridSize) {
        ctx.beginPath();
        ctx.moveTo(0, y);
        ctx.lineTo(canvas.width, y);
        ctx.stroke();
      }

      // Draw and Update Traveling Circuit Dots (Subtle & Non-distracting)
      particles.forEach((p) => {
        p.x += p.vx;
        p.y += p.vy;

        // Turn at grid intersections randomly
        if (Math.abs(p.x % gridSize) < Math.abs(p.vx) && Math.abs(p.y % gridSize) < Math.abs(p.vy)) {
          if (Math.random() < 0.3) {
            const turnHorizontal = p.vy !== 0;
            const dir = Math.random() > 0.5 ? 1 : -1;
            p.vx = turnHorizontal ? p.speed * dir : 0;
            p.vy = !turnHorizontal ? p.speed * dir : 0;
          }
        }

        // Wrap around screen boundaries
        if (p.x < 0) p.x = canvas.width;
        if (p.x > canvas.width) p.x = 0;
        if (p.y < 0) p.y = canvas.height;
        if (p.y > canvas.height) p.y = 0;

        // Draw Subtle Pulse Dot with low opacity
        ctx.save();
        ctx.globalAlpha = 0.22;
        ctx.fillStyle = p.color;
        ctx.beginPath();
        ctx.arc(p.x, p.y, p.size, 0, Math.PI * 2);
        ctx.fill();

        // Subtle Tail effect
        ctx.strokeStyle = p.color;
        ctx.globalAlpha = 0.12;
        ctx.lineWidth = 1;
        ctx.beginPath();
        ctx.moveTo(p.x, p.y);
        ctx.lineTo(p.x - p.vx * 5, p.y - p.vy * 5);
        ctx.stroke();
        ctx.restore();
      });

      animationFrameId = requestAnimationFrame(render);
    };

    render();

    return () => {
      window.removeEventListener('resize', handleResize);
      cancelAnimationFrame(animationFrameId);
    };
  }, []);

  return (
    <canvas
      ref={canvasRef}
      style={{
        position: 'fixed',
        top: 0,
        left: 0,
        width: '100vw',
        height: '100vh',
        pointerEvents: 'none',
        zIndex: 0
      }}
    />
  );
}
