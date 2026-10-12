// Live job monitoring script with real-time speed calculation and telemetry stream
function initJobMonitor(jobId) {
  const progressBar = document.getElementById("progress-fill");
  const progressText = document.getElementById("progress-text");
  const speedText = document.getElementById("speed-text");
  const statusBadge = document.getElementById("status-badge");
  const statusText = document.getElementById("status-text");
  const totalUrls = document.getElementById("total-urls");
  const processedUrls = document.getElementById("processed-urls");
  const successfulUrls = document.getElementById("successful-urls");
  const failedUrls = document.getElementById("failed-urls");
  const stopButton = document.getElementById("btn-stop-job");
  const errorsContainer = document.getElementById("live-errors-container");
  const errorsList = document.getElementById("live-errors-list");

  let startTime = null;
  let lastProcessed = 0;

  if (stopButton) {
    stopButton.addEventListener("click", async () => {
      if (!confirm("Are you sure you want to stop this ongoing crawl? In-flight requests will be safely isolated.")) {
        return;
      }
      stopButton.disabled = true;
      stopButton.innerHTML = `<svg class="spin" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 12a9 9 0 1 1-6.219-8.56"/></svg> Stopping...`;
      try {
        const res = await fetch(`/api/jobs/${jobId}/cancel`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
        });
        if (res.ok) {
          const data = await res.json();
          updateStatus(data.status);
          stopButton.style.display = "none";
          if (typeof showToast === "function") showToast("Crawl job stopped by user request.");
        } else {
          alert("Failed to stop job: Server returned an error.");
          stopButton.disabled = false;
          stopButton.innerHTML = `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect width="18" height="18" x="3" y="3" rx="2"/></svg> Stop Crawling`;
        }
      } catch (err) {
        console.error("Error stopping job:", err);
        alert("Network error stopping job.");
        stopButton.disabled = false;
        stopButton.innerHTML = `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect width="18" height="18" x="3" y="3" rx="2"/></svg> Stop Crawling`;
      }
    });
  }

  function updateStatus(status) {
    statusBadge.className = `badge badge-${status.toLowerCase().replace('_', '-')}`;
    const isRunning = status === "RUNNING";
    statusBadge.innerHTML = `<span class="beacon ${isRunning ? 'beacon-pulse' : ''}"></span> <span id="status-text">${status.replace('_', ' ')}</span>`;
  }

  async function checkErrors() {
    try {
      const res = await fetch(`/api/jobs/${jobId}/errors`);
      if (res.ok) {
        const data = await res.json();
        if (data.errors && data.errors.length > 0) {
          errorsContainer.style.display = "block";
          errorsList.innerHTML = data.errors.slice(0, 3).map(e => `
            <div style="display: flex; gap: 0.5rem; align-items: baseline;">
              <span class="badge badge-failed" style="padding: 0.1rem 0.35rem; font-size: 0.6875rem;">${e.error_type}</span>
              <span style="overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">${e.message}</span>
            </div>
          `).join('');
        }
      }
    } catch (err) {
      // ignore error polling failure
    }
  }

  async function poll() {
    try {
      const res = await fetch(`/api/jobs/${jobId}`);
      if (!res.ok) return;

      const data = await res.json();

      // Update counters
      totalUrls.innerText = data.total_urls;
      processedUrls.innerText = data.processed_urls;
      successfulUrls.innerText = data.successful_urls;
      failedUrls.innerText = data.failed_urls;

      // Update speed calculation
      if (data.started_at && !startTime) {
        startTime = new Date(data.started_at).getTime();
      }
      if (startTime && data.status === "RUNNING") {
        const elapsedSec = (Date.now() - startTime) / 1000;
        if (elapsedSec > 1) {
          const speed = (data.processed_urls / elapsedSec).toFixed(1);
          if (speedText) speedText.innerText = `${speed} URLs/s`;
        }
      } else if (data.status === "COMPLETED") {
        if (speedText) speedText.innerText = `Finished`;
      }

      // Update progress bar
      let pct = 0;
      if (data.total_urls > 0) {
        pct = Math.min(100, Math.round((data.processed_urls / data.total_urls) * 100));
      } else if (data.status === "COMPLETED") {
        pct = 100;
      }
      progressBar.style.width = `${pct}%`;
      progressText.innerText = `${pct}%`;

      // Update status badge
      updateStatus(data.status);

      // Check errors if any failed
      if (data.failed_urls > 0) {
        checkErrors();
      }

      // Update Stop button visibility
      if (stopButton) {
        if (["RUNNING", "CREATED"].includes(data.status)) {
          stopButton.style.display = "inline-flex";
        } else {
          stopButton.style.display = "none";
        }
      }

      // Check if finished
      if (["COMPLETED", "COMPLETED_WITH_ERRORS", "FAILED"].includes(data.status)) {
        if (data.status === "COMPLETED") {
          progressBar.style.width = "100%";
          progressText.innerText = "100%";
        }
        return; // stop polling
      }

      setTimeout(poll, 1500);
    } catch (err) {
      console.error("Error polling job status:", err);
      setTimeout(poll, 3000);
    }
  }

  poll();
}
