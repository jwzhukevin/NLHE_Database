(function(){
  'use strict';
  const STAGE_ID = 'carouselStage';
  const DOTS_ID = 'carouselDots';
  const INTERVAL_MS = 5000; // 5秒

  function createImg(src){
    const img = document.createElement('img');
    img.alt = '';
    img.decoding = 'async';
    img.loading = 'eager';
    img.src = src;
    return img;
  }

  function activate(stage, dots, idx){
    const imgs = Array.from(stage.querySelectorAll('img'));
    imgs.forEach((im, i)=>{
      if (i === idx) im.classList.add('active');
      else im.classList.remove('active');
    });
    dots.querySelectorAll('button').forEach((b, i)=>{
      b.setAttribute('aria-selected', String(i===idx));
    });
  }

  async function init(){
    const stage = document.getElementById(STAGE_ID);
    const dots = document.getElementById(DOTS_ID);
    if (!stage || !dots) return;

    let list = [];
    try {
      const res = await fetch('/api/landing-pictures', { headers: { 'Accept': 'application/json' } });
      const data = await res.json();
      list = Array.isArray(data.images) ? data.images : [];
    } catch {}

    if (!list.length) {
      // 无图则隐藏轮播容器
      const shell = document.getElementById('heroCarousel');
      if (shell) shell.style.display = 'none';
      return;
    }

    list.forEach((src, i)=>{
      const img = createImg(src);
      if (i===0) img.classList.add('active');
      stage.appendChild(img);
      const dot = document.createElement('button');
      dot.type = 'button';
      dot.setAttribute('aria-label', 'Slide ' + (i+1));
      dot.setAttribute('aria-selected', String(i===0));
      dot.addEventListener('click', ()=>{
        current = i;
        activate(stage, dots, current);
        restart();
      });
      dots.appendChild(dot);
    });

    let current = 0;
    let timer = null;
    function next(){ current = (current + 1) % list.length; activate(stage, dots, current); }
    function start(){ timer = setInterval(next, INTERVAL_MS); }
    function stop(){ if (timer) { clearInterval(timer); timer = null; } }
    function restart(){ stop(); start(); }

    // 悬停暂停，移出继续
    const shell = document.getElementById('heroCarousel');
    if (shell){
      shell.addEventListener('mouseenter', stop);
      shell.addEventListener('mouseleave', start);
    }

    start();
  }

  document.addEventListener('DOMContentLoaded', init);
})();
