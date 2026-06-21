(function () {
  const storageKey = "gridSentinelTheme";
  const root = document.documentElement;
  const savedTheme = localStorage.getItem(storageKey);
  const systemTheme = window.matchMedia("(prefers-color-scheme: light)").matches ? "light" : "dark";

  function setTheme(theme) {
    const nextTheme = theme === "light" ? "light" : "dark";
    root.dataset.theme = nextTheme;
    localStorage.setItem(storageKey, nextTheme);

    document.querySelectorAll("[data-theme-toggle]").forEach((button) => {
      const label = button.querySelector("[data-theme-label]");
      const icon = button.querySelector(".theme-icon");
      const targetMode = nextTheme === "dark" ? "light" : "dark";
      button.setAttribute("aria-label", `Switch to ${targetMode} mode`);
      if (label) label.textContent = nextTheme === "dark" ? "Dark" : "Light";
      if (icon) icon.textContent = nextTheme === "dark" ? "D" : "L";
    });

    window.dispatchEvent(new CustomEvent("themechange", { detail: { theme: nextTheme } }));
  }

  setTheme(savedTheme || systemTheme);

  document.addEventListener("click", (event) => {
    const button = event.target.closest("[data-theme-toggle]");
    if (!button) return;
    setTheme(root.dataset.theme === "dark" ? "light" : "dark");
  });
})();
