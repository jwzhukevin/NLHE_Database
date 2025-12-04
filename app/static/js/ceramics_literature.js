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
    // 支持正则：当输入形如 /pattern/ 时，开启 regex 模式并剥离斜杠
    if (q.startsWith('/') && q.endsWith('/') && q.length >= 2){
      q = q.substring(1, q.length - 1);
      if (q) params.set('q', q);
      params.set('regex', '1');
    } else {
      if (q) params.set('q', q);
      // 不设置 regex，后端将走 ILIKE（不区分大小写）
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

  function buildRow(item){
    const tr = document.createElement('tr');
    const cells = [
      { key:'compound_name', value: item.compound_name },
      { key:'bending_strain', value: toFixedOrNone(item.bending_strain, 2) },
      { key:'bending_strength', value: (function(){
          const v = item.bending_strength; const u = item.bending_strength_unit;
          const sv = toFixedOrNone(v, 2); if (sv === 'None') return 'None';
          return u ? `${sv} ${u}` : sv;
        })()
      },
      { key:'space_group', value: item.space_group },
    ];
    cells.forEach(c=>{ const td=document.createElement('td'); td.setAttribute('data-col-key', c.key); td.textContent = c.value===undefined?'':c.value; tr.appendChild(td); });
    // 最后一列：文章地址 -> 统一 DOI 按钮
    const tdLink = document.createElement('td'); tdLink.setAttribute('data-col-key','article_link');
    const doi = item.doi || '';
    const btn = document.createElement('a');
    btn.className = 'btn btn--secondary';
    btn.textContent = 'DOI';
    if (doi){
      btn.href = 'https://doi.org/' + encodeURIComponent(doi);
      btn.target = '_blank';
      btn.rel = 'noopener noreferrer';
    } else {
      btn.href = '#';
      btn.addEventListener('click', (e)=>{ e.preventDefault(); });
      btn.classList.add('disabled');
    }
    tdLink.appendChild(btn);
    tr.appendChild(tdLink);
    return tr;
  }

  function renderTable(items){
    const tbody = document.querySelector('#cer-lit-table tbody'); if (!tbody) return;
    tbody.innerHTML='';
    if (!items || !items.length){ const tr=document.createElement('tr'); const td=document.createElement('td'); const colCount=document.querySelectorAll('#cer-lit-table thead th').length||5; td.colSpan=colCount; td.textContent=(window._? _('No results') : 'No results'); tr.appendChild(td); tbody.appendChild(tr); return; }
    items.forEach(it=>tbody.appendChild(buildRow(it)));
    // 应用列显隐
    applyColumnVisibility(getVisibleCols());
  }

  function renderPagination(total, page, pageSize, onPage){
    const el = document.getElementById('cer-lit-pagination'); if (!el) return;
    el.innerHTML=''; const pages = Math.max(1, Math.ceil(total/pageSize));
    const mk=(p,l,dis)=>{ const b=document.createElement('button'); b.className='btn'+(dis?' disabled':''); b.disabled=!!dis; b.textContent=l; b.addEventListener('click', ()=>onPage(p)); return b; };
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

  // ===== 列显隐（与高温合金页面一致的结构） =====
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
      if (sortKey==='article_link'){
        // 按 DOI 文本排序（按钮内无文本，无法排序），直接返回 0
        return 0;
      } else {
        v1=r1.querySelector(`[data-col-key="${sortKey}"]`)?.textContent||'';
        v2=r2.querySelector(`[data-col-key="${sortKey}"]`)?.textContent||'';
      }
      if (sortKey==='bending_strength'){
        // 从文本中提取数值部分进行比较
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
        setVisibleCols(selected); applyColumnVisibility(selected);
        colMenu.classList.add('is-hidden'); colBtn.classList.remove('active'); colBtn.setAttribute('aria-expanded','false');
      });
      // 初始应用
      applyColumnVisibility(getVisibleCols());
    }

    // 表头删除列按钮
    document.querySelectorAll('#cer-lit-table th .col-remove').forEach(btn => {
      btn.addEventListener('click', (e)=>{
        e.stopPropagation();
        const key = btn.getAttribute('data-col-key'); if (!key) return;
        const set = getVisibleCols(); set.delete(key); setVisibleCols(set); applyColumnVisibility(set);
      });
    });

    initSorting();
    const { page } = restoreState(form); loadPage(form, page||1);
  });
})();
