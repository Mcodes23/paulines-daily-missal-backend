// Real working tabs for Missal Admin
document.addEventListener("DOMContentLoaded", () => {
  const form = document.querySelector("#liturgicalday_form");
  if (!form) return;

  // Create tabs header
  const tabBar = document.createElement("div");
  tabBar.id = "missal-tabs";
  tabBar.innerHTML = `
    <button data-tab="details" class="active">🕊️ Day Details</button>
    <button data-tab="reading1">📖 First Reading</button>
    <button data-tab="reading2">📖 Second Reading</button>
    <button data-tab="psalm">🎵 Psalm</button>
    <button data-tab="accl">🎺 Gospel Acclamation</button>
    <button data-tab="gospel">✝️ Gospel</button>
    <button data-tab="prayers">🙏 Prayers</button>
  `;

  form.prepend(tabBar);

  const allInlines = Array.from(document.querySelectorAll(".inline-group"));
  const sections = {
    details: form.querySelector("fieldset.module"),
    reading1: allInlines.find(el => el.id.includes("reading")),
    reading2: allInlines.find(el => el.id.includes("secondreading")),
    psalm: allInlines.find(el => el.id.includes("responsorialpsalm")),
    accl: allInlines.find(el => el.id.includes("gospelacclamation")),
    gospel: allInlines.find(el => el.id.includes("gospel") && !el.id.includes("acclamation")),
    prayers: allInlines.find(el => el.id.includes("specialsections")),
  };

  // Wrap them in <div class="tab-section">
  Object.entries(sections).forEach(([key, el]) => {
    if (el) {
      const wrapper = document.createElement("div");
      wrapper.className = "tab-section";
      wrapper.dataset.tab = key;
      el.parentNode.insertBefore(wrapper, el);
      wrapper.appendChild(el);
      if (key === "details") wrapper.classList.add("active");
    }
  });

  // Activate tab click
  document.querySelectorAll("#missal-tabs button").forEach(btn => {
    btn.addEventListener("click", () => {
      document.querySelectorAll("#missal-tabs button").forEach(b => b.classList.remove("active"));
      document.querySelectorAll(".tab-section").forEach(sec => sec.classList.remove("active"));
      btn.classList.add("active");
      const activeTab = btn.dataset.tab;
      const section = document.querySelector(`.tab-section[data-tab="${activeTab}"]`);
      if (section) section.classList.add("active");
      window.scrollTo({ top: 0, behavior: "smooth" });
    });
  });
});
