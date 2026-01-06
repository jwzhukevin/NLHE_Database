// 职责：
// 1. 统一管理全站加载器的显示与隐藏（引用计数 + 延迟展示 + 最小展示时长）。
// 2. 渲染能带曲线风格的 Canvas 动画，为等待过程增添科技感。
// 3. 提供详尽中文注释，便于团队成员理解与维护。

(function () {
    'use strict';

    // =========================================================================
    // 模块一：加载器状态管理器 (Loader State Manager)
    // =========================================================================

    const LOADER_ID = 'global-loader';
    const BODY_LOADED_CLASS = 'loaded';
    const DELAY_SHOW_MS = 200;   // 延迟展示，避免闪烁
    const MIN_SHOW_MS = 1000;   // 最小展示时长，保证动画完整
    const DEBUG = true;          // 调试开关

    let counter = 0;             // 当前仍在请求加载器的调用数
    let showTimer = null;        // 延迟展示定时器
    let visible = false;         // 加载器是否已显示
    let shownAt = 0;             // 加载器开始显示的时间戳

    /** 调试日志工具，可随时关闭 */
    function log(...args) {
        if (!DEBUG) return;
        try {
            console.debug('[loader]', ...args);
        } catch (_) {
            // 某些运行环境可能没有 console，这里安全忽略
        }
    }

    /** 获取加载器 DOM 元素 */
    function getLoaderEl() {
        return document.getElementById(LOADER_ID);
    }

    /** 真正执行“显示”操作，并启动动画 */
    function doShow() {
        if (visible) return;

        const el = getLoaderEl();
        if (el) {
            el.style.display = 'flex';
        }
        document.body.classList.remove(BODY_LOADED_CLASS);

        visible = true;
        shownAt = Date.now();
        log('加载器已显示，counter =', counter);

        startBandAnimation();
    }

    /** 真正执行“隐藏”操作，并停止动画 */
    function doHide() {
        const el = getLoaderEl();
        if (el) {
            el.style.display = 'none';
        }
        document.body.classList.add(BODY_LOADED_CLASS);

        visible = false;
        shownAt = 0;
        log('加载器已隐藏');

        stopBandAnimation();
    }

    /** 安排一次延迟显示，避免闪烁 */
    function scheduleShow() {
        if (visible || showTimer) return;

        showTimer = setTimeout(() => {
            showTimer = null;
            if (counter > 0) {
                log('延迟到期，执行显示');
                doShow();
            }
        }, DELAY_SHOW_MS);

        log(`已安排 ${DELAY_SHOW_MS}ms 后显示`);
    }

    /** 取消已经安排但尚未执行的显示计划 */
    function cancelScheduledShow() {
        if (!showTimer) return;
        clearTimeout(showTimer);
        showTimer = null;
        log('取消待显示的动画');
    }

    /** 全局 API：请求显示加载器 */
    window.showLoader = function () {
        counter = Math.max(0, counter) + 1;
        log('showLoader -> counter =', counter);
        scheduleShow();
    };

    /** 全局 API：请求隐藏加载器 */
    window.hideLoader = function () {
        counter = Math.max(0, counter - 1);
        log('hideLoader -> counter =', counter);

        if (counter > 0) {
            log('仍有其他请求占用，保持显示');
            return;
        }

        if (!visible) {
            cancelScheduledShow();
            return;
        }

        const elapsed = Date.now() - (shownAt || Date.now());
        const remain = Math.max(0, MIN_SHOW_MS - elapsed);

        if (remain > 0) {
            log(`未达最小展示时长，等待 ${remain}ms`);
            setTimeout(() => {
                if (counter === 0) doHide();
            }, remain);
        } else {
            doHide();
        }
    };

    // 页面初始化时主动请求显示，防止白屏
    window.showLoader();

    // 所有资源加载完成后尝试隐藏一次
    window.addEventListener('load', () => {
        log('window.load 触发，尝试隐藏加载器');
        window.hideLoader();
    });

    // 兜底：10 秒内仍未显示则清理状态，避免卡住
    setTimeout(() => {
        if (counter > 0 && !visible) {
            log('超时兜底：清理延迟状态');
            cancelScheduledShow();
            counter = 0;
        }
    }, 10000);

    // =========================================================================
    // 模块二：能带曲线 Canvas 动画 (Band Curve Canvas Animation)
    // =========================================================================

    const CANVAS_ID = 'band-loader-canvas';
    const BAND_WIDTH = 960;
    const BAND_HEIGHT = 600;
    const GRID_COUNT = 10;
    const PAD_LEFT = 56;
    const PAD_RIGHT = 36;
    const PAD_TOP = 72;
    const PAD_BOTTOM = 72;

    const DRAW_DURATION_MS = 500;
    const PAUSE_MS = 0;
    const SWEEP_PERIOD_MS = 1600;
    const SWEEP_WIDTH_RATIO = 0.18;

    const COLOR_GRID = 'rgba(0,0,0,0.06)';
    const COLOR_AXIS = '#94a3b8';
    const COLOR_BAND = '#0047AB';
    const TITLE_COLOR = '#0f172a';
    const TITLE_TEXT = 'Electrons are transitioning';
    const TITLE_FONT = '700 20px "Microsoft YaHei", "Noto Sans SC", Inter, system-ui, -apple-system, "Segoe UI", Arial, sans-serif';
    const K_LABEL_FONT = '700 20px "Microsoft YaHei", "Noto Sans SC", Inter, system-ui, -apple-system, "Segoe UI", Arial, sans-serif';
    const AXIS_TITLE_FONT = '700 20px "Microsoft YaHei", "Noto Sans SC", Inter, system-ui, -apple-system, "Segoe UI", Arial, sans-serif';
    const TEXT_MIN_ALPHA = 0.55;
    const TEXT_MAX_ALPHA = 1.0;

    let canvas = null;
    let ctx = null;
    let dpr = 1;
    let inner = {
        x0: PAD_LEFT,
        y0: PAD_TOP,
        x1: BAND_WIDTH - PAD_RIGHT,
        y1: BAND_HEIGHT - PAD_BOTTOM
    };
    let bands = [];
    let currentBand = 0;
    let bandStartTs = 0;
    let pausedUntil = 0;
    let backdropDrawn = false;
    let bandsCompleted = 0;
    let animationStartTs = 0;
    let rafId = null;

    /** 初始化 Canvas 并处理高清屏适配 */
    function initCanvas() {
        canvas = document.getElementById(CANVAS_ID);
        if (!canvas) return false;

        dpr = Math.max(1, window.devicePixelRatio || 1);
        canvas.width = Math.floor(BAND_WIDTH * dpr);
        canvas.height = Math.floor(BAND_HEIGHT * dpr);

        ctx = canvas.getContext('2d');
        if (!ctx) return false;

        ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
        inner = {
            x0: PAD_LEFT,
            y0: PAD_TOP,
            x1: BAND_WIDTH - PAD_RIGHT,
            y1: BAND_HEIGHT - PAD_BOTTOM
        };
        return true;
    }

    /** Catmull-Rom 样条插值，使曲线平滑而自然 */
    function catmullRom(points, segmentsPerSpan) {
        const result = [];
        if (!points || points.length < 2) return points || result;

        const pts = [points[0], ...points, points[points.length - 1]];
        for (let i = 0; i < pts.length - 3; i++) {
            const P0 = pts[i];
            const P1 = pts[i + 1];
            const P2 = pts[i + 2];
            const P3 = pts[i + 3];
            for (let j = 0; j < segmentsPerSpan; j++) {
                const t = j / segmentsPerSpan;
                const t2 = t * t;
                const t3 = t2 * t;

                const a0 = -0.5 * t3 + t2 - 0.5 * t;
                const a1 = 1.5 * t3 - 2.5 * t2 + 1.0;
                const a2 = -1.5 * t3 + 2.0 * t2 + 0.5 * t;
                const a3 = 0.5 * t3 - 0.5 * t2;

                result.push({
                    x: a0 * P0.x + a1 * P1.x + a2 * P2.x + a3 * P3.x,
                    y: a0 * P0.y + a1 * P1.y + a2 * P2.y + a3 * P3.y
                });
            }
        }
        result.push(points[points.length - 1]);
        return result;
    }

    /** 生成 10 条能带曲线的数据 */
    function generateBands() {
        const arr = [];
        const N = 480;
        const w = inner.x1 - inner.x0;
        const h = inner.y1 - inner.y0;
        const midY = inner.y0 + h / 2;
        const rand = Math.random;

        for (let i = 0; i < 10; i++) {
            const pts = [];
            const layerGap = (h / 12) * 1.05;
            const offsetBase = (i - 4.5) * layerGap;
            const offsetJitter = (rand() - 0.5) * layerGap * 0.35;
            const offset = offsetBase + offsetJitter;

            const amp1 = h * (0.10 + rand() * 0.08);
            const amp2 = h * (0.035 + rand() * 0.04);
            const freq1 = 1.0 + i * 0.03 + rand() * 0.06;
            const freq2 = 2.0 + rand() * 0.3;
            const phase1 = rand() * Math.PI * 2;
            const phase2 = rand() * Math.PI * 2;

            for (let k = 0; k < N; k++) {
                const t = k / (N - 1);
                const x = inner.x0 + w * t;
                const xVal = -Math.PI + (Math.PI * 2) * t;
                const osc = amp1 * Math.sin(xVal * freq1 + phase1) + amp2 * Math.sin(xVal * freq2 + phase2);
                const noise = (rand() - 0.5) * h * 0.0012;
                pts.push({
                    x,
                    y: midY - (offset + osc + noise)
                });
            }

            arr.push(catmullRom(pts, 6));
        }

        return arr;
    }

    /** 绘制背景（网格、坐标轴、刻度），只需要绘制一次 */
    function drawBackdropOnce() {
        if (!ctx) return;

        ctx.clearRect(0, 0, BAND_WIDTH, BAND_HEIGHT);
        const w = inner.x1 - inner.x0;
        const h = inner.y1 - inner.y0;

        ctx.save();
        ctx.strokeStyle = COLOR_GRID;
        ctx.lineWidth = 0.8;
        ctx.setLineDash([3, 5]);
        for (let i = 1; i < GRID_COUNT; i++) {
            const x = inner.x0 + (w * i) / GRID_COUNT;
            ctx.beginPath();
            ctx.moveTo(x, inner.y0);
            ctx.lineTo(x, inner.y1);
            ctx.stroke();

            const y = inner.y0 + (h * i) / GRID_COUNT;
            ctx.beginPath();
            ctx.moveTo(inner.x0, y);
            ctx.lineTo(inner.x1, y);
            ctx.stroke();
        }
        ctx.restore();

        ctx.save();
        ctx.strokeStyle = '#8a96a3';
        ctx.lineWidth = 1;
        ctx.strokeRect(inner.x0, inner.y0, w, h);

        ctx.setLineDash([4, 6]);
        ctx.strokeStyle = COLOR_AXIS;
        ctx.beginPath();
        ctx.moveTo(inner.x0, inner.y0);
        ctx.lineTo(inner.x0, inner.y1);
        ctx.stroke();
        ctx.beginPath();
        ctx.moveTo(inner.x0, inner.y1);
        ctx.lineTo(inner.x1, inner.y1);
        ctx.stroke();
        ctx.restore();

        ctx.save();
        ctx.setLineDash([4, 6]);
        ctx.strokeStyle = '#9ca3af';
        ctx.beginPath();
        ctx.moveTo(inner.x0, inner.y0 + h / 2);
        ctx.lineTo(inner.x1, inner.y0 + h / 2);
        ctx.stroke();
        ctx.restore();

        const kLabels = ['Γ', 'X', 'M', 'K', 'Γ'];
        ctx.save();
        for (let i = 0; i < kLabels.length; i++) {
            const x = inner.x0 + w * (i / (kLabels.length - 1));
            if (i > 0 && i < kLabels.length - 1) {
                ctx.save();
                ctx.setLineDash([3, 5]);
                ctx.strokeStyle = '#cbd5e1';
                ctx.beginPath();
                ctx.moveTo(x, inner.y0);
                ctx.lineTo(x, inner.y1);
                ctx.stroke();
                ctx.restore();
            }
            ctx.strokeStyle = '#334155';
            ctx.beginPath();
            ctx.moveTo(x, inner.y1);
            ctx.lineTo(x, inner.y1 - 8);
            ctx.stroke();
        }
        ctx.restore();

        ctx.save();
        ctx.strokeStyle = '#334155';
        for (let i = 1; i <= 4; i++) {
            const y = inner.y0 + (h * i) / 5;
            ctx.beginPath();
            ctx.moveTo(inner.x0, y);
            ctx.lineTo(inner.x0 + 8, y);
            ctx.stroke();
        }
        ctx.restore();

        backdropDrawn = true;
    }

    /** 绘制带扫光效果的文本 */
    function drawSweepingText(text, x, y, font, sweepArea) {
        if (!ctx) return;
        if (!animationStartTs) {
            animationStartTs = Date.now();
        }

        const w = inner.x1 - inner.x0;
        const elapsed = Date.now() - animationStartTs;
        const sweepPhase = (elapsed % SWEEP_PERIOD_MS) / SWEEP_PERIOD_MS;
        const sweepWidth = Math.max(60, w * SWEEP_WIDTH_RATIO);
        const sweepX = inner.x0 + (w + sweepWidth) * sweepPhase - sweepWidth;

        ctx.save();
        ctx.font = font;
        ctx.fillStyle = TITLE_COLOR;
        ctx.globalAlpha = TEXT_MIN_ALPHA;
        ctx.fillText(text, x, y);

        ctx.beginPath();
        ctx.rect(sweepX, sweepArea.y, sweepWidth, sweepArea.h);
        ctx.clip();
        ctx.globalAlpha = TEXT_MAX_ALPHA;
        ctx.fillText(text, x, y);
        ctx.restore();
    }

    /** 绘制标题、K 点标签与坐标轴标题 */
    function drawDynamicTexts() {
        if (!ctx) return;

        const w = inner.x1 - inner.x0;
        const h = inner.y1 - inner.y0;

        ctx.clearRect(0, 0, BAND_WIDTH, PAD_TOP - 2);
        ctx.clearRect(0, inner.y1 + 1, BAND_WIDTH, PAD_BOTTOM - 2);
        ctx.clearRect(0, inner.y0, PAD_LEFT - 2, h);

        ctx.textAlign = 'center';
        ctx.textBaseline = 'bottom';
        drawSweepingText(TITLE_TEXT, inner.x0 + w / 2, inner.y0 - 16, TITLE_FONT, {
            x: inner.x0,
            y: 0,
            w,
            h: PAD_TOP
        });

        const kLabels = ['Γ', 'X', 'M', 'K', 'Γ'];
        ctx.textBaseline = 'alphabetic';
        kLabels.forEach((label, i) => {
            const x = inner.x0 + w * (i / (kLabels.length - 1));
            drawSweepingText(label, x, inner.y1 + 22, K_LABEL_FONT, {
                x: inner.x0,
                y: inner.y1,
                w,
                h: 34
            });
        });

        drawSweepingText('Focus', inner.x0 + w / 2, inner.y1 + 42, AXIS_TITLE_FONT, {
            x: inner.x0,
            y: inner.y1 + 28,
            w,
            h: 26
        });

        ctx.save();
        ctx.translate(PAD_LEFT - 22, inner.y0 + h / 2);
        ctx.rotate(-Math.PI / 2);
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        drawSweepingText('Patience', 0, 0, AXIS_TITLE_FONT, {
            x: -h / 2,
            y: -18,
            w: h,
            h: 36
        });
        ctx.restore();
    }

    /** 根据绘制进度渲染当前能带曲线 */
    function drawCurrentBand(progress) {
        if (!ctx || bands.length === 0) return;
        const pts = bands[currentBand];
        if (!pts || pts.length === 0) return;

        const safeProgress = Math.min(1, Math.max(0, progress));
        const count = Math.max(2, Math.floor(pts.length * safeProgress));

        ctx.save();
        ctx.strokeStyle = COLOR_BAND;
        ctx.lineWidth = 1;
        ctx.lineJoin = 'round';
        ctx.lineCap = 'round';

        ctx.beginPath();
        ctx.rect(inner.x0, inner.y0, inner.x1 - inner.x0, inner.y1 - inner.y0);
        ctx.clip();

        ctx.beginPath();
        ctx.moveTo(pts[0].x, pts[0].y);
        for (let i = 1; i < count; i++) {
            ctx.lineTo(pts[i].x, pts[i].y);
        }
        ctx.stroke();
        ctx.restore();
    }

    /** 动画主循环，驱动曲线绘制与扫光效果 */
    function drawFrame(ts) {
        if (!canvas || !ctx) return;

        if (!backdropDrawn) {
            drawBackdropOnce();
        }

        if (!animationStartTs) animationStartTs = ts;
        if (!bandStartTs) bandStartTs = ts;

        try {
            drawDynamicTexts();
        } catch (err) {
            log('drawDynamicTexts error:', err);
        }

        if (pausedUntil && ts < pausedUntil) {
            rafId = requestAnimationFrame(drawFrame);
            return;
        }

        if (pausedUntil && ts >= pausedUntil) {
            pausedUntil = 0;
            bandsCompleted += 1;
            if (bands.length > 0) {
                currentBand = (currentBand + 1) % bands.length;
            }

            if (bandsCompleted >= bands.length && bands.length > 0) {
                bandsCompleted = 0;
                backdropDrawn = false;
                bands = generateBands();
            }
            bandStartTs = ts;
        }

        const progress = bands.length === 0 ? 0 : (ts - bandStartTs) / DRAW_DURATION_MS;
        drawCurrentBand(progress);

        if (progress >= 1) {
            pausedUntil = ts + PAUSE_MS;
        }

        rafId = requestAnimationFrame(drawFrame);
    }

    /** 启动动画：初始化资源并进入主循环 */
    function startBandAnimation() {
        if (!initCanvas()) {
            log('未找到 band-loader-canvas，动画未启动');
            return;
        }

        bands = generateBands();
        currentBand = 0;
        bandStartTs = 0;
        pausedUntil = 0;
        bandsCompleted = 0;
        backdropDrawn = false;
        animationStartTs = 0;

        if (rafId) cancelAnimationFrame(rafId);
        rafId = requestAnimationFrame(drawFrame);
    }

    /** 停止动画，释放所有临时资源 */
    function stopBandAnimation() {
        if (rafId) {
            try {
                cancelAnimationFrame(rafId);
            } catch (err) {
                log('cancelAnimationFrame error:', err);
            }
        }

        rafId = null;
        canvas = null;
        ctx = null;
        bands = [];
        bandStartTs = 0;
        pausedUntil = 0;
        bandsCompleted = 0;
        animationStartTs = 0;
        backdropDrawn = false;
    }
})();