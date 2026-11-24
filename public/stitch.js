const form = document.querySelector('#question-form');
const input = document.querySelector('#question');
const count = document.querySelector('#count');
const validation = document.querySelector('#validation');
const submit = document.querySelector('#submit');
const result = document.querySelector('#result');
const resultLabel = document.querySelector('#result-label');
const resultDate = document.querySelector('#result-date');
const answer = document.querySelector('#answer');
const citation = document.querySelector('#citation');
const citationLabel = document.querySelector('#citation-label');
const actions = document.querySelector('#answer-actions');
const followups = document.querySelector('#followups');
let selectedFund = '';
let lastResponse = null;

const labels = {
  FACTUAL_SUPPORTED: '✓ VERIFIED ANSWER',
  CLARIFICATION_REQUIRED: 'CLARIFICATION NEEDED',
  ADVICE_OR_OPINION: 'FACTS-ONLY BOUNDARY',
  PERFORMANCE_REQUEST: 'FACTS-ONLY BOUNDARY',
  OUT_OF_SCOPE: 'OUTSIDE SUPPORTED SCOPE',
  UNSUPPORTED_BY_SOURCES: 'FACT NOT VERIFIED',
  SENSITIVE_DATA: 'PRIVACY WARNING',
  SERVICE_ERROR: 'SERVICE UNAVAILABLE',
};

function setQuestion(value) {
  input.value = value;
  count.textContent = `${input.value.length} / 1000`;
  validation.hidden = true;
  input.focus();
}

function showValidation(message) {
  validation.textContent = message;
  validation.hidden = false;
  input.focus();
}

function showResult(payload) {
  lastResponse = payload;
  result.hidden = false;
  const category = Object.hasOwn(labels, payload.category) ? payload.category : 'SERVICE_ERROR';
  result.classList.toggle('neutral', category !== 'FACTUAL_SUPPORTED');
  resultLabel.textContent = labels[category];
  answer.textContent = payload.answer || 'The assistant could not complete this request.';
  const date = new Date(payload.source_updated_at);
  resultDate.textContent = Number.isNaN(date.getTime()) ? '' : `Source retrieved: ${date.toLocaleDateString('en-IN', {day: 'numeric', month: 'short', year: 'numeric'})}`;
  citation.hidden = true;
  if (payload.citation && payload.citation.label && payload.citation.url) {
    try {
      const url = new URL(payload.citation.url);
      if (url.protocol === 'https:' && url.hostname === 'groww.in') {
        citation.href = url.href;
        citationLabel.textContent = payload.citation.label;
        citation.hidden = false;
      }
    } catch { /* Invalid source URL is not rendered. */ }
  }
  actions.hidden = category !== 'FACTUAL_SUPPORTED' || citation.hidden;
  followups.replaceChildren();
  if (!actions.hidden) {
    const fund = selectedFund || inferFund(input.value);
    if (fund) {
      for (const topic of ['exit load', 'minimum SIP', 'benchmark']) {
        const button = document.createElement('button');
        button.type = 'button';
        button.textContent = `Ask about ${topic}`;
        button.addEventListener('click', () => setQuestion(`What is the ${topic} of ${fund}?`));
        followups.append(button);
      }
    }
  }
  result.scrollIntoView({block: 'nearest', behavior: 'smooth'});
}

function inferFund(question) {
  const lower = question.toLowerCase();
  return [...document.querySelectorAll('.fund-card')]
    .map(button => button.dataset.fund)
    .find(fund => lower.includes(fund.replace(/ Direct (Plan )?Growth/i, '').toLowerCase())) || '';
}

document.querySelectorAll('.fund-card').forEach(button => button.addEventListener('click', () => {
  selectedFund = button.dataset.fund;
  document.querySelectorAll('.fund-card').forEach(item => item.setAttribute('aria-pressed', String(item === button)));
  document.querySelector('#clear-fund').hidden = false;
}));
document.querySelector('#clear-fund').addEventListener('click', () => {
  selectedFund = '';
  document.querySelectorAll('.fund-card').forEach(button => button.setAttribute('aria-pressed', 'false'));
  document.querySelector('#clear-fund').hidden = true;
});
document.querySelectorAll('[data-topic]').forEach(button => button.addEventListener('click', () => {
  if (selectedFund) setQuestion(`What is the ${button.dataset.topic} of ${selectedFund}?`);
  else setQuestion(`What is the ${button.dataset.topic} of HDFC [fund name]?`);
}));
document.querySelectorAll('[data-question]').forEach(button => button.addEventListener('click', () => setQuestion(button.dataset.question)));
input.addEventListener('input', () => { count.textContent = `${input.value.length} / 1000`; validation.hidden = true; });

form.addEventListener('submit', async event => {
  event.preventDefault();
  const question = input.value.trim();
  if (!question) return showValidation('Enter a question before submitting.');
  if (question.length > 1000) return showValidation('Keep the question within 1,000 characters.');
  if (question.includes('[fund name]')) return showValidation('Select a fund or replace [fund name] with a supported HDFC fund.');
  validation.hidden = true;
  submit.disabled = true;
  submit.textContent = 'Checking sources…';
  showResult({category: 'CLARIFICATION_REQUIRED', answer: 'Checking approved sources…'});
  try {
    const resolvedQuestion = selectedFund && !/\bhdfc\b/i.test(question) ? `${question} for ${selectedFund}` : question;
    const response = await fetch('/api/query', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({question: resolvedQuestion})});
    const payload = await response.json();
    if (!payload.category) throw new Error(payload.error || 'The request could not be completed.');
    showResult(payload);
  } catch {
    showResult({category: 'SERVICE_ERROR', answer: 'The verified source service is temporarily unavailable. Please try again later.'});
  } finally {
    submit.disabled = false;
    submit.textContent = 'Ask question';
  }
});

document.querySelector('#copy').addEventListener('click', async () => {
  if (!lastResponse || citation.hidden) return;
  try {
    await navigator.clipboard.writeText(`${lastResponse.answer}\nSource: ${citation.href}`);
    document.querySelector('#copy').textContent = 'Copied';
    setTimeout(() => { document.querySelector('#copy').textContent = 'Copy answer & source'; }, 2000);
  } catch { document.querySelector('#copy').textContent = 'Copy unavailable'; }
});
