const form = document.querySelector("#question-form");
const input = document.querySelector("#question");
const submit = document.querySelector("#submit");
const result = document.querySelector("#result");
const answer = document.querySelector("#answer");
const citation = document.querySelector("#citation");
const sourceDate = document.querySelector("#source-date");
const category = document.querySelector("#result-category");
const characterCount = document.querySelector("#character-count");

const labels = {
  FACTUAL_SUPPORTED: "Verified answer",
  CLARIFICATION_REQUIRED: "Clarification needed",
  ADVICE_OR_OPINION: "Facts-only boundary",
  PERFORMANCE_REQUEST: "Facts-only boundary",
  OUT_OF_SCOPE: "Outside supported scope",
  UNSUPPORTED_BY_SOURCES: "Not verified",
  SENSITIVE_DATA: "Privacy warning",
  SERVICE_ERROR: "Service unavailable",
};

document.querySelectorAll(".example").forEach((button) => {
  button.addEventListener("click", () => {
    input.value = button.textContent.trim();
    characterCount.textContent = input.value.length;
    input.focus();
  });
});

input.addEventListener("input", () => {
  characterCount.textContent = input.value.length;
});

function showError(message) {
  result.className = "result error";
  category.textContent = "Request error";
  answer.textContent = message;
  citation.hidden = true;
  sourceDate.textContent = "";
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  const question = input.value.trim();
  if (!question) {
    showError("Enter a question before submitting.");
    return;
  }

  submit.disabled = true;
  submit.textContent = "Checking sources…";
  result.className = "result";
  category.textContent = "Loading";
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
    if (!response.ok && !payload.category) {
      throw new Error(payload.error || "The request could not be completed.");
    }
    const isWarning = payload.category !== "FACTUAL_SUPPORTED";
    result.className = `result${isWarning ? " warning" : ""}`;
    category.textContent = labels[payload.category] || payload.category;
    answer.textContent = payload.answer;
    citation.textContent = `Source: ${payload.citation.label}`;
    citation.href = payload.citation.url;
    citation.hidden = false;
    const date = new Date(payload.source_updated_at);
    sourceDate.textContent = `Last updated from sources: ${date.toLocaleDateString("en-IN", { day: "2-digit", month: "short", year: "numeric" })}`;
  } catch (error) {
    showError(error.message || "The assistant could not complete the request.");
  } finally {
    submit.disabled = false;
    submit.textContent = "Ask question";
  }
});
