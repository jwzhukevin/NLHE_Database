'use strict';
(function(){
  const STORAGE_KEY = 'cer_exp_state';
  const VISIBLE_COLS_KEY = 'cer_exp_visible_cols';

  function toFixedOrNone(v, digits=2) {
    if (v === null || v === undefined || v === '') return 'None';
    const n = Number(v);
    if (!isFinite(n) || n === 0) return 'None';
    return n.toFixed(digits);
  }

  function normalizeCrystal(s){
    if (s === null || s === undefined) return '';
    let t = String(s);
    // 去掉末尾的 "crystal structure" 等冗余字样（不区分大小写，允许多余空格）
    t = t.replace(/\s*crystal\s*structure\s*$/i, '');
    return t.trim();
  }

  // ===== 列显隐：放在工具函数之后，确保下文可用 =====
  const OPTIONAL_COLUMNS = ['bending_strength_mpa','bending_strain_percent','zt'];

  function getVisibleCols(){
    try{
      const raw = localStorage.getItem(VISIBLE_COLS_KEY);
      if (!raw) return new Set(OPTIONAL_COLUMNS);
      const arr = JSON.parse(raw);
      if (Array.isArray(arr) && arr.length) return new Set(arr);
      return new Set(OPTIONAL_COLUMNS);
    }catch{ return new Set(OPTIONAL_COLUMNS); }
  }

  function setVisibleCols(set){
    try{ localStorage.setItem(VISIBLE_COLS_KEY, JSON.stringify(Array.from(set))); }catch{}
  }

  function applyColumnVisibility(visibleSet){
    OPTIONAL_COLUMNS.forEach(key=>{
      const selector = `[data-col-key="${key}"]`;
      document.querySelectorAll(selector).forEach(el => {
        if (visibleSet.has(key)) el.classList.remove('hidden');
        else el.classList.add('hidden');
      });
    });
    const menu = document.getElementById('colMenu');
    if (menu){
      menu.querySelectorAll('input[type="checkbox"]').forEach(cb => {
        cb.checked = visibleSet.has(cb.value);
      });
    }
  }
  // 安全导出别名，避免某些环境作用域问题
  try { window._cerExpApplyColumnVisibility = applyColumnVisibility; } catch {}

  function qs(form){
    const fd = new FormData(form);
    const params = new URLSearchParams();
    const q = (fd.get('q') || '').toString().trim();
    if (q) params.set('q', q);
    let ps = '20';
    try { ps = localStorage.getItem('cer_exp_per_page') || '20'; } catch {}
    params.set('page_size', ps);
    return params;
  }

  function saveState(form, page){
    try {
      const params = qs(form);
      if (page) params.set('page', String(page));
      const obj = {}; for (const [k,v] of params.entries()) obj[k]=v;
      localStorage.setItem(STORAGE_KEY, JSON.stringify(obj));
    } catch {}
  }

  function restoreState(form){
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      if (!raw) return { page: 1 };
      const state = JSON.parse(raw);
      const q = state.q || '';
      const input = document.getElementById('cerExpSearchInput');
      if (input) input.value = q;
      const page = parseInt(state.page || '1', 10);
      return { page: isNaN(page) ? 1 : page };
    } catch { return { page: 1 }; }
  }

  function buildRow(item){
    const tr = document.createElement('tr');
    const cells = [
      { key: 'material', value: item.material },
      { key: 'crystal_structure', value: normalizeCrystal(item.crystal_structure) },
      { key: 'bending_strength_mpa', value: toFixedOrNone(item.bending_strength_mpa, 2) },
      { key: 'bending_strain_percent', value: toFixedOrNone(item.bending_strain_percent, 2) },
      { key: 'zt', value: toFixedOrNone(item.zt, 2) },
    ];
    cells.forEach(c => {
      const td = document.createElement('td');
      td.setAttribute('data-col-key', c.key);
      td.textContent = c.value === undefined ? '' : c.value;
      tr.appendChild(td);
    });
    // 动作列：工艺详情按钮
    const tdAct = document.createElement('td');
    tdAct.setAttribute('data-col-key', 'actions');
    const btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'btn btn--secondary';
    btn.innerHTML = (window._ ? _('Detail') : 'Detail');
    const proc = item.heat_treatment_process || '';
    btn.addEventListener('click', ()=> openProcModal(proc));
    tdAct.appendChild(btn);
    tr.appendChild(tdAct);
    return tr;
  }

  function renderTable(items){
    const tbody = document.querySelector('#cer-exp-table tbody');
    if (!tbody) return;
    tbody.innerHTML = '';
    if (!items || !items.length){
      const tr = document.createElement('tr');
      const td = document.createElement('td');
      const colCount = document.querySelectorAll('#cer-exp-table thead th').length || 6;
      td.colSpan = colCount; td.textContent = (window._ ? _('No results') : 'No results');
      tr.appendChild(td); tbody.appendChild(tr); return;
    }
    items.forEach(it => tbody.appendChild(buildRow(it)));
    // 应用列显隐
    (window._cerExpApplyColumnVisibility || applyColumnVisibility)(getVisibleCols());
  }

  function renderPagination(total, page, pageSize, onPage){
    const el = document.getElementById('cer-exp-pagination');
    if (!el) return;
    el.innerHTML='';
    const pages = Math.max(1, Math.ceil(total / pageSize));
    const mk = (p, label, dis) => { const b=document.createElement('button'); b.className='btn'+(dis?' disabled':''); b.disabled=!!dis; b.textContent=label; b.addEventListener('click', ()=>onPage(p)); return b; };
    el.appendChild(mk(1, '<<', page===1));
    el.appendChild(mk(Math.max(1,page-1), '<', page===1));
    const span=document.createElement('span'); span.style.margin='0 0.5rem'; span.textContent = `${page} / ${pages}`; el.appendChild(span);
    el.appendChild(mk(Math.min(pages,page+1), '>', page===pages));
    el.appendChild(mk(pages, '>>', page===pages));
  }

  function attachPerPage(form){
    const perBtn = document.getElementById('perPageBtn');
    const perMenu = document.getElementById('perPageMenu');
    const perCurrent = document.getElementById('perPageCurrent');
    if (perBtn && perMenu && perCurrent){
      let ps='20'; try { ps = localStorage.getItem('cer_exp_per_page') || '20'; } catch {}
      perCurrent.textContent = `(${ps})`;
      perBtn.addEventListener('click', ()=>{ perMenu.classList.toggle('is-hidden'); });
      perMenu.querySelectorAll('[data-per-page]').forEach(item => {
        item.addEventListener('click', ()=>{
          const n = item.getAttribute('data-per-page');
          try { localStorage.setItem('cer_exp_per_page', String(n)); } catch {}
          perCurrent.textContent = `(${n})`;
          perMenu.classList.add('is-hidden');
          saveState(form, 1); loadPage(form, 1);
        });
      });
    }
  }

  function compareValues(a,b,numeric){
    if (numeric){ const na=Number(a), nb=Number(b); if (isNaN(na)&&isNaN(nb)) return 0; if (isNaN(na)) return -1; if (isNaN(nb)) return 1; return na-nb; }
    const sa=(a??'').toString(); const sb=(b??'').toString(); return sa.localeCompare(sb);
  }

  function sortCurrentTbody(sortKey, order){
    const tbody = document.querySelector('#cer-exp-table tbody'); if (!tbody) return;
    const rows = Array.from(tbody.querySelectorAll('tr'));
    const numericKeys = new Set(['bending_strength_mpa','bending_strain_percent','zt']);
    rows.sort((r1,r2)=>{
      let v1 = r1.querySelector(`[data-col-key="${sortKey}"]`)?.textContent ?? '';
      let v2 = r2.querySelector(`[data-col-key="${sortKey}"]`)?.textContent ?? '';
      const cmp = compareValues(v1, v2, numericKeys.has(sortKey));
      return order==='descending' ? -cmp : cmp;
    });
    rows.forEach(r=>tbody.appendChild(r));
  }

  function initSorting(){
    const thead = document.querySelector('#cer-exp-table thead'); if (!thead) return;
    const headers = Array.from(thead.querySelectorAll('th.sortable'));
    headers.forEach(th => {
      th.addEventListener('click', ()=>{
        const cur = th.getAttribute('aria-sort') || 'none';
        const next = cur === 'ascending' ? 'descending' : 'ascending';
        headers.forEach(h=>h.setAttribute('aria-sort','none'));
        th.setAttribute('aria-sort', next);
        const key = th.getAttribute('data-sort-key');
        try { localStorage.setItem('cer_exp_sort', JSON.stringify({key, order: next})); } catch {}
        sortCurrentTbody(key, next);
      });
    });
    try {
      const raw = localStorage.getItem('cer_exp_sort'); if (raw){ const {key, order} = JSON.parse(raw); const target = headers.find(h=>h.getAttribute('data-sort-key')===key); if (target){ headers.forEach(h=>h.setAttribute('aria-sort','none')); target.setAttribute('aria-sort', order); }}
    } catch {}
  }

  async function loadPage(form, page=1){
    const params = qs(form); params.set('page', String(page));
    const url = '/Ceramics/experiment/query?' + params.toString();
    let data;
    try {
      const res = await fetch(url, { headers: { 'Accept': 'application/json' } });
      if (!res.ok) throw new Error(String(res.status));
      data = await res.json();
    } catch (e) {
      console.error('ceramics experiment query failed', e);
      renderTable([]); renderPagination(0,1,Number(params.get('page_size')||'20'), ()=>{}); return;
    }
    renderTable(data.items || []);
    renderPagination(data.total||0, data.page||1, data.page_size||20, p=>{ saveState(form,p); loadPage(form,p); });
    try { const raw = localStorage.getItem('cer_exp_sort'); if (raw){ const {key, order} = JSON.parse(raw); if (key&&order) sortCurrentTbody(key, order); } } catch {}
  }

  document.addEventListener('DOMContentLoaded', function(){
    const form = document.getElementById('cerExpForm'); if (!form) return;
    const btnQuery = document.getElementById('btn-query');
    btnQuery && btnQuery.addEventListener('click', ()=>{ saveState(form,1); loadPage(form,1); });
    const inp = document.getElementById('cerExpSearchInput'); if (inp) inp.addEventListener('keydown', (e)=>{ if (e.key==='Enter'){ e.preventDefault(); saveState(form,1); loadPage(form,1); }});
    attachPerPage(form);
    // 列菜单绑定
    const colBtn = document.getElementById('colToggleBtn');
    const colMenu = document.getElementById('colMenu');
    if (colBtn && colMenu){
      colBtn.addEventListener('click', ()=>{
        colMenu.classList.toggle('is-hidden');
        const expanded = !colMenu.classList.contains('is-hidden');
        colBtn.classList.toggle('active', expanded);
        colBtn.setAttribute('aria-expanded', expanded ? 'true' : 'false');
      });
      document.getElementById('applyColsBtn')?.addEventListener('click', ()=>{
        const checks = Array.from(colMenu.querySelectorAll('input[type="checkbox"]'));
        const selected = new Set(checks.filter(cb=>cb.checked).map(cb=>cb.value));
        setVisibleCols(selected); (window._cerExpApplyColumnVisibility || applyColumnVisibility)(selected);
        colMenu.classList.add('is-hidden'); colBtn.classList.remove('active'); colBtn.setAttribute('aria-expanded','false');
      });
      // 初始应用
      (window._cerExpApplyColumnVisibility || applyColumnVisibility)(getVisibleCols());
    }
    // 表头删除列按钮
    document.querySelectorAll('#cer-exp-table th .col-remove').forEach(btn => {
      btn.addEventListener('click', (e)=>{
        e.stopPropagation();
        const key = btn.getAttribute('data-col-key'); if (!key) return;
        const set = getVisibleCols(); set.delete(key); setVisibleCols(set); (window._cerExpApplyColumnVisibility || applyColumnVisibility)(set);
      });
    });
    initSorting();
    const { page } = restoreState(form); loadPage(form, page||1);
  });

  // ===== 工艺弹窗逻辑 =====
  function openProcModal(text){
    const modal = document.getElementById('expProcModal'); if (!modal) return;
    const txt = document.getElementById('expProcText'); if (txt) txt.textContent = text || '';
    modal.style.display = 'flex';
    const closeBtn = document.getElementById('expProcClose');
    closeBtn && closeBtn.addEventListener('click', ()=>{ modal.style.display = 'none'; });
    modal.addEventListener('click', (e)=>{ if (e.target === modal) modal.style.display = 'none'; });
  }
})();
