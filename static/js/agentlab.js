(function () {
  window.hideWorkingOverlay = function() {
    var overlay = document.getElementById("agent-working");
    if (overlay) {
      overlay.hidden = true;
      overlay.style.display = "none";
    }
  };

  function showWorking() {
    var overlay = document.getElementById("agent-working");
    if (!overlay) {
      return;
    }
    overlay.hidden = false;
    overlay.style.display = "grid";
    overlay.setAttribute("aria-busy", "true");
  }

  document.addEventListener("keydown", function (event) {
    var target = event.target;
    if (!target || !target.classList || !target.classList.contains("js-prompt")) {
      return;
    }
    if (event.key !== "Enter" || event.shiftKey) {
      return;
    }
    event.preventDefault();
    var form = target.form || target.closest("form");
    if (form) {
      if (typeof form.requestSubmit === "function") {
        form.requestSubmit();
      } else {
        form.submit();
      }
    }
  });

  document.addEventListener("submit", function (event) {
    var form = event.target;
    if (!form || !form.classList.contains("js-agent-form")) {
      return;
    }
    showWorking();
    var button = form.querySelector("[type=submit]");
    if (button) {
      button.disabled = true;
      button.textContent = "Working…";
    }
  });

  // Global PivotMind Chat Assistant Helper
  window.sendPivotMindChat = function(chatUrl, formId) {
    const form = document.getElementById(formId);
    if (!form) return;
    const input = form.querySelector("input[name='question']");
    const container = document.getElementById("chat-messages");
    if (!input || !container) return;

    const question = input.value.trim();
    if (!question) return;

    // Construct FormData BEFORE clearing input field!
    const formData = new FormData(form);
    formData.set("question", question);

    // Append User Message
    const userDiv = document.createElement("div");
    userDiv.className = "chat-msg user";
    userDiv.textContent = question;
    container.appendChild(userDiv);
    input.value = "";

    // Append Loading Assistant Message
    const loadDiv = document.createElement("div");
    loadDiv.className = "chat-msg assistant";
    loadDiv.innerHTML = "<em>Analyzing dataset and computing metrics...</em>";
    container.appendChild(loadDiv);
    container.scrollTop = container.scrollHeight;

    fetch(chatUrl, {
      method: "POST",
      body: formData,
    })
    .then(res => res.json())
    .then(data => {
      if (data.error) {
        loadDiv.innerHTML = `<span style="color: var(--danger);">Error: ${data.error}</span>`;
      } else {
        let html = data.answer_html || data.answer || "No response.";
        loadDiv.innerHTML = html;

        // Render Plotly Chart directly if fig_json is provided
        const figJson = data.fig_json || (data.chart_report && data.chart_report.fig_json);
        const vizHtml = data.viz_html || (data.chart_report && data.chart_report.fig_html);

        if (figJson && typeof Plotly !== "undefined") {
          const chartWrapper = document.createElement("div");
          chartWrapper.style.marginTop = "1rem";
          chartWrapper.style.paddingTop = "0.8rem";
          chartWrapper.style.borderTop = "1px solid var(--line)";
          
          const divId = "chat-chart-" + Date.now() + "-" + Math.floor(Math.random() * 1000);
          const chartDiv = document.createElement("div");
          chartDiv.id = divId;
          chartDiv.style.minHeight = "360px";
          chartDiv.style.width = "100%";
          chartDiv.style.borderRadius = "8px";
          chartDiv.style.background = "#0d1526";
          
          chartWrapper.appendChild(chartDiv);
          loadDiv.appendChild(chartWrapper);

          try {
            const parsedFig = typeof figJson === "string" ? JSON.parse(figJson) : figJson;
            Plotly.newPlot(divId, parsedFig.data, parsedFig.layout || {}, { responsive: true });
          } catch(err) {
            console.error("Plotly rendering error:", err);
          }
        } else if (vizHtml) {
          const chartWrapper = document.createElement("div");
          chartWrapper.style.marginTop = "1rem";
          chartWrapper.style.paddingTop = "0.8rem";
          chartWrapper.style.borderTop = "1px solid var(--line)";
          chartWrapper.innerHTML = vizHtml;
          loadDiv.appendChild(chartWrapper);

          // Execute script tags inside vizHtml manually since innerHTML ignores script execution
          const scripts = chartWrapper.querySelectorAll("script");
          scripts.forEach(s => {
            const newScript = document.createElement("script");
            newScript.textContent = s.textContent;
            document.body.appendChild(newScript).parentNode.removeChild(newScript);
          });
        }
      }
      container.scrollTop = container.scrollHeight;
    })
    .catch(err => {
      console.error(err);
      loadDiv.innerHTML = `<span style="color: var(--danger);">Connection error. Please try again.</span>`;
    });
  };
})();
