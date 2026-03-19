const NUMPAD_KEYS = {
  1: "KP_END",
  2: "KP_DOWNARROW",
  3: "KP_PGDN",
  4: "KP_LEFTARROW",
  5: "KP_5",
  6: "KP_RIGHTARROW",
  7: "KP_HOME",
  8: "KP_UPARROW",
  9: "KP_PGUP",
};

const state = {
  maps: [],
  strategies: [],
  selectedMap: "",
  selectedSide: "T",
  bindings: {},
  slotMeta: {},
  activeSlot: null,
};

const mapSelect = document.querySelector("#mapSelect");
const bindingsEditor = document.querySelector("#bindingsEditor");
const copyButton = document.querySelector("#copyButton");
const showButton = document.querySelector("#showButton");
const copyStatus = document.querySelector("#copyStatus");
const commandDialog = document.querySelector("#commandDialog");
const dialogTextarea = document.querySelector("#dialogTextarea");
const slotDialog = document.querySelector("#slotDialog");
const slotDialogTitle = document.querySelector("#slotDialogTitle");
const slotDialogOptions = document.querySelector("#slotDialogOptions");

init();

async function init() {
  registerEvents();
  await loadData();
}

function registerEvents() {
  mapSelect.addEventListener("change", () => {
    state.selectedMap = mapSelect.value;
    resetBindingsFromSelection();
  });

  document.querySelectorAll('input[name="side"]').forEach((input) => {
    input.addEventListener("change", () => {
      state.selectedSide = input.value;
      resetBindingsFromSelection();
    });
  });

  copyButton.addEventListener("click", async () => {
    const command = buildCommandFromState();
    if (!command) {
      copyStatus.textContent = "Add at least one bind before exporting the config.";
      return;
    }

    try {
      await navigator.clipboard.writeText(command);
      copyStatus.textContent = "The config was copied to your clipboard.";
    } catch (error) {
      copyStatus.textContent = "Clipboard access failed. Use “Show config” as a fallback.";
    }
  });

  showButton.addEventListener("click", () => {
    const command = buildCommandFromState();
    if (!command) {
      copyStatus.textContent = "Add at least one bind before exporting the config.";
      return;
    }

    dialogTextarea.value = command;
    commandDialog.showModal();
    dialogTextarea.focus();
    dialogTextarea.select();
  });
}

async function loadData() {
  const response = await fetch("/api/data");
  const data = await response.json();
  state.maps = data.maps;
  state.strategies = data.strategies;
  state.selectedMap = state.maps[0]?.slug || "";
  populateMapOptions();
  resetBindingsFromSelection();
}

function populateMapOptions() {
  mapSelect.innerHTML = "";
  state.maps.forEach((map) => {
    const selected = map.slug === state.selectedMap;
    mapSelect.add(new Option(map.name, map.slug, selected, selected));
  });
}

function getRelevantStrategies() {
  return state.strategies.filter(
    (strategy) => strategy.mapSlug === state.selectedMap && strategy.side === state.selectedSide,
  );
}

function getSlotOptions(slot) {
  return getRelevantStrategies()
    .filter((strategy) => strategy.bindings[String(slot)])
    .map((strategy) => ({
      strategyId: strategy.id,
      strategyName: strategy.name,
      command: strategy.bindings[String(slot)],
    }));
}

function resetBindingsFromSelection() {
  state.bindings = {};
  state.slotMeta = {};

  for (let slot = 1; slot <= 9; slot += 1) {
    const firstOption = getSlotOptions(slot)[0] || null;
    state.bindings[slot] = firstOption?.command || "";
    state.slotMeta[slot] = firstOption
      ? `Preset: ${firstOption.strategyName}`
      : "Manual / empty";
  }

  renderBindingsEditor();
  copyStatus.textContent = "";
}

function renderBindingsEditor() {
  bindingsEditor.innerHTML = Array.from({ length: 9 }, (_, index) => {
    const slot = index + 1;
    return `
      <article class="binding-row">
        <div class="binding-labels">
          <strong>Numpad ${slot}</strong>
          <span>${NUMPAD_KEYS[slot]}</span>
          <small>${escapeHTML(state.slotMeta[slot] || "Manual / empty")}</small>
        </div>
        <label class="binding-input-wrap">
          <span class="sr-only">Command for numpad ${slot}</span>
          <input
            type="text"
            data-slot-input="${slot}"
            value="${escapeHTML(state.bindings[slot] || "")}" 
            placeholder="Leave empty to skip this bind"
          />
        </label>
        <button type="button" data-slot-pick="${slot}">Pick strat</button>
      </article>
    `;
  }).join("");

  bindingsEditor.querySelectorAll("[data-slot-input]").forEach((input) => {
    input.addEventListener("input", () => {
      const slot = Number(input.dataset.slotInput);
      state.bindings[slot] = input.value;
      state.slotMeta[slot] = input.value.trim() ? "Manual edit" : "Manual / empty";
    });
  });

  bindingsEditor.querySelectorAll("[data-slot-pick]").forEach((button) => {
    button.addEventListener("click", () => openSlotDialog(Number(button.dataset.slotPick)));
  });
}

function openSlotDialog(slot) {
  state.activeSlot = slot;
  const options = getSlotOptions(slot);
  slotDialogTitle.textContent = `Pick a strat for numpad ${slot}`;

  const cards = options.map(
    (option) => `
      <button type="button" class="slot-option" data-slot-command="${escapeHTML(option.command)}" data-slot-name="${escapeHTML(option.strategyName)}">
        <strong>${escapeHTML(option.strategyName)}</strong>
        <span>${escapeHTML(option.command)}</span>
      </button>
    `,
  );

  cards.unshift(`
    <button type="button" class="slot-option clear-option" data-slot-clear="true">
      <strong>Clear this bind</strong>
      <span>Leave this numpad key unbound in the exported config.</span>
    </button>
  `);

  if (options.length === 0) {
    cards.push(`
      <div class="slot-empty-state">
        No predefined commands were found for this key on the selected map and side. You can still type a custom command manually.
      </div>
    `);
  }

  slotDialogOptions.innerHTML = cards.join("");

  slotDialogOptions.querySelectorAll("[data-slot-command]").forEach((button) => {
    button.addEventListener("click", () => {
      applySlotOption(slot, button.dataset.slotCommand, button.dataset.slotName);
      slotDialog.close();
    });
  });

  slotDialogOptions.querySelectorAll("[data-slot-clear]").forEach((button) => {
    button.addEventListener("click", () => {
      applySlotOption(slot, "", "Manual / empty");
      slotDialog.close();
    });
  });

  slotDialog.showModal();
}

function applySlotOption(slot, command, strategyName) {
  state.bindings[slot] = command;
  state.slotMeta[slot] = command ? `Preset: ${strategyName}` : "Manual / empty";
  renderBindingsEditor();
}

function buildCommandFromState() {
  const commands = [];

  for (let slot = 1; slot <= 9; slot += 1) {
    const rawValue = state.bindings[slot] || "";
    const cleanedValue = sanitizeCommand(rawValue);
    if (!cleanedValue) {
      continue;
    }
    const escapedValue = cleanedValue.replaceAll('"', "'");
    commands.push(`bind ${NUMPAD_KEYS[slot]} "${escapedValue}"`);
  }

  return commands.join("; ");
}

function sanitizeCommand(value) {
  return value.trim().replace(/\s+/g, " ");
}

function escapeHTML(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}
