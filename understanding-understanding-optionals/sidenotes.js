// A simplified, modern approach that places all footnotes in a right-side column,
// preserving order and preventing overlap. This script expects Pandoc footnotes with:
//   (1) each footnote reference <a class="footnote-ref" href="#fnN"> in the text,
//   (2) a corresponding footnote <li id="fnN"> at the bottom.

(function () {
  // Debounce utility to avoid thrashing on resize.
  function debounce(fn, delay) {
    let timer = null;
    return (...args) => {
      clearTimeout(timer);
      timer = setTimeout(() => fn(...args), delay);
    };
  }

  let sidenoteContainer = null;
  let sidenoteElements = [];
  let footnoteRefs = [];

  // Main initialization
  function initSidenotes() {
    // Get references to each footnote.
    footnoteRefs = Array.from(document.querySelectorAll("a.footnote-ref"));
    if (footnoteRefs.length === 0) {
      return; // No footnotes found.
    }

    // Create a container for all sidenotes.
    sidenoteContainer = document.createElement("div");
    sidenoteContainer.id = "sidenote-container";
    // Absolutely positioned to the right of main content.
    // You can adjust the width/top/right for your layout.
    sidenoteContainer.style.position = "absolute";
    sidenoteContainer.style.top = "0";
    sidenoteContainer.style.width = "18em";
    // We'll place it once we know where main content ends.

    // Insert into DOM.
    document.body.appendChild(sidenoteContainer);

    // Build each sidenote and store references.
    footnoteRefs.forEach((ref, index) => {
      // The footnote ID is in the href, e.g. #fn1.
      const footnoteID = ref.getAttribute("href").slice(1); // remove '#'.
      const footnoteLi = document.getElementById(footnoteID);
      if (!footnoteLi) return;

      // Create a copy of footnote content.
      const sidenote = document.createElement("div");
      sidenote.classList.add("sidenote");
      sidenote.style.position = "absolute";
      sidenote.innerHTML = footnoteLi.innerHTML; // clone the inner HTML.

      // Optional: add a small heading or link back:
      // sidenote.insertAdjacentHTML(
      //   'afterbegin',
      //   `<div class="sidenote-index">[${index + 1}]</div>`
      // );

      // Append to container.
      sidenoteContainer.appendChild(sidenote);
      sidenoteElements.push(sidenote);
    });

    // Position them initially.
    positionSidenotes();

    // Reposition on window resize.
    window.addEventListener("resize", debounce(positionSidenotes, 200));
  }

  // Recompute positions of the sidenotes in the right column.
  function positionSidenotes() {
    if (!sidenoteContainer || footnoteRefs.length === 0) return;

    // Decide where to place the container horizontally.
    // For example, to the right of #markdownBody or #content.
    // If you don't have a main container, just fix it or place it on the right.
    const main = document.getElementById("markdownBody") || document.body;
    const mainRect = main.getBoundingClientRect();

    // We place the sidenote container at the right side of main.
    // You can tweak this offset.
    sidenoteContainer.style.left = (window.scrollX + mainRect.right + 40) + "px";

    // For vertical offset, we top-align with the top of main content.
    // You can tweak this offset or fix it at 0.
    const containerTop = window.scrollY + mainRect.top;
    sidenoteContainer.style.top = containerTop + "px";

    let currentBottom = 0; // track the bottom of the last placed sidenote.

    sidenoteElements.forEach((note, idx) => {
      // Each corresponding reference.
      const ref = footnoteRefs[idx];
      const refRect = ref.getBoundingClientRect();
      const desiredTop = window.scrollY + refRect.top; // absolute top of the reference.

      // Convert desiredTop into local coords of container.
      const localTop = desiredTop - containerTop;

      // If it would collide with the previous note, shift it down a bit.
      const minTop = currentBottom + 10; // 10px gap.
      const finalTop = Math.max(localTop, minTop);

      note.style.top = finalTop + "px";
      note.style.left = "0"; // keep everything in one column.

      // Force layout so we can measure note height.
      const noteHeight = note.offsetHeight;
      currentBottom = finalTop + noteHeight;
    });
  }

  // Run on DOMContentLoaded.
  document.addEventListener("DOMContentLoaded", initSidenotes);
})();
