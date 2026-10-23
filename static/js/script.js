document.addEventListener("DOMContentLoaded", () => {
  // Hide messages after 10 seconds
  setTimeout(() => {
    document.querySelectorAll(".alert-dismissible").forEach((a) =>
      bootstrap.Alert.getOrCreateInstance(a).close());
  }, 10000);

  // Stop double clicks: disable the button while a form is working
  document.querySelectorAll("form[data-busy]").forEach((form) => {
    form.addEventListener("submit", () => {
      const btn = form.querySelector("button[type=submit]");
      if (btn) {
        btn.disabled = true;
        btn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Working...';
      }
    });
  });

  // Dashboard charts
  if (window.chartData && document.getElementById("statusChart")) {
    const d = window.chartData;
    new Chart(document.getElementById("statusChart"), {
      type: "doughnut",
      data: { labels: ["Success", "Failed"],
              datasets: [{ data: [d.ok, d.failed], backgroundColor: ["#22c55e", "#ef4444"] }] },
      options: { plugins: { legend: { position: "bottom" } } },
    });
    new Chart(document.getElementById("dayChart"), {
      type: "bar",
      data: { labels: d.days,
              datasets: [{ label: "Backups per day", data: d.counts, backgroundColor: "#0ea5e9" }] },
      options: { scales: { y: { beginAtZero: true, ticks: { precision: 0 } } },
                 plugins: { legend: { display: false } } },
    });
  }
});