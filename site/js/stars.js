/* ============================================================
   stars.js — 星空與流星
   ------------------------------------------------------------
   純 canvas，無外部相依。取自 Friends World 的背景質感：
   多層星點（不同亮度與閃爍週期）＋ 偶爾劃過的流星。
   ============================================================ */
(function () {
  'use strict';

  var cv = document.getElementById('stars');
  if (!cv) return;
  if (window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;

  var ctx = cv.getContext('2d');
  var dpr = Math.min(window.devicePixelRatio || 1, 2);
  var W = 0, H = 0;
  var stars = [], shoots = [];

  function resize() {
    W = cv.clientWidth; H = cv.clientHeight;
    cv.width = W * dpr; cv.height = H * dpr;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    seed();
  }

  function seed() {
    // 密度隨畫面大小調整，手機不要塞太多顆
    var n = Math.round(Math.min(220, Math.max(90, (W * H) / 7000)));
    stars = [];
    for (var i = 0; i < n; i++) {
      var big = Math.random() < 0.06;
      stars.push({
        x: Math.random() * W,
        y: Math.random() * H,
        r: big ? 1.1 + Math.random() * 0.9 : 0.35 + Math.random() * 0.7,
        base: big ? 0.55 + Math.random() * 0.35 : 0.18 + Math.random() * 0.45,
        // 每顆星有自己的閃爍週期與相位，才不會整片一起亮
        sp: 0.0004 + Math.random() * 0.0013,
        ph: Math.random() * Math.PI * 2,
        big: big
      });
    }
  }

  function spawnShoot() {
    // 從上方隨機位置往右下劃
    shoots.push({
      x: Math.random() * W * 0.7,
      y: -30 - Math.random() * 60,
      len: 90 + Math.random() * 120,
      sp: 5 + Math.random() * 4,
      ang: Math.PI / 4.6 + (Math.random() - 0.5) * 0.25,
      life: 0,
      max: 90 + Math.random() * 50
    });
  }

  function draw(t) {
    ctx.clearRect(0, 0, W, H);

    for (var i = 0; i < stars.length; i++) {
      var s = stars[i];
      var a = s.base * (0.55 + 0.45 * Math.sin(t * s.sp + s.ph));
      ctx.beginPath();
      ctx.arc(s.x, s.y, s.r, 0, Math.PI * 2);
      ctx.fillStyle = 'rgba(226, 234, 255, ' + a.toFixed(3) + ')';
      ctx.fill();

      // 大顆的加一圈很淡的暈
      if (s.big) {
        ctx.beginPath();
        ctx.arc(s.x, s.y, s.r * 3.4, 0, Math.PI * 2);
        ctx.fillStyle = 'rgba(150, 185, 255, ' + (a * 0.12).toFixed(3) + ')';
        ctx.fill();
      }
    }

    for (var j = shoots.length - 1; j >= 0; j--) {
      var sh = shoots[j];
      sh.life++;
      sh.x += Math.cos(sh.ang) * sh.sp;
      sh.y += Math.sin(sh.ang) * sh.sp;

      var fade = 1 - sh.life / sh.max;
      if (fade <= 0 || sh.x > W + 120 || sh.y > H + 120) { shoots.splice(j, 1); continue; }

      var tx = sh.x - Math.cos(sh.ang) * sh.len;
      var ty = sh.y - Math.sin(sh.ang) * sh.len;
      var g = ctx.createLinearGradient(sh.x, sh.y, tx, ty);
      g.addColorStop(0, 'rgba(232, 240, 255, ' + (0.85 * fade).toFixed(3) + ')');
      g.addColorStop(0.35, 'rgba(150, 190, 255, ' + (0.35 * fade).toFixed(3) + ')');
      g.addColorStop(1, 'rgba(150, 190, 255, 0)');
      ctx.strokeStyle = g;
      ctx.lineWidth = 1.6;
      ctx.lineCap = 'round';
      ctx.beginPath();
      ctx.moveTo(sh.x, sh.y);
      ctx.lineTo(tx, ty);
      ctx.stroke();

      // 頭部的光點
      ctx.beginPath();
      ctx.arc(sh.x, sh.y, 1.8, 0, Math.PI * 2);
      ctx.fillStyle = 'rgba(240, 246, 255, ' + (0.9 * fade).toFixed(3) + ')';
      ctx.fill();
    }

    requestAnimationFrame(draw);
  }

  var rt = 0;
  window.addEventListener('resize', function () {
    clearTimeout(rt);
    rt = setTimeout(resize, 180);
  });

  resize();
  requestAnimationFrame(draw);

  // 流星不要太頻繁，偶爾出現才有驚喜感
  (function loop() {
    setTimeout(function () {
      if (!document.hidden && shoots.length < 2) spawnShoot();
      loop();
    }, 4200 + Math.random() * 7000);
  })();
})();
