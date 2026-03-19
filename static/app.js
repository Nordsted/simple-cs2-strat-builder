const state = {
  maps: [],
  strategies: [],
  selectedMap: "",
  selectedSide: "T",
  selectedStrategyId: null,
};

const mapSelect = document.querySelector("#mapSelect");
const formMapSelect = document.querySelector("#formMapSelect");
const strategySelect = document.querySelector("#strategySelect");
const strategyMeta = document.querySelector("#strategyMeta");
const commandPreview = document.querySelector("#commandPreview");
const copyButton = document.querySelector("#copyButton");
const showButton = document.querySelector("#showButton");
const copyStatus = document.querySelector("#copyStatus");
const formStatus = document.querySelector("#formStatus");
const strategyForm = document.querySelector("#strategyForm");
const bindingFields = document.querySelector("#bindingFields");
const dialog = document.querySelector("#commandDialog");
const dialogTextarea = document.querySelector("#dialogTextarea");

init();

async function init() {
  renderBindingFields();
  registerEvents();
  await loadData();
}

function registerEvents() {
  mapSelect.addEventListener("change", () => {
    state.selectedMap = mapSelect.value;
    refreshStrategyOptions();
  });

  document.querySelectorAll('input[name="side"]').forEach((input) => {
    input.addEventListener("change", () => {
      state.selectedSide = input.value;
      refreshStrategyOptions();
    });
  });

  strategySelect.addEventListener("change", () => {
    state.selectedStrategyId = Number(strategySelect.value);
    renderSelectedStrategy();
  });

  copyButton.addEventListener("click", async () => {
    const command = getSelectedStrategy()?.command;
    if (!command) {
      copyStatus.textContent = "Choose a strategy first.";
      return;
    }

    try {
      await navigator.clipboard.writeText(command);
      copyStatus.textContent = "The command was copied to your clipboard.";
    } catch (error) {
      copyStatus.textContent = "Clipboard access failed. Use “Show command” as a fallback.";
    }
  });

  showButton.addEventListener("click", () => {
    const command = getSelectedStrategy()?.command;
    if (!command) {
      copyStatus.textContent = "Choose a strategy first.";
      return;
    }
    dialogTextarea.value = command;
    dialog.showModal();
    dialogTextarea.focus();
    dialogTextarea.select();
  });

  strategyForm.addEventListener("submit", submitStrategy);
}

async function loadData() {
  const response = await fetch("/api/data");
  const data = await response.json();
  state.maps = data.maps;
  state.strategies = data.strategies;
  state.selectedMap = state.maps[0]?.slug || "";
  populateMapOptions();
  refreshStrategyOptions();
}

function populateMapOptions() {
  mapSelect.innerHTML = "";
  formMapSelect.innerHTML = "";

  state.maps.forEach((map) => {
    const option = new Option(map.name, map.slug, map.slug === state.selectedMap, map.slug === state.selectedMap);
    mapSelect.add(option);
    formMapSelect.add(new Option(map.name, map.slug));
  });
}

function refreshStrategyOptions() {
  const filtered = getFilteredStrategies();
  strategySelect.innerHTML = "";

  filtered.forEach((strategy, index) => {
    const selected = index === 0;
    strategySelect.add(new Option(strategy.name, String(strategy.id), selected, selected));
  });

  state.selectedStrategyId = filtered[0]?.id ?? null;
  renderSelectedStrategy();
}

function getFilteredStrategies() {
  return state.strategies.filter(
    (strategy) => strategy.mapSlug === state.selectedMap && strategy.side === state.selectedSide,
  );
}

function getSelectedStrategy() {
  return state.strategies.find((strategy) => strategy.id === state.selectedStrategyId) || null;
}

function renderSelectedStrategy() {
  const strategy = getSelectedStrategy();
  if (!strategy) {
    strategyMeta.innerHTML = "<p>No strategies are available for this map and side yet.</p>";
    commandPreview.textContent = "No command available yet.";
    return;
  }

  const bindings = Object.entries(strategy.bindings)
    .sort(([a], [b]) => Number(a) - Number(b))
    .map(([slot, value]) => `<li><strong>Numpad ${slot}:</strong> ${escapeHTML(value)}</li>`)
    .join("");

  strategyMeta.innerHTML = `
    <p><strong>${escapeHTML(strategy.name)}</strong> · by ${escapeHTML(strategy.creator)}</p>
    <p>${escapeHTML(strategy.description)}</p>
    <p><strong>Source:</strong> ${escapeHTML(strategy.source)}</p>
    <ul>${bindings}</ul>
  `;
  commandPreview.textContent = strategy.command;
}

function renderBindingFields() {
  bindingFields.innerHTML = Array.from({ length: 9 }, (_, index) => {
    const slot = index + 1;
    return `
      <label class="binding-field">
        Numpad ${slot}
        <input type="text" name="binding-${slot}" placeholder="Example: say_team Flashing over A" />
      </label>
    `;
  }).join("");
}

async function submitStrategy(event) {
  event.preventDefault();
  formStatus.textContent = "Saving...";

  const formData = new FormData(strategyForm);
  const bindings = {};
  for (let slot = 1; slot <= 9; slot += 1) {
    const value = String(formData.get(`binding-${slot}`) || "").trim();
    if (value) {
      bindings[String(slot)] = value;
    }
  }

  const payload = {
    creator: String(formData.get("creator") || "").trim(),
    mapSlug: String(formData.get("mapSlug") || "").trim(),
    side: document.querySelector('input[name="formSide"]:checked')?.value || "T",
    name: String(formData.get("name") || "").trim(),
    description: String(formData.get("description") || "").trim(),
    bindings,
  };

  try {
    const response = await fetch("/api/strategies", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });

    if (!response.ok) {
      const errorPayload = await response.json().catch(() => ({ error: "Unknown error." }));
      throw new Error(errorPayload.error || "Unknown error.");
    }

    const strategy = await response.json();
    state.strategies.push(strategy);
    state.selectedMap = strategy.mapSlug;
    state.selectedSide = strategy.side;
    mapSelect.value = strategy.mapSlug;
    document.querySelector(`input[name="side"][value="${strategy.side}"]`).checked = true;
    refreshStrategyOptions();
    state.selectedStrategyId = strategy.id;
    strategySelect.value = String(strategy.id);
    renderSelectedStrategy();
    strategyForm.reset();
    formStatus.textContent = "The strategy was saved to the database.";
  } catch (error) {
    formStatus.textContent = `Could not save strategy: ${error.message}`;
  }
}

function escapeHTML(value) {
  return value
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}
