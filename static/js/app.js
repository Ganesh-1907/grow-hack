const form = document.getElementById("analyze-form");
const button = document.getElementById("analyze-button");
const errorMessage = document.getElementById("error-message");
const progressSection = document.getElementById("progress-section");
const summaryCard = document.getElementById("summary-card");
const summaryContent = document.getElementById("summary-content");
const resultsSection = document.getElementById("results-section");
const preview = document.getElementById("markdown-preview");
const downloadMarkdown = document.getElementById("download-markdown");
const downloadPdf = document.getElementById("download-pdf");
const steps = [...document.querySelectorAll(".step")];

const tabRepo = document.getElementById("tab-repo");
const tabContent = document.getElementById("tab-content");
const repoPanel = document.getElementById("repo-panel");
const contentPanel = document.getElementById("content-panel");
const tabSliderTrack = document.getElementById("tab-slider-track");

const themeToggle = document.getElementById("theme-toggle");
const sunIcon = document.getElementById("sun-icon");
const moonIcon = document.getElementById("moon-icon");
const THEME_KEY = "ghai_theme";

const profileModal = document.getElementById("profile-modal");
const profileForm = document.getElementById("profile-form");
const profileError = document.getElementById("profile-error");
const greeting = document.getElementById("greeting");
const editProfileBtn = document.getElementById("edit-profile-btn");
const PROFILE_KEY = "ghai_profile";

// --- Theme Switching Logic ---
function initTheme() {
  const savedTheme = localStorage.getItem(THEME_KEY) || "dark";
  setTheme(savedTheme);
}

function setTheme(theme) {
  if (theme === "light") {
    document.documentElement.classList.add("light");
    sunIcon.classList.add("hidden");
    moonIcon.classList.remove("hidden");
    localStorage.setItem(THEME_KEY, "light");
  } else {
    document.documentElement.classList.remove("light");
    sunIcon.classList.remove("hidden");
    moonIcon.classList.add("hidden");
    localStorage.setItem(THEME_KEY, "dark");
  }
}

if (themeToggle) {
  themeToggle.addEventListener("click", () => {
    const isLight = document.documentElement.classList.contains("light");
    setTheme(isLight ? "dark" : "light");
  });
}

// Initialize theme
initTheme();

// --- Profile Modal Logic ---
function getProfile() {
  try {
    return JSON.parse(localStorage.getItem(PROFILE_KEY)) || null;
  } catch {
    return null;
  }
}

function saveProfile(name, email) {
  localStorage.setItem(PROFILE_KEY, JSON.stringify({ name, email }));
}

function showGreeting(profile) {
  const first = (profile.name || "").trim().split(/\s+/)[0] || "friend";
  greeting.textContent = `Welcome back, ${first}!`;
  greeting.classList.remove("hidden");
  if (editProfileBtn) editProfileBtn.classList.remove("hidden");
}

function openProfileModal(prefill) {
  if (profileError) profileError.classList.add("hidden");
  if (prefill) {
    document.getElementById("profile-name").value = prefill.name || "";
    document.getElementById("profile-email").value = prefill.email || "";
  } else {
    document.getElementById("profile-name").value = "";
    document.getElementById("profile-email").value = "";
  }
  if (profileModal) profileModal.classList.remove("hidden");
}

(function initProfile() {
  const profile = getProfile();
  if (profile && profile.name && profile.email) {
    showGreeting(profile);
    return;
  }
  openProfileModal(null);
})();

if (editProfileBtn) {
  editProfileBtn.addEventListener("click", () => openProfileModal(getProfile()));
}

if (profileForm) {
  profileForm.addEventListener("submit", (event) => {
    event.preventDefault();
    const name = document.getElementById("profile-name").value.trim();
    const email = document.getElementById("profile-email").value.trim();
    if (!name || !email || !email.includes("@")) {
      profileError.textContent = "Please enter your name and a valid email.";
      profileError.classList.remove("hidden");
      return;
    }
    saveProfile(name, email);
    profileModal.classList.add("hidden");
    showGreeting({ name, email });
  });
}

// --- Sliding Tab Switching Logic ---
function switchTab(activeTab) {
  const showRepo = activeTab === "repo";
  tabRepo.classList.toggle("active", showRepo);
  tabContent.classList.toggle("active", !showRepo);
  
  if (tabSliderTrack) {
    tabSliderTrack.style.transform = showRepo ? "translateX(0%)" : "translateX(-50%)";
  }

  if (showRepo) {
    // Hide content creator results
    if (contentResults) contentResults.classList.add("hidden");
    
    // Restore repository documentation results if they exist
    if (preview && preview.innerHTML.trim() !== "") {
      if (resultsSection) resultsSection.classList.remove("hidden");
    }
    if (summaryContent && summaryContent.innerHTML.trim() !== "") {
      if (summaryCard) summaryCard.classList.remove("hidden");
    }
  } else {
    // Hide repository documentation results & progress
    if (resultsSection) resultsSection.classList.add("hidden");
    if (summaryCard) summaryCard.classList.add("hidden");
    if (progressSection) progressSection.classList.add("hidden");
    
    // Restore content creator results if they exist
    if (contentPreview && contentPreview.innerHTML.trim() !== "") {
      if (contentResults) contentResults.classList.remove("hidden");
    }
  }
}

if (tabRepo) {
  tabRepo.addEventListener("click", () => switchTab("repo"));
}
if (tabContent) {
  tabContent.addEventListener("click", () => switchTab("content"));
}

// --- Form & Submit Handling ---
if (form) {
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const url = document.getElementById("repo-url").value.trim();
    if (!url) return;

    resetUI();
    button.disabled = true;
    button.textContent = "Analyzing...";

    try {
      activateStep(0);
      const response = await fetch("/analyze", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ repo_url: url }),
      });

      const data = await response.json();
      if (!response.ok) {
        throw new Error(data.error || "Analysis failed.");
      }

      activateStep(1);
      renderSummary(data.summary);
      activateStep(2);
      preview.innerHTML = marked.parse(data.documentation || "");
      activateStep(3);

      resultsSection.classList.remove("hidden");
      setupDownload(downloadMarkdown, "/download/markdown", data.markdown);
      setupDownload(downloadPdf, "/download/pdf", data.pdf);

      if (data.pdf) {
        downloadPdf.disabled = false;
      }
    } catch (error) {
      showError(error.message);
    } finally {
      button.disabled = false;
      button.textContent = "Analyze Repository";
    }
  });
}

function resetUI() {
  errorMessage.classList.add("hidden");
  errorMessage.textContent = "";
  progressSection.classList.remove("hidden");
  summaryCard.classList.add("hidden");
  resultsSection.classList.add("hidden");
  preview.innerHTML = "";
  downloadPdf.disabled = true;
  steps.forEach((step) => step.classList.remove("active", "done"));
}

function activateStep(index) {
  steps.forEach((step, i) => {
    step.classList.toggle("done", i < index);
    step.classList.toggle("active", i === index);
  });
}

function renderSummary(summary) {
  const rows = [
    ["Name", summary.name],
    ["Language", summary.language],
    ["Framework", summary.framework],
    ["Package Manager", summary.package_manager],
    ["Project Type", summary.project_type],
    ["Stars", summary.stars],
    ["Forks", summary.forks],
    ["Files Analyzed", summary.files],
  ];

  summaryContent.innerHTML = rows
    .map(([label, value]) => {
      return `<div class="flex justify-between gap-4 pb-2" style="border-bottom: 1px solid var(--border-color)">
        <span style="color: var(--text-secondary)">${label}</span>
        <span class="text-right font-semibold" style="color: var(--text-primary)">${escapeHtml(String(value ?? "Unknown"))}</span>
      </div>`;
    })
    .join("");

  summaryCard.classList.remove("hidden");
}

function setupDownload(element, endpoint, path) {
  if (!path) {
    element.disabled = true;
    return;
  }
  element.disabled = false;
  element.onclick = () => {
    window.location.href = `${endpoint}?path=${encodeURIComponent(path)}`;
  };
}

function showError(message) {
  errorMessage.textContent = message;
  errorMessage.classList.remove("hidden");
}

function escapeHtml(value) {
  return value
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

// --- Content Creator Form Handling ---
const contentForm = document.getElementById("content-form");
const contentButton = document.getElementById("content-button");
const contentError = document.getElementById("content-error");
const contentStatus = document.getElementById("content-status");
const contentResults = document.getElementById("content-results");
const contentTitle = document.getElementById("content-title");
const contentTypeBadge = document.getElementById("content-type-badge");
const contentNotes = document.getElementById("content-notes");
const contentPreview = document.getElementById("content-preview");
const downloadContent = document.getElementById("download-content");
const contentLiveBanner = document.getElementById("content-live-banner");
const contentLiveLink = document.getElementById("content-live-link");
const contentPublishError = document.getElementById("content-publish-error");

if (contentForm) {
  contentForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    const input = document.getElementById("content-input").value.trim();
    if (!input) return;

    contentError.classList.add("hidden");
    contentError.textContent = "";
    contentResults.classList.add("hidden");
    contentPreview.innerHTML = "";
    contentLiveBanner.classList.add("hidden");
    contentPublishError.classList.add("hidden");
    contentButton.disabled = true;
    contentButton.textContent = "Generating...";
    contentStatus.textContent = "Classifying, researching, drafting, reviewing...";
    contentStatus.classList.remove("hidden");

    try {
      const profile = getProfile();
      const response = await fetch("/generate-content", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          input,
          author: profile ? profile.name : "",
          email: profile ? profile.email : "",
        }),
      });

      const data = await response.json();
      if (!response.ok) {
        throw new Error(data.error || "Content generation failed.");
      }

      contentStatus.classList.add("hidden");
      contentTitle.textContent = data.title || "Generated Content";
      contentTypeBadge.textContent = `input: ${data.input_type || "unknown"}`;

      if (data.devto_url) {
        contentLiveLink.href = data.devto_url;
        contentLiveBanner.classList.remove("hidden");
      }
      if (data.publish_error) {
        contentPublishError.textContent = `Generated but not published: ${data.publish_error}`;
        contentPublishError.classList.remove("hidden");
      }

      const notes = [data.interpreted_as, data.notes_for_judge].filter(Boolean).join(" · ");
      contentNotes.textContent = notes || "";
      contentNotes.classList.toggle("hidden", !notes);
      contentPreview.innerHTML = marked.parse(data.content_markdown || "");
      contentResults.classList.remove("hidden");

      if (data.markdown_path) {
        downloadContent.disabled = false;
        downloadContent.onclick = () => {
          window.location.href = `/download/markdown?path=${encodeURIComponent(data.markdown_path)}`;
        };
      } else {
        downloadContent.disabled = true;
      }
    } catch (error) {
      contentStatus.classList.add("hidden");
      contentError.textContent = error.message;
      contentError.classList.remove("hidden");
    } finally {
      contentButton.disabled = false;
      contentButton.textContent = "Generate Content";
    }
  });
}
