'use strict';
(function(){
  const VISIBLE_COLS_KEY = 'cer_exp_visible_cols';
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

  function renderPagination(total, page, pageSize, onPage){
    const el = document.getElementById('cer-exp-pagination');
    if (!el) return;
    el.innerHTML='';
    const pages = Math.max(1, Math.ceil(total / pageSize));
    const mk = (p, label, dis) => { const b=document.createElement('button'); b.className='button-tool-small'+(dis?' disabled':''); b.disabled=!!dis; b.textContent=label; b.addEventListener('click', ()=>onPage(p)); return b; };
    el.appendChild(mk(1, '<<', page===1));
    el.appendChild(mk(Math.max(1,page-1), '<', page===1));
    const span=document.createElement('span'); span.style.margin='0 0.5rem'; span.textContent = `${page} / ${pages}`;
    el.appendChild(span);
    el.appendChild(mk(Math.min(pages,page+1), '>', page===pages));
    el.appendChild(mk(pages, '>>', page===pages));
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

  document.addEventListener('DOMContentLoaded', function(){
    const form = document.getElementById('cerExpForm'); if (!form) return;

    const runSearch = (page = 1) => {
        const params = qs(form);
        params.set('page', String(page));
        window.location.search = params.toString();
    };

    document.getElementById('btn-query')?.addEventListener('click', () => runSearch(1));
    document.getElementById('cerExpSearchInput')?.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') { e.preventDefault(); runSearch(1); }
    });

    if (window.initialData) {
        renderPagination(window.initialData.total, window.initialData.page, window.initialData.page_size, p => {
            runSearch(p);
        });
    }

    if (window.searchParams && window.searchParams.q) {
        const input = document.getElementById('cerExpSearchInput');
        if (input) input.value = window.searchParams.q;
    }

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
          runSearch(1);
        });
      });
    }

    const colBtn = document.getElementById('colToggleBtn');
    const colMenu = document.getElementById('colMenu');
    if (colBtn && colMenu){
      colBtn.addEventListener('click', ()=>{ colMenu.classList.toggle('is-hidden'); });
      document.getElementById('applyColsBtn')?.addEventListener('click', ()=>{
        const checks = Array.from(colMenu.querySelectorAll('input[type="checkbox"]'));
        const selected = new Set(checks.filter(cb=>cb.checked).map(cb=>cb.value));
        setVisibleCols(selected); applyColumnVisibility(selected);
        colMenu.classList.add('is-hidden');
      });
    }

    document.querySelectorAll('#cer-exp-table th .col-remove').forEach(btn => {
      btn.addEventListener('click', (e)=>{
        e.stopPropagation();
        const key = btn.getAttribute('data-col-key'); if (!key) return;
        const set = getVisibleCols(); set.delete(key); setVisibleCols(set); applyColumnVisibility(set);
      });
    });

    initSorting();
    applyColumnVisibility(getVisibleCols());
  });
})();
