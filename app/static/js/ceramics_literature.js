'use strict';
(function(){
  const STORAGE_KEY = 'cer_lit_state';
  const VISIBLE_COLS_KEY = 'cer_lit_visible_cols';
  const SORT_KEY = 'cer_lit_sort';

  function toFixedOrNone(v, digits=2){
    if (v === null || v === undefined || v === '') return 'None';
    const n = Number(v); if (!isFinite(n) || n === 0) return 'None';
    return n.toFixed(digits);
  }

  function qs(form){
    const fd = new FormData(form);
    const params = new URLSearchParams();
    let q = (fd.get('q') || '').toString().trim();
    if (q.startsWith('/') && q.endsWith('/') && q.length >= 2){
      q = q.substring(1, q.length - 1);
      if (q) params.set('q', q);
      params.set('regex', '1');
    } else {
      if (q) params.set('q', q);
    }
    let ps='20'; try { ps = localStorage.getItem('cer_lit_per_page') || '20'; } catch {}
    params.set('page_size', ps);
    return params;
  }

  function saveState(form, page){
    try { const p = qs(form); if (page) p.set('page', String(page)); const o={}; for(const [k,v] of p.entries()) o[k]=v; localStorage.setItem(STORAGE_KEY, JSON.stringify(o)); } catch {}
  }
  
  function restoreState(form){
    try {
      const raw = localStorage.getItem(STORAGE_KEY); if (!raw) return { page: 1 };
      const s = JSON.parse(raw); const q = s.q || ''; const inp = document.getElementById('cerLitSearchInput'); if (inp) inp.value = q;
      const page = parseInt(s.page || '1', 10); return { page: isNaN(page) ? 1 : page };
    } catch { return { page: 1 }; }
  }

  function buildRow(item) {
    const template = document.getElementById('cer-lit-row-template');
    if (!template) return document.createElement('tr');

    const tr = template.content.cloneNode(true).querySelector('tr');

    const cells = {
      'compound_name': item.compound_name,
      'bending_strain': toFixedOrNone(item.bending_strain, 2),
      'bending_strength': (() => {
        const v = item.bending_strength;
        const u = item.bending_strength_unit;
        const sv = toFixedOrNone(v, 2);
        if (sv === 'None') return 'None';
        return u ? `${sv} ${u}` : sv;
      })(),
      'space_group': item.space_group,
    };

    for (const [key, value] of Object.entries(cells)) {
      const td = tr.querySelector(`[data-col-key="${key}"]`);
      if (td) td.textContent = value === undefined ? '' : value;
    }

    const doiLink = tr.querySelector('[data-col-key="article_link"] a');
    if (doiLink) {
      const doi = item.doi || '';
      if (doi) {
        doiLink.href = 'https://doi.org/' + encodeURIComponent(doi);
        doiLink.classList.remove('disabled');
        doiLink.title = window._ ? _('View on doi.org') : 'View on doi.org';
      } else {
        doiLink.href = '#';
        doiLink.addEventListener('click', (e) => e.preventDefault());
        doiLink.classList.add('disabled');
        doiLink.title = window._ ? _('DOI not available') : 'DOI not available';
      }
    }

    return tr;
  }

  function renderTable(items){
    const tbody = document.querySelector('#cer-lit-table tbody'); if (!tbody) return;
    tbody.innerHTML = '';
    if (!items || !items.length){
      const tr = document.createElement('tr');
      const td = document.createElement('td');
      const colCount = document.querySelectorAll('#cer-lit-table thead th').length || 5;
      td.colSpan = colCount;
      td.textContent = window._ ? _('No results') : 'No results';
      tr.appendChild(td);
      tbody.appendChild(tr);
    } else {
      items.forEach(it => tbody.appendChild(buildRow(it)));
    }
    applyColumnVisibility(getVisibleCols());
  }

  function renderPagination(total, page, pageSize, onPage){
    const el = document.getElementById('cer-lit-pagination'); if (!el) return;
    el.innerHTML=''; const pages = Math.max(1, Math.ceil(total/pageSize));
    const mk=(p,l,dis)=>{ const b=document.createElement('button'); b.className='button-tool-small' + (dis?' disabled':''); b.disabled=!!dis; b.textContent=l; b.addEventListener('click', ()=>onPage(p)); return b; };
    el.appendChild(mk(1,'<<',page===1)); el.appendChild(mk(Math.max(1,page-1),'<',page===1));
    const span=document.createElement('span'); span.style.margin='0 0.5rem'; span.textContent=`${page} / ${pages}`; el.appendChild(span);
    el.appendChild(mk(Math.min(pages,page+1),'>',page===pages)); el.appendChild(mk(pages,'>>',page===pages));
  }

  function attachPerPage(form){
    const perBtn=document.getElementById('perPageBtn'); const perMenu=document.getElementById('perPageMenu'); const perCurrent=document.getElementById('perPageCurrent');
    if (perBtn && perMenu && perCurrent){ let ps='20'; try { ps = localStorage.getItem('cer_lit_per_page')||'20'; } catch {}
      perCurrent.textContent = `(${ps})`;
      perBtn.addEventListener('click', ()=>{ perMenu.classList.toggle('is-hidden'); });
      perMenu.querySelectorAll('[data-per-page]')?.forEach(item=>{
        item.addEventListener('click', ()=>{ const n=item.getAttribute('data-per-page'); try { localStorage.setItem('cer_lit_per_page', String(n)); } catch {} perCurrent.textContent=`(${n})`; perMenu.classList.add('is-hidden'); saveState(form,1); loadPage(form,1); });
      });
    }
  }

  const OPTIONAL_COLUMNS = ['bending_strain','bending_strength','space_group'];

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

  function compareValues(a,b,numeric){ if (numeric){ const na=Number(a), nb=Number(b); if (isNaN(na)&&isNaN(nb)) return 0; if (isNaN(na)) return -1; if (isNaN(nb)) return 1; return na-nb; } const sa=(a??'').toString(); const sb=(b??'').toString(); return sa.localeCompare(sb); }

  function sortCurrentTbody(sortKey, order){
    const tbody=document.querySelector('#cer-lit-table tbody'); if (!tbody) return;
    const rows=Array.from(tbody.querySelectorAll('tr'));
    const numericKeys=new Set(['bending_strain','bending_strength']);
    rows.sort((r1,r2)=>{
      let v1, v2;
      if (sortKey==='article_link'){ return 0; }
      v1=r1.querySelector(`[data-col-key="${sortKey}"]`)?.textContent||'';
      v2=r2.querySelector(`[data-col-key="${sortKey}"]`)?.textContent||'';
      if (sortKey==='bending_strength'){
        v1 = parseFloat((v1||'').replace(/[^0-9.\-]/g,''));
        v2 = parseFloat((v2||'').replace(/[^0-9.\-]/g,''));
      }
      const cmp=compareValues(v1,v2,numericKeys.has(sortKey));
      return order==='descending' ? -cmp : cmp;
    });
    rows.forEach(r=>tbody.appendChild(r));
  }

  function initSorting(){ const thead=document.querySelector('#cer-lit-table thead'); if (!thead) return; const headers=Array.from(thead.querySelectorAll('th.sortable')); headers.forEach(th=>{ th.addEventListener('click', ()=>{ const cur=th.getAttribute('aria-sort')||'none'; const next=cur==='ascending'?'descending':'ascending'; headers.forEach(h=>h.setAttribute('aria-sort','none')); th.setAttribute('aria-sort', next); const key=th.getAttribute('data-sort-key'); try { localStorage.setItem('cer_lit_sort', JSON.stringify({key, order: next})); } catch {} sortCurrentTbody(key, next); }); }); try { const raw=localStorage.getItem('cer_lit_sort'); if (raw){ const {key, order}=JSON.parse(raw); const target=headers.find(h=>h.getAttribute('data-sort-key')===key); if (target){ headers.forEach(h=>h.setAttribute('aria-sort','none')); target.setAttribute('aria-sort', order); } } } catch {} }

  async function loadPage(form, page=1){
    const params=qs(form); params.set('page', String(page));
    const url='/Ceramics/literature/query?'+params.toString(); let data;
    try { const res=await fetch(url, { headers: { 'Accept':'application/json' } }); if (!res.ok) throw new Error(String(res.status)); data = await res.json(); }
    catch (e) { console.error('ceramics literature query failed', e); renderTable([]); renderPagination(0,1,Number(params.get('page_size')||'20'), ()=>{}); return; }
    renderTable(data.items||[]);
    renderPagination(data.total||0, data.page||1, data.page_size||20, p=>{ saveState(form,p); loadPage(form,p); });
    try { const raw=localStorage.getItem(SORT_KEY); if (raw){ const {key, order}=JSON.parse(raw); if (key&&order) sortCurrentTbody(key, order); } } catch {}
  }

  document.addEventListener('DOMContentLoaded', function(){
    const form=document.getElementById('cerLitForm'); if (!form) return;
    const btn=document.getElementById('btn-query');
    btn && btn.addEventListener('click', ()=>{ saveState(form,1); loadPage(form,1); });
    const inp=document.getElementById('cerLitSearchInput'); if (inp) inp.addEventListener('keydown', (e)=>{ if (e.key==='Enter'){ e.preventDefault(); saveState(form,1); loadPage(form,1); } });
    attachPerPage(form);

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
        setVisibleCols(selected); applyColumnVisibility(selected);
        colMenu.classList.add('is-hidden'); colBtn.classList.remove('active'); colBtn.setAttribute('aria-expanded','false');
      });
      applyColumnVisibility(getVisibleCols());
    }

    document.querySelectorAll('#cer-lit-table th .col-remove').forEach(btn => {
      btn.addEventListener('click', (e)=>{
        e.stopPropagation();
        const key = btn.getAttribute('data-col-key'); if (!key) return;
        const set = getVisibleCols(); set.delete(key); setVisibleCols(set); applyColumnVisibility(set);
      });
    });

    initSorting();
    const { page } = restoreState(form);
    loadPage(form, page || 1);
  });
})();
