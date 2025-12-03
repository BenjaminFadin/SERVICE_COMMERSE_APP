// Simple interactivity for the static MVP demo.
document.addEventListener("DOMContentLoaded", () => {
  // Toggle filter chips
  document.querySelectorAll(".filter-chip").forEach((chip) => {
    chip.addEventListener("click", () => {
      chip.classList.toggle("active");
    });
  });

  // Slot selection for booking
  document.querySelectorAll(".slot").forEach((slot) => {
    slot.addEventListener("click", () => {
      if (slot.classList.contains("disabled")) return;
      document.querySelectorAll(".slot.active").forEach((s) => s.classList.remove("active"));
      slot.classList.add("active");
      const target = document.querySelector("[data-selected-slot]");
      if (target) {
        target.textContent = slot.textContent.trim();
      }
    });
  });

  // Fake form submission to show toast/cta
  const forms = document.querySelectorAll("[data-demo-form]");
  forms.forEach((form) =>
    form.addEventListener("submit", (e) => {
      e.preventDefault();
      const btn = form.querySelector("button[type='submit']");
      if (btn) {
        btn.disabled = true;
        const initial = btn.innerHTML;
        btn.innerHTML = "Saved ✓";
        setTimeout(() => {
          btn.disabled = false;
          btn.innerHTML = initial;
        }, 1400);
      }
    })
  );
});
