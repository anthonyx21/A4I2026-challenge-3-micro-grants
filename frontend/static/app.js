/**
 * Clean 2-Panel Controller integrated with Cloud Run ADK:
 * https://cascade-analyst-89073885580.us-central1.run.app/
 */

const state = {
  budget: 50000,
  weightingMode: "compound_intensity",
  riskReductionPct: 45,
  equityCarveout: false,
  secondOrderShock: false,
  queueFilter: "ALL",
  selectedBusinessId: "0111663-06-001",
  agentApp: "grant_advisor",
  allocationData: null,
};

document.addEventListener("DOMContentLoaded", async () => {
  bindUIEvents();
  await refreshAllocationAndSelection();
});

function bindUIEvents() {
  document.getElementById("recompute-btn").addEventListener("click", async () => {
    state.budget = parseInt(document.getElementById("budget-input").value || "50000", 10);
    state.equityCarveout = document.getElementById("equity-carveout-toggle").checked;
    await refreshAllocationAndSelection();
  });

  document.getElementById("equity-carveout-toggle").addEventListener("change", async (e) => {
    state.equityCarveout = e.target.checked;
    await refreshAllocationAndSelection();
  });

  const agentSelect = document.getElementById("agent-app-select");
  if (agentSelect) {
    agentSelect.addEventListener("change", (e) => {
      state.agentApp = e.target.value;
    });
  }

  // Queue filter buttons
  document.querySelectorAll(".queue-filter-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      state.queueFilter = btn.dataset.filter;
      document.querySelectorAll(".queue-filter-btn").forEach((b) => {
        b.className =
          b.dataset.filter === state.queueFilter
            ? "queue-filter-btn text-[11px] font-semibold px-2 py-1 rounded bg-slate-900 text-white"
            : "queue-filter-btn text-[11px] font-semibold px-2 py-1 rounded bg-slate-100 text-slate-600 hover:bg-slate-200";
      });
      renderApplicantQueue();
    });
  });

  // Recommended question pills
  document.querySelectorAll(".preset-prompt-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      if (btn.dataset.agent) {
        state.agentApp = btn.dataset.agent;
        const sel = document.getElementById("agent-app-select");
        if (sel) sel.value = state.agentApp;
      }
      sendChatMessage(btn.dataset.prompt);
    });
  });

  // Chat input form
  document.getElementById("chat-form").addEventListener("submit", (e) => {
    e.preventDefault();
    const input = document.getElementById("chat-input");
    const msg = input.value.trim();
    if (!msg) return;
    input.value = "";
    sendChatMessage(msg);
  });
}

async function refreshAllocationAndSelection() {
  const res = await fetch("/api/allocate", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      budget: state.budget,
      weighting_mode: state.weightingMode,
      risk_reduction_pct: state.riskReductionPct,
      equity_carveout: state.equityCarveout,
      second_order_shock: state.secondOrderShock,
    }),
  });
  state.allocationData = await res.json();
  renderTopKPIs();
  renderApplicantQueue();
  selectApplicant(state.selectedBusinessId);
}

window.selectApplicant = function (businessId) {
  state.selectedBusinessId = businessId;
  renderApplicantQueue();

  if (!state.allocationData) return;
  const selected =
    state.allocationData.applicants.find((a) => a.business_id === businessId) ||
    state.allocationData.applicants[0];
  renderSelectedBanner(selected);
};

function renderTopKPIs() {
  const d = state.allocationData;
  if (!d) return;
  document.getElementById("kpi-allocated").textContent = `$${d.total_allocated.toLocaleString()}`;
  document.getElementById("kpi-funded-count").textContent = `${d.funded_count}`;
  document.getElementById("kpi-downstream-reach").textContent = `${d.total_downstream_reached} biz`;
}

function renderApplicantQueue() {
  const container = document.getElementById("applicant-queue-list");
  if (!state.allocationData) return;

  const all = state.allocationData.applicants;
  const filtered = all.filter((a) => {
    if (state.queueFilter === "FUNDED") return a.allocated_amount > 0;
    if (state.queueFilter === "ALERTS")
      return (
        a.decision_category === "SKIPPED_ROBUST_HUB" ||
        a.decision_category === "EQUITY_CARVEOUT_ALERT" ||
        Boolean(a.entity_warning)
      );
    return true;
  });

  container.innerHTML = filtered
    .map((a) => {
      const isSelected = a.business_id === state.selectedBusinessId;
      const isFunded = a.allocated_amount > 0;
      const isSkippedHub = a.decision_category === "SKIPPED_ROBUST_HUB";
      const isBiasLeaf = a.decision_category === "EQUITY_CARVEOUT_ALERT";

      let badgeStyle = "bg-slate-100 text-slate-600";
      if (isFunded) badgeStyle = "bg-emerald-100 text-emerald-800 font-bold";
      else if (isSkippedHub) badgeStyle = "bg-rose-100 text-rose-800 font-bold";
      else if (isBiasLeaf) badgeStyle = "bg-amber-100 text-amber-900 font-bold";

      return `
        <div
          onclick="selectApplicant('${a.business_id}')"
          class="p-3 rounded-xl border transition cursor-pointer ${
            isSelected
              ? "bg-blue-50/90 border-blue-500 ring-1 ring-blue-500"
              : "bg-white hover:bg-slate-50 border-slate-200"
          }"
        >
          <div class="flex items-start justify-between gap-2">
            <div>
              <h3 class="text-xs font-bold text-slate-900">${a.name}</h3>
              <p class="text-[11px] text-slate-500 font-mono">${a.business_id} · NAICS ${a.naics4}</p>
            </div>
            <span class="text-xs font-mono font-bold px-2 py-0.5 rounded ${
              isFunded ? "bg-emerald-600 text-white" : "bg-slate-100 text-slate-700"
            }">
              ${isFunded ? `$${a.allocated_amount.toLocaleString()}` : `$${(a.grant_ask / 1000).toFixed(0)}k`}
            </span>
          </div>

          <div class="mt-2 flex items-center justify-between text-[11px]">
            <span class="text-[10px] px-2 py-0.5 rounded ${badgeStyle}">${a.live_status}</span>
            <span class="font-mono text-slate-600">
              2-Hop: <strong class="text-blue-700">${a.metrics.effective_2hop_reach}</strong> · Gap: <strong>$${(a.cash_gap / 1000).toFixed(0)}k</strong>
            </span>
          </div>
        </div>
      `;
    })
    .join("");
}

function renderSelectedBanner(a) {
  const banner = document.getElementById("selected-applicant-banner");
  const isFunded = a.allocated_amount > 0;

  banner.innerHTML = `
    <div class="flex flex-wrap items-center gap-2">
      <span class="text-slate-400">Selected:</span>
      <span class="font-bold text-white">${a.name}</span>
      <span class="font-mono text-[11px] text-slate-400">(${a.business_id})</span>
      <span class="text-[10px] font-semibold px-2 py-0.5 rounded ${
        isFunded ? "bg-emerald-500 text-slate-950" : "bg-slate-700 text-slate-200"
      }">
        ${isFunded ? `$${a.allocated_amount.toLocaleString()} Funded` : a.live_status}
      </span>
    </div>
  `;
}

async function sendChatMessage(messageText) {
  const chatContainer = document.getElementById("chat-messages");
  const submitBtn = document.getElementById("chat-submit-btn");

  const userBubble = document.createElement("div");
  userBubble.className = "bg-blue-600 text-white rounded-xl p-3 ml-12 text-xs shadow-2xs";
  userBubble.innerHTML = `<p class="font-semibold mb-0.5 text-[10px] text-blue-200">Grant Officer → ${escapeHtml(
    state.agentApp
  )}</p><p>${escapeHtml(messageText)}</p>`;
  chatContainer.appendChild(userBubble);

  // Loading indicator while Cloud Run executes BigQuery GQL & Gemini tools
  const loadingBubble = document.createElement("div");
  loadingBubble.className =
    "bg-slate-100 border border-slate-200 rounded-xl p-3.5 mr-8 text-xs text-slate-600 flex items-center gap-2 animate-pulse";
  loadingBubble.innerHTML = `
    <span class="inline-block w-2 h-2 rounded-full bg-blue-600"></span>
    <span>Querying live Cloud Run agent (<code>${escapeHtml(
      state.agentApp
    )}</code>) &amp; BigQuery property graph...</span>
  `;
  chatContainer.appendChild(loadingBubble);
  chatContainer.scrollTop = chatContainer.scrollHeight;
  if (submitBtn) submitBtn.disabled = true;

  try {
    const res = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        message: messageText,
        selected_business_id: state.selectedBusinessId,
        budget: state.budget,
        risk_reduction_pct: state.riskReductionPct,
        weighting_mode: state.weightingMode,
        equity_carveout: state.equityCarveout,
        agent_app: state.agentApp,
      }),
    });
    const data = await res.json();
    loadingBubble.remove();

    const botBubble = document.createElement("div");
    botBubble.className =
      "bg-slate-100 border border-slate-200 rounded-xl p-3.5 mr-8 text-xs text-slate-800 space-y-1.5";
    const formattedReply = formatMarkdown(data.reply);

    botBubble.innerHTML = `
      <div class="flex items-center justify-between text-[10px] font-mono text-emerald-700 font-semibold">
        <span>🤖 ${escapeHtml(data.source)}</span>
      </div>
      <div class="leading-relaxed space-y-1.5">${formattedReply}</div>
    `;
    chatContainer.appendChild(botBubble);
    chatContainer.scrollTop = chatContainer.scrollHeight;
  } catch (err) {
    loadingBubble.remove();
    const errBubble = document.createElement("div");
    errBubble.className = "bg-rose-50 border border-rose-200 rounded-xl p-3 mr-8 text-xs text-rose-800";
    errBubble.textContent = `Error communicating with agent: ${err.message}`;
    chatContainer.appendChild(errBubble);
  } finally {
    if (submitBtn) submitBtn.disabled = false;
  }
}

function formatMarkdown(md) {
  return md
    .replace(/```(?:sql|json)?([\s\S]*?)```/g, '<pre class="bg-slate-900 text-emerald-300 font-mono text-[11px] p-2.5 rounded-lg my-2 overflow-x-auto">$1</pre>')
    .replace(/^# (.*$)/gm, '<div class="font-bold text-slate-900 text-sm border-b border-slate-300 pb-1 mb-1">$1</div>')
    .replace(/^## (.*$)/gm, '<div class="font-bold text-slate-900 text-xs mt-2.5 mb-1">$1</div>')
    .replace(/^### (.*$)/gm, '<div class="font-bold text-slate-900 text-xs mt-2 mb-1">$1</div>')
    .replace(/^---$/gm, '<hr class="my-2 border-slate-300" />')
    .replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>")
    .replace(/\*(.*?)\*/g, "<em>$1</em>")
    .replace(/`([^`]+)`/g, '<code class="font-mono text-[11px] bg-white px-1 py-0.5 rounded border border-slate-200">$1</code>')
    .replace(/^\*   (.*$)/gm, '<div class="pl-2.5 border-l-2 border-blue-400 my-1">$1</div>')
    .replace(/^- (.*$)/gm, '<div class="pl-2.5 border-l-2 border-blue-400 my-1">$1</div>')
    .replace(/^  - (.*$)/gm, '<div class="pl-5 text-slate-700 my-0.5">• $1</div>');
}

function escapeHtml(str) {
  return str.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}
