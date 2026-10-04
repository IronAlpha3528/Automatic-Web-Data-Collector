// Live job monitoring script
function initJobMonitor(jobId) {
  const progressBar = document.getElementById("progress-fill");
  const progressText = document.getElementById("progress-text");
  const statusBadge = document.getElementById("status-badge");
  const totalUrls = document.getElementById("total-urls");
  const processedUrls = document.getElementById("processed-urls");
  const successfulUrls = document.getElementById("successful-urls");
  const failedUrls = document.getElementById("failed-urls");

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
      statusBadge.innerText = data.status;
      statusBadge.className = `badge badge-${data.status.toLowerCase().replace('_', '-')}`;

      // Check if finished
      if (["COMPLETED", "COMPLETED_WITH_ERRORS", "FAILED"].includes(data.status)) {
        document.getElementById("action-buttons").style.display = "flex";
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
