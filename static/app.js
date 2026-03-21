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
  activePickerSlot: null,
};

const mapSelect = document.querySelector("#mapSelect");
const bindingsEditor = document.querySelector("#bindingsEditor");
const copyButton = document.querySelector("#copyButton");
const showButton = document.querySelector("#showButton");
const copyStatus = document.querySelector("#copyStatus");
const commandDialog = document.querySelector("#commandDialog");
const dialogTextarea = document.querySelector("#dialogTextarea");
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
    if (typeof commandDialog.showModal === "function") {
      commandDialog.showModal();
      dialogTextarea.focus();
      dialogTextarea.select();
      return;
    }

    copyStatus.textContent = "Dialog is not supported in this browser. Copy from the text that was selected.";
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
  state.activePickerSlot = null;
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
    button.addEventListener("click", () => toggleSlotPicker(Number(button.dataset.slotPick)));
  });

  bindingsEditor.querySelectorAll("[data-slot-clear]").forEach((button) => {
    button.addEventListener("click", () => clearSlot(Number(button.dataset.slotClear)));
  });

  bindingsEditor.querySelectorAll("[data-picker-apply]").forEach((button) => {
    button.addEventListener("click", () => {
      applyStrategyToSlot(Number(button.dataset.slotNumber), Number(button.dataset.pickerApply));
    });
  });

  bindingsEditor.querySelectorAll("[data-picker-close]").forEach((button) => {
    button.addEventListener("click", () => toggleSlotPicker(Number(button.dataset.pickerClose)));
  });

  bindingsEditor.querySelectorAll("[data-picker-clear]").forEach((button) => {
    button.addEventListener("click", () => clearSlot(Number(button.dataset.pickerClear)));
  });
}

function renderSlotRow(slot) {
  const title = slot.strategy ? slot.strategy.name : `Open slot ${slot.slotNumber}`;
  const description = slot.strategy
    ? slot.strategy.description
    : "Pick any strategy for this map and side, or type a custom team message.";
  const isPickerOpen = state.activePickerSlot === slot.slotNumber;

  return `
    <article class="strategy-row" data-slot-row="${slot.slotNumber}">
      <div class="strategy-main-column">
        <div class="strategy-row-header">
          <div class="strategy-title-copy">
            <div class="strategy-title-row">
              <span class="strategy-slot-label">Numpad ${slot.slotNumber}</span>
              <h3>${escapeHTML(title)}</h3>
            </div>
            <p class="strategy-row-description">${escapeHTML(description)}</p>
          </div>
          <div class="strategy-badges strategy-badges-primary">${renderSlotBadges(slot, "primary")}</div>
        </div>
        <div class="strategy-badges strategy-badges-secondary" data-slot-badges="${slot.slotNumber}">${renderSlotBadges(slot, "secondary")}</div>
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
            <button type="button" class="ghost-button" data-slot-pick="${slot.slotNumber}">${isPickerOpen ? "Close picker" : "Pick strat"}</button>
            <button type="button" class="ghost-button" data-slot-clear="${slot.slotNumber}">Clear</button>
          </div>
        </div>
        ${isPickerOpen ? renderInlinePicker(slot.slotNumber) : ""}
      </div>
    </article>
  `;
}

function renderSlotBadges(slot, group) {
  const badges = group === "primary" ? renderPrimaryBadges(slot) : renderSecondaryBadges(slot);
  return badges.join("");
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
    badgeContainer.innerHTML = renderSlotBadges(slot, "secondary");
  }
}

function renderBadge(label, tone) {
  return `<span class="meta-badge meta-badge-${tone}">${escapeHTML(label)}</span>`;
}

function renderPrimaryBadges(slot) {
  const metaEntries = getVisibleMetaEntries(slot.strategy?.meta || {});
  const priorityKeys = ["tags", "difficulty"];
  return priorityKeys
    .filter((key) => key in metaEntries)
    .map((key) => renderBadge(`${humanizeKey(key)}: ${formatMetaValue(metaEntries[key])}`, "meta"));
}

function renderSecondaryBadges(slot) {
  const metaEntries = getVisibleMetaEntries(slot.strategy?.meta || {});
  const secondaryKeys = ["goodWhen", "purpose"];
  const orderedBadges = [
    ...secondaryKeys
      .filter((key) => key in metaEntries)
      .map((key) => renderBadge(`${humanizeKey(key)}: ${formatMetaValue(metaEntries[key])}`, "meta")),
    ...Object.entries(metaEntries)
      .filter(([key]) => !["tags", "difficulty", ...secondaryKeys].includes(key))
      .map(([key, value]) => renderBadge(`${humanizeKey(key)}: ${formatMetaValue(value)}`, "meta")),
  ];

  const statusLabel = getSlotStatusLabel(slot);
  if (statusLabel) {
    orderedBadges.push(renderBadge(statusLabel, "status"));
  }

  return orderedBadges;
}

function getVisibleMetaEntries(meta) {
  const hiddenMetaKeys = new Set(["notes"]);
  return Object.fromEntries(Object.entries(meta).filter(([key]) => !hiddenMetaKeys.has(key)));
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

function toggleSlotPicker(slotNumber) {
  state.activePickerSlot = state.activePickerSlot === slotNumber ? null : slotNumber;
  renderBindingsEditor();
}

function renderInlinePicker(slotNumber) {
  const options = getRelevantStrategies();
  const optionCards = options
    .map(
      (strategy) => `
        <button
          type="button"
          class="slot-option"
          data-slot-number="${slotNumber}"
          data-picker-apply="${strategy.id}"
        >
          <div class="slot-option-header">
            <strong>${escapeHTML(strategy.name)}</strong>
            <span>${escapeHTML(strategy.creator)}</span>
          </div>
          <span>${escapeHTML(strategy.description)}</span>
          <code>${escapeHTML(strategy.message)}</code>
          <div class="strategy-badges">${renderMetaBadges(strategy.meta).join("")}</div>
        </button>
      `,
    )
    .join("");

  const emptyState = options.length
    ? optionCards
    : `
      <div class="slot-empty-state">
        No strats for this map/side.
      </div>
    `;

  return `
    <section class="slot-picker-panel" aria-label="Strategy picker for numpad ${slotNumber}">
      <div class="slot-picker-panel-actions">
        <button type="button" class="ghost-button" data-picker-clear="${slotNumber}">Clear</button>
        <button type="button" class="ghost-button" data-picker-close="${slotNumber}">Close</button>
      </div>
      <div class="slot-dialog-options">
        ${emptyState}
      </div>
    </section>
  `;
}

function renderMetaBadges(meta) {
  return Object.entries(getVisibleMetaEntries(meta || {})).map(([key, value]) =>
    renderBadge(`${humanizeKey(key)}: ${formatMetaValue(value)}`, "meta"),
  );
}

function applyStrategyToSlot(slotNumber, strategyId) {
  const strategy = getRelevantStrategies().find((entry) => entry.id === strategyId);
  if (!strategy) {
    return;
  }

  state.slots[slotNumber - 1] = createSlotFromStrategy(slotNumber, strategy);
  state.activePickerSlot = null;
  renderBindingsEditor();
}

function clearSlot(slotNumber) {
  state.slots[slotNumber - 1] = createEmptySlot(slotNumber);
  if (state.activePickerSlot === slotNumber) {
    state.activePickerSlot = null;
  }
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
