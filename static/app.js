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

const TEAM_CHAT_PREFIX = "say_team";
const MAX_SLOTS = 9;

const state = {
  maps: [],
  strategies: [],
  selectedMap: "",
  selectedSide: "T",
  slots: [],
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
const sideButtons = Array.from(document.querySelectorAll("[data-side]"));

init();

async function init() {
  registerEvents();
  await loadData();
}

function registerEvents() {
  mapSelect.addEventListener("change", () => {
    state.selectedMap = mapSelect.value;
    resetSlotsFromSelection();
  });

  sideButtons.forEach((button) => {
    button.addEventListener("click", () => {
      if (state.selectedSide === button.dataset.side) {
        return;
      }

      state.selectedSide = button.dataset.side;
      syncSideButtons();
      resetSlotsFromSelection();
    });
  });

  copyButton.addEventListener("click", async () => {
    const command = buildCommandFromState();
    if (!command) {
      copyStatus.textContent = "Add at least one strategy message before exporting.";
      return;
    }

    try {
      await navigator.clipboard.writeText(command);
      copyStatus.textContent = "Copied to clipboard.";
    } catch (error) {
      copyStatus.textContent = "Clipboard access failed. Use “Show config” instead.";
    }
  });

  showButton.addEventListener("click", () => {
    const command = buildCommandFromState();
    if (!command) {
      copyStatus.textContent = "Add at least one strategy message before exporting.";
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
  syncSideButtons();
  resetSlotsFromSelection();
}

function populateMapOptions() {
  mapSelect.innerHTML = "";
  state.maps.forEach((map) => {
    const selected = map.slug === state.selectedMap;
    mapSelect.add(new Option(map.name, map.slug, selected, selected));
  });
}

function syncSideButtons() {
  sideButtons.forEach((button) => {
    const isSelected = button.dataset.side === state.selectedSide;
    button.classList.toggle("is-selected", isSelected);
    button.setAttribute("aria-pressed", String(isSelected));
  });
}

function getRelevantStrategies() {
  return state.strategies.filter(
    (strategy) => strategy.mapSlug === state.selectedMap && strategy.side === state.selectedSide,
  );
}

function createEmptySlot(slotNumber) {
  return {
    slotNumber,
    strategy: null,
    message: "",
    isManualEdit: false,
  };
}

function createSlotFromStrategy(slotNumber, strategy) {
  return {
    slotNumber,
    strategy,
    message: normalizeCommand(strategy.message),
    isManualEdit: false,
  };
}

function resetSlotsFromSelection() {
  const relevantStrategies = getRelevantStrategies();
  state.slots = Array.from({ length: MAX_SLOTS }, (_, index) => {
    const slotNumber = index + 1;
    const strategy = relevantStrategies[index] || null;
    return strategy ? createSlotFromStrategy(slotNumber, strategy) : createEmptySlot(slotNumber);
  });

  renderBindingsEditor();
  copyStatus.textContent = "";
}

function renderBindingsEditor() {
  bindingsEditor.innerHTML = state.slots.map(renderSlotRow).join("");

  bindingsEditor.querySelectorAll("[data-slot-input]").forEach((input) => {
    input.addEventListener("input", () => {
      const slotNumber = Number(input.dataset.slotInput);
      const slot = state.slots[slotNumber - 1];
      slot.message = normalizeCommand(input.value);
      slot.isManualEdit = slot.strategy ? slot.message !== normalizeCommand(slot.strategy.message) : Boolean(slot.message);
      updateSlotStatus(slotNumber);
    });
  });

  bindingsEditor.querySelectorAll("[data-slot-pick]").forEach((button) => {
    button.addEventListener("click", () => openSlotDialog(Number(button.dataset.slotPick)));
  });

  bindingsEditor.querySelectorAll("[data-slot-clear]").forEach((button) => {
    button.addEventListener("click", () => clearSlot(Number(button.dataset.slotClear)));
  });
}

function renderSlotRow(slot) {
  const title = slot.strategy ? slot.strategy.name : `Open slot ${slot.slotNumber}`;
  const description = slot.strategy
    ? slot.strategy.description
    : "Pick any strategy for this map and side, or type a custom team message.";

  return `
    <article class="strategy-row" data-slot-row="${slot.slotNumber}">
      <div class="strategy-slot-column">
        <strong>Numpad ${slot.slotNumber}</strong>
      </div>
      <div class="strategy-main-column">
        <div class="strategy-row-header">
          <div>
            <h3>${escapeHTML(title)}</h3>
            <p>${escapeHTML(description)}</p>
          </div>
        </div>
        <div class="strategy-badges" data-slot-badges="${slot.slotNumber}">${renderSlotBadges(slot)}</div>
        <div class="strategy-controls-row">
          <label class="strategy-message-input">
            <span class="sr-only">Message for numpad ${slot.slotNumber}</span>
            <input
              type="text"
              data-slot-input="${slot.slotNumber}"
              value="${escapeHTML(slot.message)}"
              placeholder="Type the team message only"
            />
          </label>
          <div class="strategy-row-actions">
            <button type="button" class="ghost-button" data-slot-pick="${slot.slotNumber}">Pick strat</button>
            <button type="button" class="ghost-button" data-slot-clear="${slot.slotNumber}">Clear</button>
          </div>
        </div>
      </div>
    </article>
  `;
}

function renderSlotBadges(slot) {
  const statusLabel = getSlotStatusLabel(slot);
  return [
    ...renderMetaBadges(slot.strategy?.meta || {}),
    statusLabel ? renderBadge(statusLabel, "status") : "",
  ].join("");
}

function getSlotStatusLabel(slot) {
  if (slot.isManualEdit) {
    return "Edited";
  }
  if (slot.strategy) {
    return "";
  }
  return slot.message ? "Custom" : "Empty";
}

function updateSlotStatus(slotNumber) {
  const badgeContainer = bindingsEditor.querySelector(`[data-slot-badges="${slotNumber}"]`);
  const slot = state.slots[slotNumber - 1];
  if (badgeContainer) {
    badgeContainer.innerHTML = renderSlotBadges(slot);
  }
}

function renderBadge(label, tone) {
  return `<span class="meta-badge meta-badge-${tone}">${escapeHTML(label)}</span>`;
}

function renderMetaBadges(meta) {
  const hiddenMetaKeys = new Set(["notes"]);
  return Object.entries(meta)
    .filter(([key]) => !hiddenMetaKeys.has(key))
    .map(([key, value]) => renderBadge(`${humanizeKey(key)}: ${formatMetaValue(value)}`, "meta"));
}

function humanizeKey(key) {
  return String(key)
    .replace(/([a-z])([A-Z])/g, "$1 $2")
    .replace(/[_-]+/g, " ")
    .replace(/^./, (char) => char.toUpperCase());
}

function formatMetaValue(value) {
  if (Array.isArray(value)) {
    return value.join(", ");
  }
  if (value && typeof value === "object") {
    return JSON.stringify(value);
  }
  return String(value);
}

function openSlotDialog(slotNumber) {
  const options = getRelevantStrategies();
  slotDialogTitle.textContent = `Pick a strategy for numpad ${slotNumber}`;

  const cards = options.map(
    (strategy, index) => `
      <button type="button" class="slot-option" data-strategy-id="${strategy.id}">
        <div class="slot-option-header">
          <strong>${escapeHTML(strategy.name)}</strong>
          <span>Order ${index + 1}</span>
        </div>
        <span>${escapeHTML(strategy.description)}</span>
        <code>${escapeHTML(strategy.message)}</code>
        <div class="strategy-badges">
          ${[
            renderBadge(strategy.creator, "creator"),
            ...renderMetaBadges(strategy.meta),
          ].join("")}
        </div>
      </button>
    `,
  );

  cards.unshift(`
    <button type="button" class="slot-option clear-option" data-slot-clear-dialog="true">
      <strong>Clear this slot</strong>
      <span>Leave this numpad key empty until you assign another strategy or type a message.</span>
    </button>
  `);

  if (options.length === 0) {
    cards.push(`
      <div class="slot-empty-state">
        No strategies are available for this map and side yet. You can still type a custom message.
      </div>
    `);
  }

  slotDialogOptions.innerHTML = cards.join("");

  slotDialogOptions.querySelectorAll("[data-strategy-id]").forEach((button) => {
    button.addEventListener("click", () => {
      applyStrategyToSlot(slotNumber, Number(button.dataset.strategyId));
      slotDialog.close();
    });
  });

  slotDialogOptions.querySelectorAll("[data-slot-clear-dialog]").forEach((button) => {
    button.addEventListener("click", () => {
      clearSlot(slotNumber);
      slotDialog.close();
    });
  });

  slotDialog.showModal();
}

function applyStrategyToSlot(slotNumber, strategyId) {
  const strategy = getRelevantStrategies().find((entry) => entry.id === strategyId);
  if (!strategy) {
    return;
  }

  state.slots[slotNumber - 1] = createSlotFromStrategy(slotNumber, strategy);
  renderBindingsEditor();
}

function clearSlot(slotNumber) {
  state.slots[slotNumber - 1] = createEmptySlot(slotNumber);
  renderBindingsEditor();
}

function buildCommandFromState() {
  const commands = [];

  state.slots.forEach((slot, index) => {
    const cleanedValue = normalizeCommand(slot.message);
    if (!cleanedValue) {
      return;
    }

    const escapedValue = `${TEAM_CHAT_PREFIX} ${cleanedValue}`.replaceAll('"', "'");
    commands.push(`bind ${NUMPAD_KEYS[index + 1]} "${escapedValue}"`);
  });

  return commands.join("; ");
}

function normalizeCommand(value) {
  return String(value)
    .trim()
    .replace(/^say_team\s+/i, "")
    .replace(/\s+/g, " ");
}

function escapeHTML(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}
