/* Explicit print action only; no business commands or automatic printing. */
document.getElementById("print-purchase")?.addEventListener("click", async () => {
  await document.fonts.ready;
  window.print();
});
