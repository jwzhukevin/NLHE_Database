'use strict';
/*
高温合金 CSV 列表页前端脚本
- 负责：高级搜索参数采集、调用 /High_temperature_alloy/query、渲染表格与分页、生成详情链接
- 显示：Bending Strength (MPa)/zt/Bending Strain 统一两位小数；Strength 输入步长 1，zt/Strain 0.01
- 首列仅显示 HTA-<row>（不显示哈希）；详情链接包含行号+哈希：/High_temperature_alloy/detail/HTA-<row>-<hash10>
*/

(function(){
  const STORAGE_KEY = 'hta_search_state';

  // ========== 工具 ==========
  function toFixed2(v) {
    // 解释：将 null/undefined/空字符串/非数值/0 统一显示为 'None'
    if (v === null || v === undefined || v === '') return 'None';
    const n = Number(v);
    if (!isFinite(n) || n === 0) return 'None';
    return n.toFixed(2);
  }

  // ===== 工艺信息弹窗（全局） =====
  function openProcModal(procType, procHeat) {
    const modal = document.getElementById('htaProcModal');
    if (!modal) return;
    const typeEl = document.getElementById('htaProcType');
    const heatEl = document.getElementById('htaProcHeat');
    if (typeEl) typeEl.textContent = procType || '';
    if (heatEl) heatEl.textContent = procHeat || '';
    modal.style.display = 'flex';
  }

  function initProcModal() {
    const modal = document.getElementById('htaProcModal');
    if (!modal) return;
    const closeBtn = document.getElementById('htaProcClose');
    if (closeBtn) closeBtn.addEventListener('click', () => { modal.style.display = 'none'; });
    modal.addEventListener('click', (e) => {
      if (e.target === modal) modal.style.display = 'none';
    });
  }

  function qs(form) {
    // 解释：根据启用的元素复选框决定是否包含区间参数
    const fd = new FormData(form);
    const params = new URLSearchParams();

    // [Deprecated 20251008] 元素区间筛选（Ag/Au/Cu/I/K/S/Se/Te）已移除，不再拼接对应参数

    // 文本搜索（q）
    const q = (fd.get('q') || '').toString().trim();
    if (q) params.set('q', q);

    // 类别多选，合并为逗号分隔
    ['crystal_structure','process_type','heat_treatment_process'].forEach(k => {
      const selected = Array.from(form.querySelectorAll(`select[name="${k}"] option:checked`)).map(o=>o.value).filter(Boolean);
      if (selected.length) params.set(k, selected.join(','));
    });

    // 三项性能区间
    [['bending_strength_min','bending_strength_max'],['zt_min','zt_max'],['bending_strain_min','bending_strain_max']].forEach(([a,b])=>{
      const va = fd.get(a); if (va !== null && va !== '') params.set(a, va);
      const vb = fd.get(b); if (vb !== null && vb !== '') params.set(b, vb);
    });

    // 分页大小（从本地存储读取，默认20）
    let ps = '20';
    try { ps = localStorage.getItem('hta_per_page') || '20'; } catch {}
    params.set('page_size', ps);

    return params;
  }

  function setInputValue(el, val) {
    if (!el) return;
    if (val === undefined || val === null) return;
    el.value = String(val);
  }

  function ensureMultiSelectOptions(sel, values) {
    if (!sel || !Array.isArray(values) || !values.length) return;
    const existing = new Set(Array.from(sel.options).map(o=>o.value));
    values.forEach(v => {
      if (!existing.has(v)) {
        const opt = document.createElement('option');
        opt.value = v; opt.textContent = v; opt.selected = true;
        sel.appendChild(opt);
      }
    });
    // 标记选中
    Array.from(sel.options).forEach(o => { o.selected = values.includes(o.value); });
  }

  function saveState(form, page) {
    try {
      const params = qs(form);
      if (page) params.set('page', String(page));
      const state = {};
      for (const [k,v] of params.entries()) state[k] = v;
      localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
    } catch {}
  }

  function restoreState(form) {
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      if (!raw) return { page: 1 };
      const state = JSON.parse(raw);
      // page_size
      setInputValue(form.querySelector('[name="page_size"]'), state.page_size);
      // [Deprecated 20251008] 元素区间状态恢复已移除
      // 类别多选
      ['crystal_structure','process_type','heat_treatment_process'].forEach(k => {
        if (state[k]) {
          const arr = String(state[k]).split(',').filter(Boolean);
          ensureMultiSelectOptions(form.querySelector(`select[name="${k}"]`), arr);
        }
      });
      // 三项性能
      setInputValue(form.querySelector('[name="bending_strength_min"]'), state.bending_strength_min);
      setInputValue(form.querySelector('[name="bending_strength_max"]'), state.bending_strength_max);
      setInputValue(form.querySelector('[name="zt_min"]'), state.zt_min);
      setInputValue(form.querySelector('[name="zt_max"]'), state.zt_max);
      setInputValue(form.querySelector('[name="bending_strain_min"]'), state.bending_strain_min);
      setInputValue(form.querySelector('[name="bending_strain_max"]'), state.bending_strain_max);
      const page = parseInt(state.page || '1');
      return { page: isNaN(page) ? 1 : page };
    } catch { return { page: 1 }; }
  }

  async function fetchOptions(form) {
    // 解释：下拉选项可由现有数据中去重获得（简化：首次查询时拿一页数据并从返回中采样/或后端另设端点）。
    // 本期：先留空，等用户首次查询后根据结果填充多选项（避免额外端点）。
  }


  function renderPagination(total, page, pageSize, onPage) {
    const el = document.getElementById('hta-pagination');
    if (!el) return;
    el.innerHTML = '';
    const pages = Math.max(1, Math.ceil(total / pageSize));
    const makeBtn = (p, label, disabled) => {
      const b = document.createElement('button');
      b.className = 'btn' + (disabled ? ' disabled' : '');
      b.disabled = !!disabled;
      b.textContent = label;
      b.addEventListener('click', () => onPage(p));
      return b;
    };
    el.appendChild(makeBtn(1, '<<', page === 1));
    el.appendChild(makeBtn(Math.max(1, page - 1), '<', page === 1));
    const span = document.createElement('span');
    span.style.margin = '0 0.5rem';
    span.textContent = `${page} / ${pages}`;
    el.appendChild(span);
    el.appendChild(makeBtn(Math.min(pages, page + 1), '>', page === pages));
    el.appendChild(makeBtn(pages, '>>', page === pages));
  }

  // ===== 每页数量与列显隐 =====
  // 可显隐列（固定可见：hta_id, Material, actions），元素列已移除
  const OPTIONAL_COLUMNS = ['bending_strength_mpa','zt','bending_strain'];

  function getVisibleCols() {
    try {
      const raw = localStorage.getItem('hta_visible_cols');
      if (!raw) return new Set(OPTIONAL_COLUMNS);
      const arr = JSON.parse(raw);
      if (Array.isArray(arr) && arr.length) return new Set(arr);
      return new Set(OPTIONAL_COLUMNS);
    } catch { return new Set(OPTIONAL_COLUMNS); }
  }

  function setVisibleCols(set) {
    try { localStorage.setItem('hta_visible_cols', JSON.stringify(Array.from(set))); } catch {}
  }

  function applyColumnVisibility(visibleSet) {
    const keys = OPTIONAL_COLUMNS;
    keys.forEach(key => {
      const selector = `[data-col-key="${key}"]`;
      document.querySelectorAll(selector).forEach(el => {
        if (visibleSet.has(key)) el.classList.remove('hidden');
        else el.classList.add('hidden');
      });
    });
    // 同步菜单复选框
    const menu = document.getElementById('colMenu');
    if (menu) {
      menu.querySelectorAll('input[type="checkbox"]').forEach(cb => {
        cb.checked = visibleSet.has(cb.value);
      });
    }
  }

  function initToolbar(form) {
    // per-page menu
    const perBtn = document.getElementById('perPageBtn');
    const perMenu = document.getElementById('perPageMenu');
    const perCurrent = document.getElementById('perPageCurrent');
    if (perBtn && perMenu && perCurrent) {
      // 初始化显示
      let ps = '20';
      try { ps = localStorage.getItem('hta_per_page') || '20'; } catch {}
      perCurrent.textContent = `(${ps})`;
      perBtn.addEventListener('click', () => {
        perMenu.classList.toggle('is-hidden');
        const expanded = !perMenu.classList.contains('is-hidden');
        perBtn.classList.toggle('active', expanded);
        perBtn.setAttribute('aria-expanded', expanded ? 'true' : 'false');
      });
      perMenu.querySelectorAll('[data-per-page]').forEach(item => {
        item.addEventListener('click', () => {
          const n = item.getAttribute('data-per-page');
          try { localStorage.setItem('hta_per_page', String(n)); } catch {}
          perCurrent.textContent = `(${n})`;
          perMenu.classList.add('is-hidden');
          perBtn.classList.remove('active');
          perBtn.setAttribute('aria-expanded', 'false');
          saveState(form, 1);
          loadPage(form, 1);
        });
      });
    }

    // columns menu
    const colBtn = document.getElementById('colToggleBtn');
    const colMenu = document.getElementById('colMenu');
    if (colBtn && colMenu) {
      colBtn.addEventListener('click', () => {
        colMenu.classList.toggle('is-hidden');
        const expanded = !colMenu.classList.contains('is-hidden');
        colBtn.classList.toggle('active', expanded);
        colBtn.setAttribute('aria-expanded', expanded ? 'true' : 'false');
      });
      document.getElementById('applyColsBtn')?.addEventListener('click', () => {
        const checks = Array.from(colMenu.querySelectorAll('input[type="checkbox"]'));
        const selected = new Set(checks.filter(cb => cb.checked).map(cb => cb.value));
        setVisibleCols(selected);
        applyColumnVisibility(selected);
        colMenu.classList.add('is-hidden');
        colBtn.classList.remove('active');
        colBtn.setAttribute('aria-expanded', 'false');
      });
      // 初始应用一次
      applyColumnVisibility(getVisibleCols());
    }
  }

  // ===== 表头排序（当前页内） =====
  function compareValues(a, b, numeric) {
    if (numeric) {
      const na = Number(a); const nb = Number(b);
      if (isNaN(na) && isNaN(nb)) return 0;
      if (isNaN(na)) return -1; if (isNaN(nb)) return 1;
      return na - nb;
    }
    const sa = (a ?? '').toString();
    const sb = (b ?? '').toString();
    return sa.localeCompare(sb);
  }

  function sortCurrentTbody(sortKey, order) {
    const tbody = document.querySelector('#hta-table tbody');
    if (!tbody) return;
    const rows = Array.from(tbody.querySelectorAll('tr'));
    const numericKeys = new Set(['hta_row','bending_strength_mpa','zt','bending_strain']);
    rows.sort((r1, r2) => {
      let v1, v2;
      if (sortKey === 'hta_row') {
        // 从首列文本中提取数字
        const t1 = r1.querySelector('[data-col-key="hta_id"]').textContent || '';
        const t2 = r2.querySelector('[data-col-key="hta_id"]').textContent || '';
        v1 = parseInt(t1.replace(/[^0-9]/g, ''), 10);
        v2 = parseInt(t2.replace(/[^0-9]/g, ''), 10);
      } else if (OPTIONAL_COLUMNS.includes(sortKey)) {
        v1 = r1.querySelector(`[data-col-key="${sortKey}"]`)?.textContent ?? '';
        v2 = r2.querySelector(`[data-col-key="${sortKey}"]`)?.textContent ?? '';
      } else if (sortKey === 'Material') {
        v1 = r1.querySelector('[data-col-key="Material"]').textContent;
        v2 = r2.querySelector('[data-col-key="Material"]').textContent;
      } else {
        v1 = ''; v2 = '';
      }
      const cmp = compareValues(v1, v2, numericKeys.has(sortKey));
      return order === 'descending' ? -cmp : cmp;
    });
    rows.forEach(r => tbody.appendChild(r));
  }

  function initSorting() {
    const thead = document.querySelector('#hta-table thead');
    if (!thead) return;
    const headers = Array.from(thead.querySelectorAll('th.sortable'));
    headers.forEach(th => {
      th.addEventListener('click', () => {
        const current = th.getAttribute('aria-sort') || 'none';
        const next = current === 'ascending' ? 'descending' : 'ascending';
        headers.forEach(h => h.setAttribute('aria-sort', 'none'));
        th.setAttribute('aria-sort', next);
        const key = th.getAttribute('data-sort-key');
        try { localStorage.setItem('hta_sort', JSON.stringify({ key, order: next })); } catch {}
        sortCurrentTbody(key, next);
      });
    });
    // 恢复上次排序状态
    try {
      const raw = localStorage.getItem('hta_sort');
      if (raw) {
        const { key, order } = JSON.parse(raw);
        const target = headers.find(h => h.getAttribute('data-sort-key') === key);
        if (target && (order === 'ascending' || order === 'descending')) {
          headers.forEach(h => h.setAttribute('aria-sort', 'none'));
          target.setAttribute('aria-sort', order);
        }
      }
    } catch {}
  }

  function renderPagination(total, page, pageSize, onPage) {
    const el = document.getElementById('hta-pagination');
    if (!el) return;
    el.innerHTML = '';
    const pages = Math.max(1, Math.ceil(total / pageSize));
    const makeBtn = (p, label, disabled) => {
      const b = document.createElement('button');
      b.className = 'button-tool-small' + (disabled ? ' disabled' : '');
      b.disabled = !!disabled;
      b.textContent = label;
      b.addEventListener('click', () => onPage(p));
      return b;
    };
    el.appendChild(makeBtn(1, '<<', page === 1));
    el.appendChild(makeBtn(Math.max(1, page - 1), '<', page === 1));
    const span = document.createElement('span');
    span.style.margin = '0 0.5rem';
    span.textContent = `${page} / ${pages}`;
    el.appendChild(span);
    el.appendChild(makeBtn(Math.min(pages, page + 1), '>', page === pages));
    el.appendChild(makeBtn(pages, '>>', page === pages));
  }

  function restoreState(form, searchParams) {
    const state = searchParams || {};
    setInputValue(form.querySelector('[name="q"]'), state.q);
    ['crystal_structure','process_type','heat_treatment_process'].forEach(k => {
      if (state[k]) {
        const arr = String(state[k]).split(',').filter(Boolean);
        ensureMultiSelectOptions(form.querySelector(`select[name="${k}"]`), arr);
      }
    });
    setInputValue(form.querySelector('[name="bending_strength_min"]'), state.bending_strength_min);
    setInputValue(form.querySelector('[name="bending_strength_max"]'), state.bending_strength_max);
    setInputValue(form.querySelector('[name="zt_min"]'), state.zt_min);
    setInputValue(form.querySelector('[name="zt_max"]'), state.zt_max);
    setInputValue(form.querySelector('[name="bending_strain_min"]'), state.bending_strain_min);
    setInputValue(form.querySelector('[name="bending_strain_max"]'), state.bending_strain_max);
  }

  document.addEventListener('DOMContentLoaded', function(){
    const form = document.getElementById('htaSearchForm');
    if (!form) return;

    const runSearch = (page = 1) => {
        const params = qs(form);
        params.set('page', String(page));
        window.location.search = params.toString();
    };

    document.getElementById('htaClearSearchBtn')?.addEventListener('click', () => {
        const clearBtn = document.getElementById('htaClearSearchBtn');
        const searchInput = document.getElementById('htaSearchInput');
        if (searchInput) searchInput.value = '';

        const advancedInputs = document.querySelectorAll('#advancedSearch input, #advancedSearch select');
        advancedInputs.forEach(input => {
            if (input instanceof HTMLInputElement) {
                if (input.type === 'text' || input.type === 'number' || input.type === 'hidden') {
                    input.value = '';
                }
            } else if (input instanceof HTMLSelectElement) {
                if (input.multiple) {
                    Array.from(input.options).forEach(o => { o.selected = false; });
                } else {
                    input.selectedIndex = 0;
                }
            }
        });

        const suggestions = document.getElementById('htaSearchSuggestions');
        if (suggestions) suggestions.style.display = 'none';

        try { localStorage.removeItem('hta_search_state'); } catch {}

        if (clearBtn) {
            const originalText = clearBtn.textContent;
            const originalBg = clearBtn.style.backgroundColor;
            const originalColor = clearBtn.style.color;
            const originalBorder = clearBtn.style.borderColor;

            clearBtn.textContent = 'Cleared!';
            clearBtn.style.backgroundColor = '#10b981';
            clearBtn.style.color = 'white';
            clearBtn.style.borderColor = '#10b981';

            setTimeout(() => {
                clearBtn.textContent = originalText;
                clearBtn.style.backgroundColor = originalBg;
                clearBtn.style.color = originalColor;
                clearBtn.style.borderColor = originalBorder;
            }, 1000);
        }

        if (searchInput) searchInput.focus();
    });

    document.getElementById('btn-query')?.addEventListener('click', () => runSearch(1));
    document.getElementById('btn-query-adv')?.addEventListener('click', () => runSearch(1));
    document.getElementById('htaSearchInput')?.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') { e.preventDefault(); runSearch(1); }
    });

    document.getElementById('btn-reset')?.addEventListener('click', () => {
        window.location.href = window.location.pathname;
    });

    if (window.initialData) {
        renderPagination(window.initialData.total, window.initialData.page, window.initialData.page_size, p => {
            runSearch(p);
        });
    }

    if (window.searchParams) {
        restoreState(form, window.searchParams);
    }

    initToolbar(form);
    initSorting();
    initProcModal();
    document.querySelectorAll('#hta-table th .col-remove').forEach(btn => {
      btn.addEventListener('click', (e) => {
        e.stopPropagation();
        const key = btn.getAttribute('data-col-key');
        if (!key) return;
        const set = getVisibleCols();
        set.delete(key);
        setVisibleCols(set);
        applyColumnVisibility(set);
      });
    });
  });
})();
