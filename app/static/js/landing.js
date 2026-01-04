(function(){
  'use strict';
  const STAGE_ID = 'carouselStage';
  const DOTS_ID = 'carouselDots';
  const THUMBNAIL_ID = 'carouselThumbnail';
  const INTERVAL_MS = 3000; // 3秒

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

  // 数字滚动动画
  function animateValue(element, start, end, duration) {
    const range = end - start;
    const increment = range / (duration / 16); // 60fps
    let current = start;
    
    const timer = setInterval(() => {
      current += increment;
      if ((increment > 0 && current >= end) || (increment < 0 && current <= end)) {
        current = end;
        clearInterval(timer);
      }
      
      // 格式化数字显示
      if (end >= 1000) {
        element.textContent = Math.floor(current / 1000);
      } else {
        element.textContent = Math.floor(current);
      }
    }, 16);
  }

  // 初始化数字动画
  function initStatsAnimation() {
    const statValues = document.querySelectorAll('.stat-value');
    
    const observer = new IntersectionObserver((entries) => {
      entries.forEach(entry => {
        if (entry.isIntersecting) {
          const element = entry.target;
          const target = parseInt(element.getAttribute('data-target'));
          animateValue(element, 0, target, 2000);
          observer.unobserve(element);
        }
      });
    }, { threshold: 0.5 });

    statValues.forEach(stat => observer.observe(stat));
  }

  async function init(){
    const stage = document.getElementById(STAGE_ID);
    const dots = document.getElementById(DOTS_ID);
    const thumbnail = document.getElementById(THUMBNAIL_ID);
    const prevBtn = document.querySelector('.carousel-arrow-prev');
    const nextBtn = document.querySelector('.carousel-arrow-next');
    
    if (!stage || !dots) return;

    let list = [];
    try {
      const res = await fetch('/api/landing-pictures', { headers: { 'Accept': 'application/json' } });
      const data = await res.json();
      list = Array.isArray(data.images) ? data.images : [];
    } catch {}

    if (!list.length) {
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
      
      // 缩略图预览
      dot.addEventListener('mouseenter', ()=>{
        if (thumbnail) {
          thumbnail.innerHTML = '';
          const thumbImg = createImg(src);
          thumbnail.appendChild(thumbImg);
          thumbnail.classList.add('show');
        }
      });
      
      dot.addEventListener('mouseleave', ()=>{
        if (thumbnail) {
          thumbnail.classList.remove('show');
        }
      });
      
      dot.addEventListener('click', ()=>{
        current = i;
        activate(stage, dots, current);
        restart();
      });
      
      dots.appendChild(dot);
    });

    let current = 0;
    let timer = null;

    function next(){ 
      current = (current + 1) % list.length; 
      activate(stage, dots, current); 
    }
    
    function prev(){ 
      current = (current - 1 + list.length) % list.length; 
      activate(stage, dots, current); 
    }
    
    function start(){ 
      timer = setInterval(next, INTERVAL_MS); 
    }
    
    function stop(){ 
      if (timer) { 
        clearInterval(timer); 
        timer = null; 
      } 
    }
    
    function restart(){ 
      stop(); 
      start(); 
    }

    // 箭头按钮事件
    if (prevBtn) {
      prevBtn.addEventListener('click', ()=>{
        prev();
        restart();
      });
    }
    
    if (nextBtn) {
      nextBtn.addEventListener('click', ()=>{
        next();
        restart();
      });
    }

    // 悬停暂停，移出继续
    const shell = document.getElementById('heroCarousel');
    if (shell){
      shell.addEventListener('mouseenter', stop);
      shell.addEventListener('mouseleave', start);
    }

    start();
  }

  document.addEventListener('DOMContentLoaded', () => {
    init();
    initStatsAnimation();
  });
})();
