// app/static/js/property-filter.js
// 特殊性质筛选按钮“即点即搜”脚本

document.addEventListener('DOMContentLoaded', function() {
    const propertyFilters = document.getElementById('propertyFilters');
    if (!propertyFilters) return;

    const toggleBtn = document.getElementById('propertyFiltersToggle');
    const optionsContainer = document.getElementById('propertyFiltersOptions');

    if (toggleBtn && optionsContainer) {
        toggleBtn.addEventListener('click', function() {
            const isExpanded = toggleBtn.getAttribute('aria-expanded') === 'true';
            const nextExpanded = !isExpanded;

            toggleBtn.setAttribute('aria-expanded', String(nextExpanded));

            if (nextExpanded) {
                propertyFilters.classList.remove('collapsed');
            } else {
                propertyFilters.classList.add('collapsed');
            }
        });
    }

    propertyFilters.addEventListener('click', function(event) {
        const button = event.target.closest('.button-filter');
        if (!button) return;

        const propName = button.dataset.prop;
        if (!propName) return;

        // 构建新的URL
        const currentUrl = new URL(window.location.href);
        const params = currentUrl.searchParams;

        // 根据按钮当前是否已有 'active' 类来决定是添加还是删除参数
        // 注意：此时 classList.toggle 还没执行，所以逻辑是反的
        if (button.classList.contains('active')) {
            params.delete(propName);
        } else {
            params.set(propName, '1');
        }

        // 筛选时总是回到第一页
        params.set('page', '1');

        // 跳转到新URL
        window.location.href = currentUrl.toString();
    });
});
