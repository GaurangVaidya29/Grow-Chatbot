const form = document.querySelector("#question-form");
const input = document.querySelector("#question");
const submit = document.querySelector("#submit");
const buttonLabel = submit.querySelector(".button-label");
const result = document.querySelector("#result");
const answer = document.querySelector("#answer");
const citation = document.querySelector("#citation");
const citationLabel = document.querySelector("#citation-label");
const sourceDate = document.querySelector("#source-date");
const category = document.querySelector("#result-category");
const characterCount = document.querySelector("#character-count");
const validationMessage = document.querySelector("#validation-message");

const responseStates = {
  FACTUAL_SUPPORTED: { label: "Verified answer", className: "verified" },
  CLARIFICATION_REQUIRED: { label: "Clarification needed", className: "neutral" },
  ADVICE_OR_OPINION: { label: "Facts-only boundary", className: "boundary" },
  PERFORMANCE_REQUEST: { label: "Facts-only boundary", className: "boundary" },
  OUT_OF_SCOPE: { label: "Outside supported scope", className: "neutral" },
  UNSUPPORTED_BY_SOURCES: { label: "Not verified", className: "neutral" },
  SENSITIVE_DATA: { label: "Privacy warning", className: "privacy" },
  SERVICE_ERROR: { label: "Service unavailable", className: "error" },
};

document.querySelectorAll(".example").forEach((button) => {
  button.addEventListener("click", () => {
    input.value = button.querySelector("span:last-child").textContent.trim();
    characterCount.textContent = input.value.length;
    validationMessage.hidden = true;
    input.focus();
  });
});

input.addEventListener("input", () => {
  characterCount.textContent = input.value.length;
  validationMessage.hidden = true;
});

function setLoading(isLoading) {
  submit.disabled = isLoading;
  submit.classList.toggle("loading", isLoading);
  buttonLabel.textContent = isLoading ? "Checking approved sources…" : "Ask question";
  form.setAttribute("aria-busy", String(isLoading));
}

function showValidation(message) {
  validationMessage.textContent = message;
  validationMessage.hidden = false;
  input.focus();
}

function showError(message) {
  result.className = "result-card error";
  category.textContent = "Request error";
  answer.textContent = message;
  citationLabel.textContent = "HDFC Mutual Fund – Groww";
  citation.href = "https://groww.in/mutual-funds/amc/hdfc-mutual-funds";
  citation.hidden = false;
  sourceDate.textContent = "Source date unavailable";
  result.scrollIntoView({ behavior: "smooth", block: "nearest" });
}

function formatSourceDate(value) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "Source date unavailable";
  return `Last updated from sources: ${date.toLocaleDateString("en-IN", {
    day: "2-digit",
    month: "short",
    year: "numeric",
  })}`;
}

function showResponse(payload) {
  const state = responseStates[payload.category] || responseStates.SERVICE_ERROR;
  result.className = `result-card ${state.className}`;
  category.textContent = state.label;
  answer.textContent = payload.answer;
  citationLabel.textContent = `${payload.citation.label} – Groww`;
  citation.href = payload.citation.url;
  citation.hidden = false;
  sourceDate.textContent = formatSourceDate(payload.source_updated_at);
  result.scrollIntoView({ behavior: "smooth", block: "nearest" });
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  const question = input.value.trim();
  if (!question) {
    showValidation("Enter a question before submitting.");
    return;
  }
  if (question.length > 1000) {
    showValidation("Keep the question within 1000 characters.");
    return;
  }

  validationMessage.hidden = true;
  setLoading(true);
  result.className = "result-card neutral";
  category.textContent = "Checking sources";
  answer.textContent = "Retrieving evidence and preparing a grounded answer…";
  citation.hidden = true;
  sourceDate.textContent = "";

  try {
    const response = await fetch("/api/query", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question }),
    });
    const payload = await response.json();
    if (!payload.category) {
      throw new Error(payload.error || "The request could not be completed.");
    }
    showResponse(payload);
  } catch (error) {
    showError(error.message || "The assistant could not complete the request. Please try again later.");
  } finally {
    setLoading(false);
  }
});
