/* loader.js — 全站加载遮罩控制（含引用计数）
 * 功能：
 * - 提供 window.showLoader()/window.hideLoader()，内部使用引用计数避免多模块并发时早关
 * - DOMContentLoaded 时自动隐藏（若无其他 showLoader 占用）
 * - 可选：对晶体结构查看器进行通用监听（.crystal-viewer 下出现首个 canvas 后隐藏）
 */
(function(){
  // 基本参数（可调整）
  const LOADER_ID = 'global-loader';
  const BODY_LOADED_CLASS = 'loaded';
  const DELAY_SHOW_MS = 1;   // 延迟显示（超过此时间才真正显示）
  const MIN_SHOW_MS = 10000;     // 最小展示时长（一旦显示，至少展示该时长）
  const DEBUG_LOADER = true;   // 调试开关：true 时输出日志

  // 状态
  let counter = 0;              // 引用计数
  let showTimer = null;         // 延迟显示定时器
  let visible = false;          // 是否已经显示
  let shownAt = 0;              // 实际显示的时间戳
  let crystalObserver = null;   // 晶体观察者

  // 调试工具与状态查看
  function _debug(){ if (DEBUG_LOADER) { try { console.debug('[loader]', ...arguments); } catch(_) {} } }
  window.__getLoaderState = function(){
    return {
      counter,
      visible,
      scheduled: !!showTimer,
      shownAt,
      now: Date.now()
    };
  };

  function getLoaderEl(){ return document.getElementById(LOADER_ID); }
  function reallyShow(){
    if (visible) return;
    const el = getLoaderEl();
    if (el) {
      el.style.display = 'flex';
    }
    document.body.classList.remove(BODY_LOADED_CLASS);
    visible = true;
    shownAt = Date.now();
    _debug('reallyShow: visible=true, counter=', counter);
    try { startBandAnimation(); } catch(_) {}
  }
  function reallyHide(){
    const el = getLoaderEl();
    if (el) {
      el.style.display = 'none';
    }
    document.body.classList.add(BODY_LOADED_CLASS);
    visible = false;
    shownAt = 0;
    _debug('reallyHide: visible=false');
    try { stopBandAnimation(); } catch(_) {}
  }

  function scheduleShow(){
    if (visible || showTimer) return;
    showTimer = setTimeout(() => {
      showTimer = null;
      if (counter > 0) {
        _debug('scheduleShow -> reallyShow (counter>0)');
        reallyShow();
      }
    }, DELAY_SHOW_MS);
    _debug('scheduleShow: timer set', DELAY_SHOW_MS, 'ms, counter=', counter);
  }
  function cancelScheduledShow(){
    if (showTimer) {
      clearTimeout(showTimer);
      showTimer = null;
      _debug('cancelScheduledShow: canceled pending show');
    }
  }

  // 全局 API（引用计数 + 延迟显示 + 最小展示）
  // 在 showLoader 时，引用计数+1，并启动延迟显示定时器
  window.showLoader = function(){
    counter = Math.max(0, counter) + 1;
    _debug('showLoader: counter++ =>', counter);
    scheduleShow(); // 启动延迟显示定时器
  };
  // 在 hideLoader 时，引用计数-1，并检查是否可以立即隐藏
  window.hideLoader = function(){
    counter = Math.max(0, counter - 1);
    _debug('hideLoader: counter-- =>', counter);
    if (counter > 0) return; // 仍有占用者

    // 无占用
    if (!visible) {
      // 如果还未真正显示，取消计划显示即可
      cancelScheduledShow();
      _debug('hideLoader: not visible, canceled scheduled show');
      return;
    }
    const elapsed = Date.now() - (shownAt || Date.now());
    const remain = Math.max(0, MIN_SHOW_MS - elapsed);
    if (remain > 0) {
      _debug('hideLoader: wait remain(ms)=', remain);
      setTimeout(() => { if (counter === 0) reallyHide(); }, remain);
    } else {
      reallyHide();
    }
  };

  // DOM 就绪：不再处理晶体查看器专属联动，统一走全站触发
  document.addEventListener('DOMContentLoaded', function(){
    // 预留位置（如需 DOM 准备完成后的钩子）
  });

  // 资源全部加载完成的兜底：如无占用，直接隐藏（并清理未触发的显示）
  window.addEventListener('load', function(){
    if (counter === 0) {
      cancelScheduledShow();
      if (visible) window.hideLoader();
    }
    // 全站触发：窗口完成加载时，若无其他占用则隐藏一次
    try { window.hideLoader && window.hideLoader(); } catch(_) {}
  });

  // 最长 10 秒兜底隐藏，防止异常状态
  setTimeout(() => {
    if (counter === 0) {
      cancelScheduledShow();
      if (visible) window.hideLoader();
    }
  }, 10000);

  // ==================== 全站自动触发：脚本加载即请求显示 ====================
  try { window.showLoader && window.showLoader(); } catch(_) {}

  /* ==================== 能带曲线动画模块 ==================== */
  const BAND_WIDTH = 960;         // 画布 CSS 尺寸（与 base.html 中一致）
  const BAND_HEIGHT = 600;
  const PADDING = 28;             // 旧的统一内边距（兼容保留，不再使用）
  const GRID_COUNT = 10;          // 10×10 淡网格
  const DRAW_DURATION_MS = 500;   // 每条曲线绘制时长（毫秒）
  const PAUSE_MS = 0;            // 每条绘制完后停顿（毫秒）
  const COLOR_AXIS = '#94a3b8';   // 坐标轴颜色（中灰）
  const COLOR_GRID = 'rgba(0,0,0,0.06)'; // 网格线颜色（淡）
  const COLOR_BAND = '#0047AB';   // 能带颜色（主题蓝）
  // 新的不对称内边距，保证标题与刻度标签不被裁切
  const PAD_LEFT = 56;
  const PAD_RIGHT = 36;
  const PAD_TOP = 72; // 为顶部图题预留空间
  const PAD_BOTTOM = 72;
  // 标题动画参数
  const TITLE_VARIANTS = [
    'Electrons are transitioning'
  ];
  const TITLE_ROTATE_MS = 3000; // 每 3 秒切换一次短语
  const TITLE_TEXT = 'Electrons are transitioning'; // 兼容旧变量（未使用）
  const TITLE_FONT = '600 18px Inter, system-ui, -apple-system, Segoe UI, Arial, sans-serif';
  const TITLE_COLOR = '#0f172a';
  const TITLE_STEP_MS = 400; // 省略号节拍（不再使用省略号，但保留兼容）
  const TITLE_PULSE_PERIOD_MS = 1200; // 透明度脉冲周期
  const TITLE_MIN_ALPHA = 0.55;
  const TITLE_MAX_ALPHA = 1.0;
  let titleLastTs = 0; // 用作时间基准
  // 高亮扫动参数（统一用于标题、轴标题、k 标签）
  const SWEEP_PERIOD_MS = 1600;   // 完成一次从左到右的时间
  const SWEEP_WIDTH_RATIO = 0.18; // 相对绘图区宽度的高亮带宽度

  let rafId = null;
  let canvas = null, ctx = null;
  let dpr = 1;
  let inner = { x0: PAD_LEFT, y0: PAD_TOP, x1: BAND_WIDTH - PAD_RIGHT, y1: BAND_HEIGHT - PAD_BOTTOM };
  let currentBand = 0;            // 0..9
  let bandStartTs = 0;            // 本条开始时间
  let pausedUntil = 0;            // 暂停到此时间戳
  let bands = null;               // 预生成的 10 条曲线像素点
  let backdropDrawn = false;      // 网格与坐标轴是否已绘制
  let bandsCompleted = 0;         // 已完成绘制的曲线条数（0..10）

  function initBandCanvas(){
    canvas = document.getElementById('band-loader-canvas');
    if (!canvas) return false;
    dpr = Math.max(1, window.devicePixelRatio || 1);
    canvas.width = Math.floor(BAND_WIDTH * dpr);
    canvas.height = Math.floor(BAND_HEIGHT * dpr);
    ctx = canvas.getContext('2d');
    if (!ctx) return false;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0); 
    inner = { x0: PAD_LEFT, y0: PAD_TOP, x1: BAND_WIDTH - PAD_RIGHT, y1: BAND_HEIGHT - PAD_BOTTOM };
    return true;
  }

  // Catmull-Rom 样条（centripetal）插值，返回更致密、更平滑的点列
  function catmullRomSpline(points, segmentsPerSpan){
    const res = [];
    if (!points || points.length < 2) return points || res;
    // 复制端点以便边界插值
    const pts = [points[0], ...points, points[points.length - 1]];
    // 逐段插值：P0,P1,P2,P3，输出 P1->P2 之间的曲线
    for (let i = 0; i < pts.length - 3; i++) {
      const P0 = pts[i], P1 = pts[i+1], P2 = pts[i+2], P3 = pts[i+3];
      for (let j = 0; j < segmentsPerSpan; j++) {
        const t = j / segmentsPerSpan;
        const t2 = t * t; const t3 = t2 * t;
        // Catmull-Rom 基函数（张力 tau=0.5 的等价形式）
        const a0 = -0.5*t3 + t2 - 0.5*t;
        const a1 =  1.5*t3 - 2.5*t2 + 1.0;
        const a2 = -1.5*t3 + 2.0*t2 + 0.5*t;
        const a3 =  0.5*t3 - 0.5*t2;
        const x = a0*P0.x + a1*P1.x + a2*P2.x + a3*P3.x;
        const y = a0*P0.y + a1*P1.y + a2*P2.y + a3*P3.y;
        res.push({ x, y });
      }
    }
    // 确保最后一个点加入
    res.push(points[points.length - 1]);
    return res;
  }

  function smoothBand(points){
    // 使用样条提高平滑度：每段插值 6 段（可按性能调节）
    return catmullRomSpline(points, 6);
  }

  function generateBands(){
    // 生成 10 条“类能带”曲线（像素坐标），引入可控随机 + 样条平滑
    const arr = [];
    const N = 480; // 点数（更密集）
    const xMin = -Math.PI, xMax = Math.PI;
    const w = inner.x1 - inner.x0;
    const h = inner.y1 - inner.y0;
    const centerY = inner.y0 + h / 2; // 中线

    // 简单随机函数（避免依赖额外库）：[0,1)
    const rnd = () => Math.random();

    for (let i = 0; i < 10; i++) {
      const pts = [];
      // 基础分层 + 随机微扰，防止严重重叠
      const layerGap = (h / 12) * 1.05;
      const offsetBase = (i - 4.5) * layerGap;
      const offsetJitter = (rnd() - 0.5) * layerGap * 0.35; // 随机±0.35层间距
      const offsetPx = offsetBase + offsetJitter;

      // 随机振幅与频率/相位，保持平滑
      const amp1 = h * (0.10 + rnd() * 0.08); // ~[0.10,0.18]
      const amp2 = h * (0.035 + rnd() * 0.04); // ~[0.035,0.075]
      const w1 = 1.0 + i * 0.03 + rnd() * 0.06; // 稍带随条数与随机的频率
      const w2 = 2.0 + rnd() * 0.3;
      const ph1 = rnd() * Math.PI * 2;
      const ph2 = rnd() * Math.PI * 2;

      for (let k = 0; k < N; k++) {
        const t = k / (N - 1);
        const xVal = xMin + (xMax - xMin) * t;
        const yOsc = amp1 * Math.sin(xVal * w1 + ph1) + amp2 * Math.sin(xVal * w2 + ph2);
        const xPx = inner.x0 + w * t;
        // 降低随机噪声幅度以提升平滑感
        const noise = (rnd() - 0.5) * h * 0.0012;
        const yPx = centerY - (offsetPx + yOsc + noise);
        pts.push({ x: xPx, y: yPx });
      }
      // 样条平滑重采样
      arr.push(smoothBand(pts));
    }
    return arr;
  }

  function drawBackdropOnce(){
    if (!ctx) return;
    // 清屏并绘制网格+坐标轴（仅在首次或重置时绘制）
    ctx.clearRect(0, 0, BAND_WIDTH, BAND_HEIGHT);
    const w = inner.x1 - inner.x0;
    const h = inner.y1 - inner.y0;

    // 顶部标题由动画函数在每帧绘制，这里不静态绘制
    // 网格（细虚线）
    ctx.save();
    ctx.strokeStyle = COLOR_GRID;
    ctx.lineWidth = 0.8;
    ctx.setLineDash([3, 5]);
    for (let i = 1; i < GRID_COUNT; i++) {
      const x = inner.x0 + (w * i) / GRID_COUNT;
      ctx.beginPath(); ctx.moveTo(x, inner.y0); ctx.lineTo(x, inner.y1); ctx.stroke();
      const y = inner.y0 + (h * i) / GRID_COUNT;
      ctx.beginPath(); ctx.moveTo(inner.x0, y); ctx.lineTo(inner.x1, y); ctx.stroke();
    }
    ctx.setLineDash([]);
    ctx.restore();
    // 四边框（细实线矩形）
    ctx.save();
    ctx.strokeStyle = '#8a96a3';
    ctx.lineWidth = 1;
    ctx.setLineDash([]);
    ctx.strokeRect(inner.x0, inner.y0, w, h);
    ctx.restore();
    // 坐标轴（细虚线，学术风格简洁）
    ctx.save();
    ctx.strokeStyle = COLOR_AXIS;
    ctx.lineWidth = 1;
    ctx.setLineDash([4, 6]);
    ctx.beginPath(); ctx.moveTo(inner.x0, inner.y0); ctx.lineTo(inner.x0, inner.y1); ctx.stroke();
    ctx.beginPath(); ctx.moveTo(inner.x0, inner.y1); ctx.lineTo(inner.x1, inner.y1); ctx.stroke();
    ctx.setLineDash([]);
    ctx.restore();

    // 费米能级线（水平中线，虚线）
    ctx.save();
    ctx.setLineDash([4, 6]);
    ctx.strokeStyle = '#9ca3af'; // 灰
    ctx.lineWidth = 1;
    const yF = inner.y0 + h / 2;
    ctx.beginPath(); ctx.moveTo(inner.x0, yF); ctx.lineTo(inner.x1, yF); ctx.stroke();
    ctx.setLineDash([]);
    ctx.restore();

    // 高对称点：Γ, X, M, K, Γ（x 轴上均匀 5 点），附带竖向虚线基准线（不绘制标签，标签改为每帧重绘）
    const kLabels = ['Γ','X','M','K','Γ'];
    ctx.save();
    ctx.strokeStyle = '#cbd5e1';
    ctx.lineWidth = 1;
    for (let i = 0; i < kLabels.length; i++) {
      const t = i / (kLabels.length - 1);
      const x = inner.x0 + w * t;
      // 竖向虚线基准线
      if (i !== 0 && i !== kLabels.length - 1) { // 避免覆盖左右实线边框
        ctx.save();
        ctx.setLineDash([3, 5]);
        ctx.strokeStyle = '#cbd5e1';
        ctx.beginPath(); ctx.moveTo(x, inner.y0); ctx.lineTo(x, inner.y1); ctx.stroke();
        ctx.restore();
      }
      // x 轴小刻度（朝内：向上）
      ctx.save();
      ctx.strokeStyle = '#334155';
      ctx.beginPath(); ctx.moveTo(x, inner.y1); ctx.lineTo(x, inner.y1 - 8); ctx.stroke();
      ctx.restore();
    }
    ctx.restore();

    // y 轴刻度（朝内：向右），均匀 4 段
    ctx.save();
    ctx.strokeStyle = '#334155';
    ctx.lineWidth = 1;
    for (let i = 1; i <= 4; i++) {
      const ty = inner.y0 + (h * i) / 5;
      ctx.beginPath(); ctx.moveTo(inner.x0, ty); ctx.lineTo(inner.x0 + 8, ty); ctx.stroke();
    }
    ctx.restore();

    // 轴标题改为每帧重绘（透明度脉冲），此处不静态绘制

    // 最后再以实线重绘四边框，覆盖任何可能叠加的虚线，确保左右边框为实线
    ctx.save();
    ctx.strokeStyle = '#8a96a3';
    ctx.lineWidth = 1;
    ctx.setLineDash([]);
    ctx.strokeRect(inner.x0, inner.y0, w, h);
    ctx.restore();

    backdropDrawn = true;
  }

  function drawTitle(ts){
    if (!ctx) return;
    const w = inner.x1 - inner.x0;
    // 基准时间
    if (!titleLastTs) titleLastTs = ts;
    const elapsedAll = ts - titleLastTs;
    // 标题固定文案（轮播已被限定为单一）
    const rotateIndex = Math.floor((elapsedAll % (TITLE_ROTATE_MS * TITLE_VARIANTS.length)) / TITLE_ROTATE_MS);
    const titleStr = TITLE_VARIANTS[rotateIndex] || TITLE_VARIANTS[0];
    // 清理标题区域（不影响绘图区）
    const clearH = 28; // 标题清理高度
    ctx.save();
    ctx.clearRect(inner.x0, inner.y0 - 32, w, clearH);
    // 重绘标题：先绘制基底（低透明度），再在扫动带内叠加高亮
    ctx.fillStyle = TITLE_COLOR;
    ctx.font = TITLE_FONT;
    ctx.textAlign = 'center';
    ctx.textBaseline = 'bottom';
    const titleX = inner.x0 + (w / 2);
    const titleY = inner.y0 - 16;
    // 基底
    ctx.globalAlpha = TITLE_MIN_ALPHA;
    ctx.fillText(titleStr, titleX, titleY);
    // 高亮扫动带
    const bandW = Math.max(60, w * SWEEP_WIDTH_RATIO);
    const sweepPhase = (elapsedAll % SWEEP_PERIOD_MS) / SWEEP_PERIOD_MS; // 0..1
    const bandX = inner.x0 + (w + bandW) * sweepPhase - bandW; // 从左外到右外
    ctx.save();
    ctx.beginPath();
    ctx.rect(bandX, inner.y0 - 32, bandW, clearH);
    ctx.clip();
    ctx.globalAlpha = TITLE_MAX_ALPHA;
    ctx.fillText(titleStr, titleX, titleY);
    ctx.restore();
    ctx.restore();
  }

function drawTexts(ts){
if (!ctx) return;
const w = inner.x1 - inner.x0;
const h = inner.y1 - inner.y0;
// 时间基准与扫动带计算
if (!titleLastTs) titleLastTs = ts;
const elapsedAll = ts - titleLastTs;
const bandW = Math.max(48, w * SWEEP_WIDTH_RATIO);
const sweepPhase = (elapsedAll % SWEEP_PERIOD_MS) / SWEEP_PERIOD_MS; // 0..1
const bandX = inner.x0 + (w + bandW) * sweepPhase - bandW;

  // 底部文字区域清理（不清除坐标轴线）：从 inner.y1+1 开始
  ctx.save();
  ctx.clearRect(inner.x0, inner.y1 + 1, w, 40);
  // 左侧 y 轴标题区域清理（避免上一帧叠加，且不进入绘图区）
  // 仅清理绘图区左侧外边距（0..PAD_LEFT-2），避免擦除曲线与网格
  ctx.clearRect(0, inner.y0, Math.max(0, PAD_LEFT - 2), h);

// 高对称点标签
const kLabels = ['Γ','X','M','K','Γ'];
ctx.fillStyle = '#0f172a';
ctx.font = '600 12px Inter, system-ui, -apple-system, Segoe UI, Arial, sans-serif';
ctx.textAlign = 'center';
ctx.textBaseline = 'alphabetic';
ctx.globalAlpha = TITLE_MIN_ALPHA; // 基底
for (let i = 0; i < kLabels.length; i++) {
const t = i / (kLabels.length - 1);
const x = inner.x0 + w * t;
ctx.fillText(kLabels[i], x, inner.y1 + 22);
}
// 高亮扫动叠加
ctx.save();
ctx.beginPath();
ctx.rect(bandX, inner.y1 + 2, bandW, 36);
ctx.clip();
ctx.globalAlpha = TITLE_MAX_ALPHA;
for (let i = 0; i < kLabels.length; i++) {
const t = i / (kLabels.length - 1);
const x = inner.x0 + w * t;
ctx.fillText(kLabels[i], x, inner.y1 + 22);
}
ctx.restore();

// 坐标轴标题
ctx.font = '600 14px Inter, system-ui, -apple-system, Segoe UI, Arial, sans-serif';
// x 轴标题居中
const xCenter = inner.x0 + (w / 2);
// x 轴标题基底
ctx.globalAlpha = TITLE_MIN_ALPHA;
ctx.fillText('Focus', xCenter, inner.y1 + 36);
// x 轴标题高亮
ctx.save();
ctx.beginPath();
ctx.rect(bandX, inner.y1 + 2, bandW, 40);
ctx.clip();
ctx.globalAlpha = TITLE_MAX_ALPHA;
ctx.fillText('Focus', xCenter, inner.y1 + 36);
ctx.restore();

// y 轴标题（竖排居中）
ctx.save();
ctx.translate(PAD_LEFT - 44, inner.y0 + (h / 2));
ctx.rotate(-Math.PI / 2);
ctx.textAlign = 'center';
ctx.textBaseline = 'middle';
// 基底
ctx.globalAlpha = TITLE_MIN_ALPHA;
ctx.fillText('Patience', 0, 0);
// 高亮扫动（使用全局带，旋转坐标系同样会被裁剪影响）
ctx.beginPath();
ctx.rect(bandX - (PAD_LEFT - 44), -h / 2, bandW, h); // 转换到当前变换后的坐标系近似裁剪
ctx.clip();
ctx.globalAlpha = TITLE_MAX_ALPHA;
ctx.fillText('Patience', 0, 0);
ctx.restore();

ctx.restore();
}

function drawCurrentBand(progress){
  if (!ctx || !bands) return;
  const pts = bands[currentBand];
  if (!pts || pts.length === 0) return;
  const count = Math.max(2, Math.floor(pts.length * Math.min(1, Math.max(0, progress))));
  ctx.save();
  ctx.strokeStyle = COLOR_BAND;
  ctx.lineWidth = 1.0; // 更细更学术
  ctx.lineJoin = 'round';
  ctx.lineCap = 'round';
  ctx.miterLimit = 2.5;
  // 裁剪，确保曲线不越出边界
  ctx.beginPath();
  ctx.rect(inner.x0, inner.y0, inner.x1 - inner.x0, inner.y1 - inner.y0);
  ctx.clip();
  // 曲线
  ctx.beginPath();
  ctx.moveTo(pts[0].x, pts[0].y);
  for (let i = 1; i < count; i++) {
    ctx.lineTo(pts[i].x, pts[i].y);
  }
  ctx.stroke();
  ctx.restore();
}

function drawFrame(ts){
  if (!canvas || !ctx) return;
  if (!backdropDrawn) drawBackdropOnce();
  if (!bandStartTs) bandStartTs = ts;

  // 动态标题/标签，防止异常导致后续不绘制
  try { drawTitle(ts); } catch(e) {}
  try { drawTexts(ts); } catch(e) {}

  // 暂停阶段：已完成当前条，等待切换下一条
  if (pausedUntil && ts < pausedUntil) {
    // 当前条已满幅保留，不清屏
    rafId = requestAnimationFrame(drawFrame);
    return;
  } else if (pausedUntil && ts >= pausedUntil) {
    // 结束暂停，统计完成数并切换下一条
    pausedUntil = 0;
    bandsCompleted += 1;
    currentBand = (currentBand + 1) % 10;
    // 若 10 条均已完成：清屏重来，并重新随机生成新一轮带
    if (bandsCompleted >= 10) {
      drawBackdropOnce(); // 内部含 clearRect
      bands = generateBands(); // 下一轮随机
      bandsCompleted = 0;
      currentBand = 0;
    }
    bandStartTs = ts;
  }

  const elapsed = ts - bandStartTs;
  const progress = Math.min(1, elapsed / DRAW_DURATION_MS);
  // 增量绘制：直接按进度画到当前位置（不清屏，之前的保留）
  drawCurrentBand(progress);

  if (progress >= 1) {
    // 当前曲线绘制完成，进入短暂停顿，再切下一条
    pausedUntil = ts + PAUSE_MS;
  }
  rafId = requestAnimationFrame(drawFrame);
}

  function startBandAnimation(){
    if (!initBandCanvas()) return;
    bands = generateBands();
    currentBand = 0;
    bandStartTs = 0;
    pausedUntil = 0;
    bandsCompleted = 0;
    backdropDrawn = false; // 首帧再绘制底图
    if (rafId) cancelAnimationFrame(rafId);
    rafId = requestAnimationFrame(drawFrame);
  }
  function stopBandAnimation(){
    try { if (rafId) cancelAnimationFrame(rafId); } catch(_) {}
    rafId = null;
    canvas = null; ctx = null; bands = null;
    bandStartTs = 0; pausedUntil = 0; currentBand = 0;
  }

})();
