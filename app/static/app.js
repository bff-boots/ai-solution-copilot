const chat = document.querySelector('#chat');
const form = document.querySelector('#composer');
const question = document.querySelector('#question');
const send = document.querySelector('#send');
const template = document.querySelector('#messageTemplate');
let sessionId = localStorage.getItem('solution-copilot-session') || null;

function appendMessage(role, text, sources = []) {
  const node = template.content.firstElementChild.cloneNode(true);
  node.classList.add(role);
  node.querySelector('.avatar').textContent = role === 'user' ? '我' : 'AI';
  node.querySelector('.bubble').textContent = text;
  const sourceBox = node.querySelector('.sources');
  sources.forEach(source => {
    const tag = document.createElement('div');
    tag.className = 'source';
    tag.title = source.content;
    tag.textContent = `[${source.index}] ${source.title} · ${source.chunk_id}`;
    sourceBox.appendChild(tag);
  });
  chat.appendChild(node);
  chat.scrollTop = chat.scrollHeight;
  return node;
}

function resize() { question.style.height = 'auto'; question.style.height = `${Math.min(question.scrollHeight, 150)}px`; }
question.addEventListener('input', resize);
question.addEventListener('keydown', event => { if (event.key === 'Enter' && !event.shiftKey) { event.preventDefault(); form.requestSubmit(); } });

form.addEventListener('submit', async event => {
  event.preventDefault();
  const text = question.value.trim();
  if (!text) return;
  appendMessage('user', text);
  question.value = ''; resize(); send.disabled = true;
  const pending = appendMessage('assistant', '正在检索校园知识库…');
  try {
    const response = await fetch('/api/chat', { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({question:text, session_id:sessionId}) });
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || '服务暂时不可用');
    sessionId = data.session_id; localStorage.setItem('solution-copilot-session', sessionId);
    pending.querySelector('.bubble').textContent = data.answer;
    data.sources.forEach(source => { const tag=document.createElement('div'); tag.className='source'; tag.title=source.content; tag.textContent=`[${source.index}] ${source.title} · ${source.chunk_id}`; pending.querySelector('.sources').appendChild(tag); });
  } catch (error) { pending.querySelector('.bubble').textContent = `抱歉，${error.message}`; }
  finally { send.disabled = false; question.focus(); chat.scrollTop = chat.scrollHeight; }
});

document.querySelector('#generate').addEventListener('click', async () => {
  const industry = document.querySelector('#industry').value;
  const scenario = document.querySelector('#scenario').value.trim();
  const budget = document.querySelector('#budget').value.trim() || '未说明';
  const computeScale = document.querySelector('#computeScale').value.trim() || '未说明';
  if (!scenario) { document.querySelector('#scenario').focus(); return; }
  appendMessage('user', `客户需求｜${industry}\n场景：${scenario}\n预算：${budget}｜规模：${computeScale}`);
  const pending = appendMessage('assistant', '正在生成需求判断、架构建议与下一步行动…');
  const button = document.querySelector('#generate'); button.disabled = true;
  try {
    const response = await fetch('/api/solution', { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({industry, scenario, budget, compute_scale:computeScale, session_id:sessionId}) });
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || '服务暂时不可用');
    sessionId = data.session_id; localStorage.setItem('solution-copilot-session', sessionId);
    pending.querySelector('.bubble').textContent = data.answer;
    data.sources.forEach(source => { const tag=document.createElement('div'); tag.className='source'; tag.title=source.content; tag.textContent=`[${source.index}] ${source.title} · ${source.chunk_id}`; pending.querySelector('.sources').appendChild(tag); });
  } catch (error) { pending.querySelector('.bubble').textContent = `抱歉，${error.message}`; }
  finally { button.disabled = false; chat.scrollTop = chat.scrollHeight; }
});

document.querySelector('#newChat').addEventListener('click', async () => { if (sessionId) await fetch(`/api/sessions/${sessionId}`, {method:'DELETE'}); sessionId = null; localStorage.removeItem('solution-copilot-session'); chat.innerHTML = ''; appendMessage('assistant', '已开始新对话。填写上方客户需求，开始生成方案。'); });
