// [static/js/chat.js] 聊天前端逻辑（流式输出）
// 说明：
// - 使用 fetch + ReadableStream 实现逐块渲染
// - 将用户输入追加到 messages，随后调用后端 /api/chat/stream
// - 简化用法：仅维持当前页面内的历史消息（如需持久化由后端落盘）

(function(){
  const elMessages = document.getElementById('messages');
  const elInput = document.getElementById('user-input');
  const btnSend = document.getElementById('send-btn');
  const btnClear = document.getElementById('clear-btn');
  const btnExport = document.getElementById('export-btn');
  const elModelSelect = document.getElementById('model-select');

  let history = [];
  let inFlight = false;

  function appendMessage(role, text) {
    const item = document.createElement('div');
    item.className = `msg ${role}`;
    item.innerHTML = `<div class="bubble">${escapeHtml(text)}</div>`;
    elMessages.appendChild(item);
    elMessages.scrollTop = elMessages.scrollHeight;
  }

  function escapeHtml(str) {
    return (str || '').replace(/[&<>"']/g, s => ({
      '&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;','\'':'&#39;'
    }[s]));
  }

  async function send() {
    if (inFlight) return;
    const content = (elInput.value || '').trim();
    if (!content) return;

    // 追加用户消息
    history.push({ role: 'user', content });
    appendMessage('user', content);
    elInput.value = '';

    // 占位 assistant 消息（流式更新）
    const placeholder = document.createElement('div');
    placeholder.className = 'msg assistant';
    const bubble = document.createElement('div');
    bubble.className = 'bubble';
    placeholder.appendChild(bubble);
    elMessages.appendChild(placeholder);
    elMessages.scrollTop = elMessages.scrollHeight;

    try {
      // 发送期间禁用输入与按钮，防止重复发送
      inFlight = true;
      if (btnSend) btnSend.disabled = true;
      if (elInput) elInput.disabled = true;
      const resp = await fetch('/api/chat/stream', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          messages: history,
          model: elModelSelect ? elModelSelect.value : 'deepseek-r1:14b',
          lang: window.CURRENT_LOCALE || 'en'
        })
      });

      // 如果响应不是流式文本，很可能是登录会话过期被重定向到了HTML登录页
      if (!resp.ok || !resp.body || !resp.headers.get('Content-Type').includes('text/plain')) {
          // 检查是否为登录重定向
          if (resp.headers.get('Content-Type').includes('text/html')) {
              // 刷新页面，让用户重新登录
              window.location.reload();
              return; // 终止执行
          }
          const err = await resp.text();
          throw new Error(err || ('HTTP ' + resp.status));
      }

      const reader = resp.body.getReader();
      const decoder = new TextDecoder('utf-8');
      let done = false;

      // --- 新的流式处理逻辑 ---
      let fullResponse = '';
      let buffer = '';
      let isThinking = false;
      let thinkingContainer = null;
      const answerContainer = document.createElement('div');
      bubble.appendChild(answerContainer);

      // 简单的Markdown转换，支持换行
      const markdownToHtml = (text) => {
          return escapeHtml(text).replace(/\n/g, '<br>');
      };

      // 折叠容器创建函数
      const ensureThinkingContainer = () => {
          if (thinkingContainer) return thinkingContainer;
          const wrapper = document.createElement('details');
          wrapper.className = 'thinking-process';
          wrapper.open = false;
          const summary = document.createElement('summary');
          summary.innerHTML = '<i class="fas fa-brain"></i> Thinking... (click to toggle)';
          const content = document.createElement('div');
          content.className = 'thinking-body';
          wrapper.appendChild(summary);
          wrapper.appendChild(content);
          bubble.insertBefore(wrapper, answerContainer);
          thinkingContainer = content;
          return thinkingContainer;
      };

      const THINK_START = 'Thinking...';
      const THINK_END = '...done thinking.';

      while (!done) {
        const { value, done: doneReading } = await reader.read();
        done = doneReading;
        buffer += decoder.decode(value || new Uint8Array(), { stream: !done });

        // 状态机：处理buffer中的文本
        let consumed = 0;
        if (!isThinking && buffer.includes(THINK_START)) {
            const idx = buffer.indexOf(THINK_START);
            const preText = buffer.substring(0, idx);
            answerContainer.innerHTML += markdownToHtml(preText);
            isThinking = true;
            consumed = idx + THINK_START.length;
        } else if (isThinking && buffer.includes(THINK_END)) {
            const idx = buffer.indexOf(THINK_END);
            const thinkingText = buffer.substring(0, idx);
            ensureThinkingContainer().innerHTML += markdownToHtml(thinkingText);
            isThinking = false;
            consumed = idx + THINK_END.length;
        } else if (!isThinking) {
            answerContainer.innerHTML += markdownToHtml(buffer);
            consumed = buffer.length;
        } else if (isThinking) {
            ensureThinkingContainer().innerHTML += markdownToHtml(buffer);
            consumed = buffer.length;
        }

        fullResponse += buffer;
        buffer = buffer.substring(consumed);
        elMessages.scrollTop = elMessages.scrollHeight;
      }
      // --- 流式处理逻辑结束 ---

      // 记录 assistant 完整回复到历史（用于继续上下文）
      history.push({ role: 'assistant', content: fullResponse });
    } catch (e) {
      bubble.textContent = `[Error] ${e.message || e}`;
    } finally {
      inFlight = false;
      if (btnSend) btnSend.disabled = false;
      if (elInput) {
        elInput.disabled = false;
        elInput.focus();
      }
    }
  }

  function clearChat() {
    history = [];
    elMessages.innerHTML = '';
  }

  function exportChat() {
    try {
      const data = JSON.stringify({ messages: history }, null, 2);
      const blob = new Blob([data], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = 'chat-export.json';
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
    } catch {}
  }

  btnSend && btnSend.addEventListener('click', send);
  // Enter 发送；Shift+Enter 换行；兼容 Ctrl/Cmd+Enter 也发送
  elInput && elInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') {
      if (e.shiftKey) return; // 保留换行
      e.preventDefault();
      send();
    }
  });
  btnClear && btnClear.addEventListener('click', clearChat);
  btnExport && btnExport.addEventListener('click', exportChat);

})();
