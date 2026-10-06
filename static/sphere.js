(() => {
  'use strict';
  const canvas = document.getElementById('sphere');
  if (!canvas) return;
  const ctx = canvas.getContext('2d');
  const N = 3200;
  const pts = [];
  const golden = Math.PI * (3 - Math.sqrt(5));
  for (let i = 0; i < N; i++) {
    const y = 1 - (i / (N - 1)) * 2;
    const r = Math.sqrt(1 - y * y);
    const t = golden * i;
    pts.push([Math.cos(t) * r, y, Math.sin(t) * r, 0.6 + Math.random() * 1.1]);
  }
  let size = 0;
  const resize = () => {
    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    size = canvas.clientWidth;
    canvas.width = canvas.height = Math.round(size * dpr);
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  };
  resize();
  window.addEventListener('resize', resize);

  const draw = (a) => {
    ctx.clearRect(0, 0, size, size);
    const R = size * 0.42, c = size / 2;
    const ca = Math.cos(a), sa = Math.sin(a);
    for (let i = 0; i < N; i++) {
      const p = pts[i];
      const x = p[0] * ca + p[2] * sa;
      const z = -p[0] * sa + p[2] * ca;
      const depth = (z + 1) / 2;              // 0 = far side, 1 = near side
      const light = Math.max(0, (x * 0.4 - p[1] * 0.35 + 0.7)); // light from top-right
      const alpha = (0.12 + depth * 0.75) * Math.min(1, 0.35 + light);
      ctx.fillStyle = 'rgba(' + (70 + light * 90 | 0) + ',' + (200 + light * 40 | 0) + ',' + (130 + light * 40 | 0) + ',' + alpha.toFixed(3) + ')';
      const s = p[3] * (0.8 + depth * 0.9) * (size / 900);
      ctx.fillRect(c + x * R, c + p[1] * R, s * 1.6, s * 1.6);
    }
  };

  const still = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  if (still) { draw(0.6); return; }
  let angle = 0, last = performance.now();
  const loop = (now) => {
    angle += (now - last) * 0.00012;
    last = now;
    if (!document.hidden) draw(angle);
    requestAnimationFrame(loop);
  };
  requestAnimationFrame(loop);
})();
