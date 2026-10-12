/* Reader tabs, same pattern as the /space explorer tabs (buttons with aria-pressed).
   Panels are hidden, not removed: other scripts keep filling them in the background,
   and the evidence panel beside the tabs stays visible for every tab. */
(() => {
  const buttons = [...document.querySelectorAll('.reader-tabs [data-tab]')];
  const panels = [...document.querySelectorAll('.tab-panel[data-panel]')];
  function activate(name) {
    if (!panels.some(panel => panel.dataset.panel === name)) return;
    for (const button of buttons) button.setAttribute('aria-pressed', String(button.dataset.tab === name));
    for (const panel of panels) panel.hidden = panel.dataset.panel !== name;
  }
  for (const button of buttons) button.addEventListener('click', () => activate(button.dataset.tab));
  // "Bổ sung cho câu hỏi này" trên bản đồ: chuyển sang tab Bổ sung trước khi form được điền và cuộn tới.
  document.addEventListener('knowledge-question-selected', () => activate('feedback'));
  window.readerTabs = {activate};
})();
