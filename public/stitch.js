const form = document.querySelector('#qaForm');
const questionInput = document.querySelector('#questionInput');
const charCounter = document.querySelector('#charCounter');
const validationError = document.querySelector('#validationError');
const validationText = document.querySelector('#validationErrorText');
const askButton = document.querySelector('#askBtn');
const responseArea = document.querySelector('#responseArea');
const loading = document.querySelector('#stateLoading');
const verified = document.querySelector('#stateVerifiedAnswer');
const message = document.querySelector('#stateMessage');
const fundButtons = [...document.querySelectorAll('.fund-btn')];
let selectedFund = '';
let lastAnswer = null;
let lastQuestion = '';

const categoryTitles = {
  CLARIFICATION_REQUIRED: 'Which HDFC fund do you mean?',
  ADVICE_OR_OPINION: 'Facts-only boundary',
  PERFORMANCE_REQUEST: 'Performance requests are outside scope',
  OUT_OF_SCOPE: 'Outside supported scope',
  UNSUPPORTED_BY_SOURCES: 'Fact not found in approved sources',
  SENSITIVE_DATA: 'Please remove personal information',
  SERVICE_ERROR: 'Unable to retrieve verified facts',
};

function updateCounter() {
  charCounter.textContent = `${questionInput.value.length} / 1000`;
  validationError.classList.add('hidden');
}

function setQuestion(value, submitNow = false) {
  questionInput.value = value;
  updateCounter();
  if (submitNow) form.requestSubmit();
  else questionInput.focus();
}

function showValidation(text) {
  validationText.textContent = text;
  validationError.classList.remove('hidden');
  questionInput.focus();
}

function showOnly(state) {
  responseArea.hidden = false;
  loading.hidden = state !== loading;
  verified.hidden = state !== verified;
  message.hidden = state !== message;
  responseArea.scrollIntoView({block: 'nearest', behavior: 'smooth'});
}

function approvedCitation(payload, link, label) {
  link.hidden = true;
  if (!payload?.citation?.url || !payload.citation.label) return false;
  try {
    const url = new URL(payload.citation.url);
    if (url.protocol !== 'https:' || url.hostname !== 'groww.in') return false;
    link.href = url.href;
    label.textContent = payload.citation.label;
    link.hidden = false;
    return true;
  } catch {
    return false;
  }
}

function sourceDate(value) {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? '' :
    `Last updated from sources: ${date.toLocaleDateString('en-IN', {day: 'numeric', month: 'short', year: 'numeric'})}`;
}

function fundInQuestion(text) {
  const normalized = text.toLowerCase();
  return fundButtons.map(button => button.dataset.fund)
    .find(fund => normalized.includes(fund.toLowerCase())) || '';
}

function renderFollowups(fund) {
  const container = document.querySelector('#nextQuestionChips');
  container.replaceChildren();
  if (!fund) return;
  for (const topic of ['exit load', 'minimum SIP', 'benchmark']) {
    const button = document.createElement('button');
    button.type = 'button';
    button.className = 'px-3 py-1.5 rounded-lg bg-canvas dark:bg-dark-elevated border border-outline dark:border-dark-border hover:border-brand text-xs font-medium text-charcoal dark:text-dark-text focus-ring';
    button.textContent = `Ask about ${topic} →`;
    button.addEventListener('click', () => setQuestion(`What is the ${topic} of ${fund}?`, true));
    container.append(button);
  }
}

function renderResponse(payload) {
  lastAnswer = null;
  if (payload.category === 'FACTUAL_SUPPORTED') {
    document.querySelector('#ansText').textContent = payload.answer;
    document.querySelector('#ansSourceDate').textContent = sourceDate(payload.source_updated_at);
    const hasCitation = approvedCitation(payload, document.querySelector('#ansCitationLink'), document.querySelector('#ansCitationLabel'));
    if (!hasCitation) {
      renderResponse({category: 'SERVICE_ERROR', answer: 'The source link could not be verified. Please try again later.'});
      return;
    }
    lastAnswer = payload;
    document.querySelector('#feedbackThanks').hidden = true;
    document.querySelector('#helpfulYes').hidden = false;
    document.querySelector('#helpfulNo').hidden = false;
    renderFollowups(fundInQuestion(lastQuestion) || selectedFund);
    showOnly(verified);
    return;
  }
  document.querySelector('#messageTitle').textContent = categoryTitles[payload.category] || categoryTitles.SERVICE_ERROR;
  document.querySelector('#messageText').textContent = payload.answer || 'Please try again later.';
  document.querySelector('#messageDate').textContent = sourceDate(payload.source_updated_at);
  approvedCitation(payload, document.querySelector('#messageCitationLink'), document.querySelector('#messageCitationLabel'));
  const options = document.querySelector('#clarificationFunds');
  options.replaceChildren();
  options.hidden = payload.category !== 'CLARIFICATION_REQUIRED';
  if (!options.hidden) {
    for (const button of fundButtons) {
      const option = document.createElement('button');
      option.type = 'button';
      option.className = 'p-2 text-xs font-semibold rounded-lg border border-outline dark:border-dark-border hover:border-brand bg-canvas dark:bg-dark-elevated focus-ring';
      option.textContent = button.dataset.fund;
      option.addEventListener('click', () => {
        const fact = lastQuestion.match(/expense ratio|exit load|minimum SIP|lock-in period|risk level|benchmark/i)?.[0] || 'facts';
        setQuestion(`What is the ${fact} of ${button.dataset.fund}?`, true);
      });
      options.append(option);
    }
  }
  showOnly(message);
}

fundButtons.forEach(button => button.addEventListener('click', () => {
  selectedFund = button.dataset.fund;
  fundButtons.forEach(item => {
    item.dataset.active = String(item === button);
    item.setAttribute('aria-pressed', String(item === button));
  });
  document.querySelector('#clearFundBtn').classList.remove('hidden');
}));
document.querySelector('#clearFundBtn').addEventListener('click', () => {
  selectedFund = '';
  fundButtons.forEach(button => {
    button.dataset.active = 'false';
    button.setAttribute('aria-pressed', 'false');
  });
  document.querySelector('#clearFundBtn').classList.add('hidden');
});
document.querySelectorAll('.topic-chip').forEach(button => button.addEventListener('click', () => {
  setQuestion(selectedFund ? `What is the ${button.dataset.topic.toLowerCase()} of ${selectedFund}?` :
    `What is the ${button.dataset.topic.toLowerCase()}?`);
}));
document.querySelectorAll('.example-card').forEach(button => button.addEventListener('click', () => setQuestion(button.dataset.example, true)));
questionInput.addEventListener('input', updateCounter);

form.addEventListener('submit', async event => {
  event.preventDefault();
  if (askButton.disabled) return;
  const question = questionInput.value.trim();
  if (!question) return showValidation('Enter a question before submitting.');
  if (question.length > 1000) return showValidation('Keep the question within 1,000 characters.');
  validationError.classList.add('hidden');
  lastQuestion = selectedFund && !/\bhdfc (?:large cap|flexi cap|equity fund|elss|tax saver|mid cap)\b/i.test(question) ?
    `${question} for ${selectedFund}` : question;
  askButton.disabled = true;
  showOnly(loading);
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 65000);
  try {
    const response = await fetch('/api/query', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({question: lastQuestion}),
      signal: controller.signal,
    });
    const payload = await response.json();
    if (!payload.category) throw new Error('Invalid response');
    renderResponse(payload);
  } catch {
    renderResponse({category: 'SERVICE_ERROR', answer: 'The verified source service is temporarily unavailable. Please try again later.'});
  } finally {
    clearTimeout(timeout);
    askButton.disabled = false;
  }
});

document.querySelector('#copyAnswerBtn').addEventListener('click', async () => {
  if (!lastAnswer) return;
  const button = document.querySelector('#copyAnswerBtn');
  try {
    await navigator.clipboard.writeText(`${lastAnswer.answer}\nSource: ${document.querySelector('#ansCitationLink').href}`);
    button.textContent = 'Copied';
    setTimeout(() => { button.textContent = 'Copy answer & source'; }, 2000);
  } catch {
    button.textContent = 'Copy unavailable';
  }
});
for (const id of ['helpfulYes', 'helpfulNo']) {
  document.querySelector(`#${id}`).addEventListener('click', () => {
    document.querySelector('#helpfulYes').hidden = true;
    document.querySelector('#helpfulNo').hidden = true;
    const thanks = document.querySelector('#feedbackThanks');
    thanks.textContent = 'Feedback preview only; not submitted.';
    thanks.hidden = false;
  });
}
document.querySelector('#themeToggleBtn').addEventListener('click', () => {
  const dark = document.documentElement.classList.toggle('dark');
  try { localStorage.setItem('groww_facts_theme', dark ? 'dark' : 'light'); } catch { /* Theme still works for this page. */ }
});
