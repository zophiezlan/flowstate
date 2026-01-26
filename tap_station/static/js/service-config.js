/**
 * Service Configuration Helper for flowstate Frontend
 *
 * This script fetches service configuration from the backend and provides
 * helper functions to access configured values in the UI.
 *
 * Usage:
 *   Include this script in your HTML templates:
 *   <script src="{{ url_for('static', filename='js/service-config.js') }}"></script>
 *
 *   Then use in your code:
 *   ServiceConfig.load().then(() => {
 *     document.title = ServiceConfig.getServiceName();
 *     updateLabel('queue-count', ServiceConfig.getLabel('queue_count'));
 *   });
 */

const ServiceConfig = (function () {
  "use strict";

  // Configuration data (loaded from API)
  let config = null;
  let loadPromise = null;

  // Default configuration (fallback)
  const DEFAULT_CONFIG = {
    service_name: "Drug Checking Service",
    workflow_stages: [
      {
        id: "QUEUE_JOIN",
        label: "In Queue",
        order: 1,
        visible_to_public: true,
      },
      {
        id: "SERVICE_START",
        label: "Being Served",
        order: 2,
        visible_to_public: true,
      },
      { id: "EXIT", label: "Completed", order: 3, visible_to_public: true },
    ],
    ui_labels: {
      queue_count: "people in queue",
      wait_time: "estimated wait",
      served_today: "served today",
      avg_service_time: "avg service time",
      service_status: "service status",
      status_active: "ACTIVE",
      status_idle: "IDLE",
      status_stopped: "STOPPED",
    },
    display_settings: {
      refresh_interval: 5,
      show_queue_positions: true,
      show_wait_estimates: true,
      show_served_count: true,
      show_avg_time: true,
    },
    capacity: {
      people_per_hour: 12,
      avg_service_minutes: 5,
    },
  };

  /**
   * Load service configuration from backend API
   * @returns {Promise} Promise that resolves when config is loaded
   */
  function load() {
    // Return existing promise if already loading
    if (loadPromise) {
      return loadPromise;
    }

    // Return resolved promise if already loaded
    if (config) {
      return Promise.resolve(config);
    }

    // Fetch configuration from API
    loadPromise = fetch("/api/service-config")
      .then((response) => {
        if (!response.ok) {
          throw new Error(`HTTP error! status: ${response.status}`);
        }
        return response.json();
      })
      .then((data) => {
        config = data;
        console.log("Service configuration loaded:", config.service_name);
        return config;
      })
      .catch((error) => {
        console.error("Failed to load service config, using defaults:", error);
        config = DEFAULT_CONFIG;
        return config;
      })
      .finally(() => {
        loadPromise = null;
      });

    return loadPromise;
  }

  /**
   * Get service name
   * @returns {string} Service name
   */
  function getServiceName() {
    return (config || DEFAULT_CONFIG).service_name;
  }

  /**
   * Get all workflow stages
   * @param {boolean} publicOnly - Return only public-facing stages
   * @returns {Array} Array of stage objects
   */
  function getStages(publicOnly = false) {
    const stages = (config || DEFAULT_CONFIG).workflow_stages;
    if (publicOnly) {
      return stages.filter((s) => s.visible_to_public);
    }
    return stages;
  }

  /**
   * Get stage label by ID
   * @param {string} stageId - Stage identifier
   * @returns {string} Stage label
   */
  function getStageLabel(stageId) {
    const stages = (config || DEFAULT_CONFIG).workflow_stages;
    const stage = stages.find((s) => s.id === stageId);
    return stage ? stage.label : stageId;
  }

  /**
   * Get UI label by key
   * @param {string} key - Label key
   * @param {string} defaultValue - Default value if not found
   * @returns {string} Label text
   */
  function getLabel(key, defaultValue = null) {
    const labels = (config || DEFAULT_CONFIG).ui_labels;
    return labels[key] || defaultValue || key;
  }

  /**
   * Get display setting
   * @param {string} key - Setting key
   * @param {*} defaultValue - Default value if not found
   * @returns {*} Setting value
   */
  function getDisplaySetting(key, defaultValue = null) {
    const settings = (config || DEFAULT_CONFIG).display_settings;
    return settings[key] !== undefined ? settings[key] : defaultValue;
  }

  /**
   * Get refresh interval in seconds
   * @returns {number} Refresh interval
   */
  function getRefreshInterval() {
    return getDisplaySetting("refresh_interval", 5);
  }

  /**
   * Check if setting is enabled
   * @param {string} key - Setting key
   * @returns {boolean} True if enabled
   */
  function isEnabled(key) {
    return getDisplaySetting(key, true) === true;
  }

  /**
   * Get capacity settings
   * @returns {Object} Capacity configuration
   */
  function getCapacity() {
    return (config || DEFAULT_CONFIG).capacity;
  }

  /**
   * Get first stage (typically QUEUE_JOIN)
   * @returns {Object} First stage object
   */
  function getFirstStage() {
    const stages = getStages();
    return stages.length > 0 ? stages[0] : null;
  }

  /**
   * Get last stage (typically EXIT)
   * @returns {Object} Last stage object
   */
  function getLastStage() {
    const stages = getStages();
    return stages.length > 0 ? stages[stages.length - 1] : null;
  }

  /**
   * Check if configuration is loaded
   * @returns {boolean} True if loaded
   */
  function isLoaded() {
    return config !== null;
  }

  /**
   * Get raw configuration object
   * @returns {Object} Configuration object
   */
  function getRawConfig() {
    return config || DEFAULT_CONFIG;
  }

  /**
   * Apply labels to DOM elements
   * Looks for elements with data-label attribute and updates their text
   *
   * Example:
   *   <span data-label="queue_count">people in queue</span>
   *
   * After calling applyLabels():
   *   <span data-label="queue_count">waiting</span>  (if configured)
   */
  function applyLabels() {
    document.querySelectorAll("[data-label]").forEach((element) => {
      const key = element.getAttribute("data-label");
      const label = getLabel(key);
      if (label) {
        element.textContent = label;
      }
    });
  }

  /**
   * Apply service name to DOM elements
   * Looks for elements with data-service-name attribute
   *
   * Example:
   *   <h1 data-service-name>Drug Checking Service</h1>
   *
   * After calling applyServiceName():
   *   <h1 data-service-name>Your Custom Service Name</h1>
   */
  function applyServiceName() {
    const serviceName = getServiceName();
    document.querySelectorAll("[data-service-name]").forEach((element) => {
      element.textContent = serviceName;
    });
  }

  /**
   * Apply all configurable elements
   * Convenience method to apply labels and service name
   */
  function applyAll() {
    applyLabels();
    applyServiceName();
  }

  /**
   * Initialize and apply configuration
   * Call this on page load
   *
   * @returns {Promise} Promise that resolves when config is loaded and applied
   */
  function init() {
    return load().then(() => {
      applyAll();
      return config;
    });
  }

  // Public API
  return {
    load,
    init,
    getServiceName,
    getStages,
    getStageLabel,
    getLabel,
    getDisplaySetting,
    getRefreshInterval,
    isEnabled,
    getCapacity,
    getFirstStage,
    getLastStage,
    isLoaded,
    getRawConfig,
    applyLabels,
    applyServiceName,
    applyAll,
  };
})();

// Auto-initialize if DOMContentLoaded has not fired yet
if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", () => {
    ServiceConfig.init().catch(console.error);
  });
} else {
  // DOMContentLoaded already fired, initialize immediately
  ServiceConfig.init().catch(console.error);
}
