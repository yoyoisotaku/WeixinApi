const introCard = document.getElementById('intro-card');
const surveyCard = document.getElementById('survey-card');
const resultCard = document.getElementById('result-card');
const resultEl = document.getElementById('result');

const STORAGE_KEY = 'growth_hr_preview_state_v1';

function show(el) { el.classList.remove('hidden'); }
function hide(el) { el.classList.add('hidden'); }

function loadState() {
  try {
    return JSON.parse(localStorage.getItem(STORAGE_KEY) || '{}');
  } catch {
    return {};
  }
}

function saveState(next) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
}

function normalizeGoals(cost, delivery, growth) {
  const sum = cost + delivery + growth;
  if (sum === 0) return { cost: 0, delivery: 0, growth: 0 };
  return {
    cost: +(cost / sum * 100).toFixed(1),
    delivery: +(delivery / sum * 100).toFixed(1),
    growth: +(growth / sum * 100).toFixed(1)
  };
}

function estimatePlan(data) {
  const goals = normalizeGoals(data.goal_cost, data.goal_delivery, data.goal_growth);
  const movable = Math.max(0, data.headcount - data.protected_roles);
  const aiPotential = Math.round(movable * (data.ai_replace_ratio / 100));

  let suggestion = '平衡策略：先AI试点，再局部结构调整';
  if (data.action_preference === 'ai_first') suggestion = 'AI优先：先替代任务，再做组织动作';
  if (data.action_preference === 'transfer_first') suggestion = '转岗优先：优先内部重新匹配';
  if (data.action_preference === 'natural_attrition') suggestion = '自然流失优先：冻结HC并优化排班';
  if (data.action_preference === 'layoff_first') suggestion = '裁员优先：以关键岗位保护为前提';

  const suggestedReduction = Math.max(0, Math.round(movable * (goals.cost / 100) * 0.25));
  const phase = data.pain_limit <= 8 ? '保守（2-3个迭代）' : data.pain_limit <= 15 ? '中性（2个迭代）' : '激进（1-2个迭代）';

  return `【老板叙述摘要】\n${data.narrative}\n
【目标归一化】\n降本 ${goals.cost}% / 稳交付 ${goals.delivery}% / 增长 ${goals.growth}%\n
【系统建议】\n1) 本轮策略：${suggestion}\n2) 可动人力池：${movable} 人（总人数 ${data.headcount} - 关键保护 ${data.protected_roles}）\n3) AI可替代潜力：约 ${aiPotential} 人等效工作量\n4) 建议本轮调整规模：约 ${suggestedReduction} 人（分阶段）\n5) 执行节奏：${phase}\n
【下一轮要补的数据】\n- 各部门实际 timesheet 利用率\n- 飞书组织架构与汇报关系\n- 合同到期与法务约束\n
【当前紧急问题】\n${data.urgent_issues}`;
}

function hydrateFromLocalStorage() {
  const state = loadState();
  if (state.narrative) {
    document.getElementById('narrative').value = state.narrative;
    show(surveyCard);
  }
  if (state.resultText) {
    show(resultCard);
    resultEl.textContent = state.resultText;
  }
}

document.getElementById('save-narrative').addEventListener('click', () => {
  const narrative = document.getElementById('narrative').value.trim();
  if (!narrative) {
    alert('请先填写老板自由讲述内容。');
    return;
  }
  const state = loadState();
  saveState({ ...state, narrative });
  show(surveyCard);
  surveyCard.scrollIntoView({ behavior: 'smooth' });
});

document.getElementById('survey-form').addEventListener('submit', (e) => {
  e.preventDefault();
  const form = new FormData(e.target);
  const state = loadState();
  const data = {
    narrative: state.narrative || '',
    headcount: Number(form.get('headcount')),
    fte_ratio: Number(form.get('fte_ratio')),
    goal_cost: Number(form.get('goal_cost')),
    goal_delivery: Number(form.get('goal_delivery')),
    goal_growth: Number(form.get('goal_growth')),
    pain_limit: Number(form.get('pain_limit')),
    ai_replace_ratio: Number(form.get('ai_replace_ratio')),
    protected_roles: Number(form.get('protected_roles')),
    urgent_issues: String(form.get('urgent_issues') || '').trim(),
    action_preference: String(form.get('action_preference') || 'ai_first')
  };

  const resultText = estimatePlan(data);
  resultEl.textContent = resultText;
  saveState({ ...state, ...data, resultText });
  show(resultCard);
  resultCard.scrollIntoView({ behavior: 'smooth' });
});

document.getElementById('reset').addEventListener('click', () => {
  localStorage.removeItem(STORAGE_KEY);
  location.reload();
});

document.getElementById('copy-result').addEventListener('click', async () => {
  try {
    await navigator.clipboard.writeText(resultEl.textContent || '');
    alert('已复制到剪贴板。');
  } catch {
    alert('复制失败，请手动复制。');
  }
});

hydrateFromLocalStorage();
