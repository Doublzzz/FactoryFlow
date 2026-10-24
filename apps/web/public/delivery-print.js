/* Trusted presentation code. No business writes or automatic printing. */
(() => {
  "use strict";
  const text = (chinese, english) => document.documentElement.lang === "en" ? english : chinese;
  const pages = document.getElementById("pages");
  const source = document.getElementById("source");
  const button = document.getElementById("print-button");
  const problem = document.getElementById("problem");
  const status = document.getElementById("print-status");
  const direction = document.getElementById("print-direction");
  const directionStyle = document.getElementById("print-direction-style");
  const directionHint = document.getElementById("print-direction-hint");
  const templateHint = directionHint?.textContent;
  const maxRows = Number(document.body.dataset.rowsPerPage);
  let ready = false;
  let blocked = true;
  let error = "";
  const sheets = () => [...pages.querySelectorAll(".sheet")];
  function scalePreview() {
    const available = Math.max(1, document.documentElement.clientWidth - 24);
    for (const paper of pages.querySelectorAll(".print-paper")) {
      // offset/client/scroll dimensions retain the untransformed millimetre geometry.
      const scale = Math.min(1, available / paper.offsetWidth);
      paper.style.transform = `scale(${scale})`;
      paper.parentElement.style.width = `${paper.offsetWidth * scale}px`;
      paper.parentElement.style.height = `${paper.offsetHeight * scale}px`;
    }
  }
  const overflow = (sheet) => {
    const content = sheet.querySelector(".paper-content");
    return content.scrollHeight > content.clientHeight + 1 ||
      content.scrollWidth > content.clientWidth + 1;
  };
  function page() {
    const sheet = document.createElement("section");
    sheet.className = "sheet";
    const content = document.createElement("div");
    content.className = "paper-content";
    content.append(source.querySelector(".heading").cloneNode(true));
    const table = source.querySelector("table").cloneNode(true);
    table.querySelector("tbody").replaceChildren();
    content.append(table, source.querySelector(".signatures").cloneNode(true),
      source.querySelector(".document-footer").cloneNode(true));
    sheet.append(content);
    const frame = document.createElement("div");
    frame.className = "page-frame";
    const paper = document.createElement("div");
    paper.className = "print-paper";
    paper.append(sheet);
    frame.append(paper);
    pages.append(frame);
    return sheet;
  }
  function report() {
    document.body.dataset.blocked = String(blocked);
    button.disabled = blocked || !ready;
    problem.textContent = error;
    status.textContent = blocked ? text("内容未能完整排入纸张，已阻止打印。", "Content does not fit the paper. Printing is blocked.") : text(`已排为 ${pages.children.length} 页`, `Pages ready: ${pages.children.length}`);
    if (window.parent !== window) window.parent.postMessage({
      type: "delivery-print-ready", pages: pages.children.length, blocked
    }, "*");
  }
  function check() {
    if (sheets().some(overflow)) {
      blocked = true;
      if (!error) error = text("纸张内容溢出。请调整纸张、边距、字号、列宽或行高后重新预览。", "Content overflows. Adjust the paper, margins, font, column widths or row height, then preview again.");
    }
    report();
    return ready && !blocked;
  }
  function paginate() {
    pages.replaceChildren();
    blocked = false;
    error = "";
    const rows = [...source.querySelectorAll("tbody tr")];
    let sheet = page();
    if (overflow(sheet)) {
      blocked = true;
      error = text("抬头、单据信息或签收区超过可用纸张，请调整布局。", "The heading, document details or signature area exceed the available paper. Adjust the layout.");
    }
    let count = 0;
    for (const original of rows) {
      if (blocked) break;
      if (count === maxRows) { sheet = page(); count = 0; }
      let body = sheet.querySelector("tbody");
      const row = original.cloneNode(true);
      body.append(row);
      if (overflow(sheet)) {
        row.remove();
        if (count > 0) { sheet = page(); count = 0; body = sheet.querySelector("tbody"); }
        body.append(row);
        if (overflow(sheet)) {
          blocked = true;
          sheet.classList.add("blocked");
          error = text("单行内容无法完整排入一页。请增大纸张或调整列宽、字号；业务送货单不会自动拆分。", "A single row cannot fit on one page. Use larger paper or adjust column widths and font size. This does not split the delivery record.");
          break;
        }
      }
      count++;
    }
    // Only add blank rows where they fit; never conceal actual text.
    if (!blocked) for (const current of sheets()) {
      const body = current.querySelector("tbody");
      while (body.children.length < maxRows) {
        const blank = document.createElement("tr");
        blank.className = "padding-row";
        for (let i = 0; i < 7; i++) blank.append(document.createElement("td"));
        body.append(blank);
        if (overflow(current)) { blank.remove(); break; }
      }
    }
    for (const [index, current] of sheets().entries()) {
      current.querySelector(".page-number").textContent = String(index + 1);
      current.querySelector(".page-total").textContent = String(pages.children.length);
    }
    ready = true;
    check();
    scalePreview();
  }
  function print() { if (check()) window.print(); }
  direction?.addEventListener("change", () => {
    const a4 = direction.value === "a4_upper_half";
    const originalWidth = Number(document.body.dataset.paperWidth);
    const originalHeight = Number(document.body.dataset.paperHeight);
    // Keep the delivery's geometry and pagination. Fit its whole sheet into
    // the upper half of portrait A4, with 5 mm clearance on every edge.
    const scale = Math.min(1, 200 / originalWidth, 138.5 / originalHeight);
    const left = (210 - originalWidth * scale) / 2;
    directionStyle.textContent = a4 ? `
      @page { size: 210mm 297mm; margin: 0; }
      .print-paper { width: 210mm; height: 297mm; }
      .sheet { position: absolute; top: 5mm; left: ${left}mm; transform: scale(${scale}); }
    ` : "";
    directionHint.textContent = a4
      ? text(`A4 竖版 210 × 297 mm：每张上半部放一页送货单，下半部留空。单据等比缩放为 ${(scale * 100).toFixed(1)}%。`, `A4 portrait 210 × 297 mm: one note on the upper half, lower half blank. Proportional scale: ${(scale * 100).toFixed(1)}%.`)
      : templateHint;
    if (ready) { check(); scalePreview(); }
  });
  button.addEventListener("click", print);
  window.addEventListener("message", (event) => {
    if (event.source === window.parent && event.data?.type === "delivery-print") print();
  });
  window.addEventListener("beforeprint", check);
  window.addEventListener("afterprint", scalePreview);
  window.addEventListener("resize", () => { if (ready) { check(); scalePreview(); } });
  (async () => {
    try {
      await document.fonts.ready;
      await new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)));
      paginate();
    } catch {
      blocked = true;
      error = text("分页失败，已阻止打印。请重新打开预览。", "Page layout failed. Printing is blocked. Reopen the preview.");
      report();
    }
  })();
})();
