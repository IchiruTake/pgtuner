// ----------------- UI Sync Functions -----------------
function syncNumberToSlider(id) {
    const slider = document.getElementById(id + "_range");
    const numberInput = document.getElementById(id);
    let result = Math.min(Math.max(numberInput.min, numberInput.value), numberInput.max);
    slider.value = result;
    numberInput.value = result;
}
function syncSliderToNumber(id) {
    const slider = document.getElementById(id + "_range");
    const numberInput = document.getElementById(id);
    let result = Math.min(Math.max(slider.min, slider.value), slider.max);
    numberInput.value = result;
    slider.value = result;
}

function syncLabelFromCheckbox(id, yes_text, no_text) {
    document.getElementById(id).addEventListener('change', function() {
        if (!this.checked) {
            this.nextElementSibling.textContent = no_text;
        } else {
            this.nextElementSibling.textContent = yes_text;
        }
    });
}

function _EstimateKernelInUseMemory() {
    // Ensure these part synchronized with Python code
    const kernel_memory_block = document.getElementById("base_kernel_memory_usage_in_mib");
    let kernel_memory = kernel_memory_block.value * 1; // To get a copy
    if (kernel_memory === -1) {
        kernel_memory = 768;
        const operating_system = document.getElementById("operating_system").value;
        if (operating_system === "containerd" || operating_system === "macos") {
            kernel_memory = 64;
        } else if (operating_system === "windows") {
            kernel_memory = 2048;
        } else if (operating_system === "PaaS") {
            kernel_memory = 0;
        }
    }
    return kernel_memory;
}

function _EstimateMonitoringInUseMemory() {
    // Ensure these parts synchronized with Python code
    const monitoring_memory_block = document.getElementById("base_monitoring_memory_usage_in_mib");
    let monitoring_memory = monitoring_memory_block.value * 1;  // To get a copy
    if (monitoring_memory === -1) {
        monitoring_memory = 256;
        const operating_system = document.getElementById("operating_system").value;
        if (operating_system === "containerd") {
            monitoring_memory = 64;
        } else if (operating_system === "PaaS") {
            monitoring_memory = 0;
        }
    }
    return monitoring_memory;
}

function _RamCalculator() {
    let kernel_memory = _EstimateKernelInUseMemory()
    let monitoring_memory = _EstimateMonitoringInUseMemory()
    let total_ram = document.getElementById("total_ram_in_gib").value * 1024;
    const final_ram = total_ram - kernel_memory - monitoring_memory;
    const postgresql_ram_available_block = document.getElementById("total_usable_ram");
    postgresql_ram_available_block.value = final_ram;
    // We already have a stronger backend validation with Pydantic so we don't need to check it here
    return final_ram;
}

document.querySelectorAll('.form-check-input').forEach(checkbox => {
    syncLabelFromCheckbox(checkbox.id, 'Yes', 'No');
});

// ----------------- UI Utility -----------------
function copyToClipboard() {
    const responseBox = document.getElementById('response-box');
    responseBox.select();
    document.execCommand('copy');
    // alert('Response copied to clipboard!');
}

function downloadResponse() {
    const responseBox = document.getElementById('response-box');
    const blob = new Blob([responseBox.value], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'response.txt';
    a.click();
    URL.revokeObjectURL(url);
}

// ----------------- Show Advanced Settings -----------------
function showHiddenDiv(idButton, idShow) {
    const divShow = document.getElementById(idShow);
    const toggleButton = document.getElementById(idButton);

    if (divShow.classList.contains('hidden')) {
        divShow.classList.remove('hidden');
        toggleButton.textContent = 'Hide Advanced Settings';
    } else {
        divShow.classList.add('hidden');
        toggleButton.textContent = 'Show Advanced Settings';
    }
}

//------------------ Devlog Animation -----------------
// Devlog entry expansion functionality
document.querySelectorAll('.devlog-entry').forEach(entry => {
    entry.addEventListener('click', function(e) {
        // Prevent expansion if clicking on links
        if (e.target.tagName === 'A' || e.target.closest('a')) {
            return;
        }

        const details = this.querySelector('.devlog-details');
        const icon = this.querySelector('.expand-icon');
        const isExpanded = !details.classList.contains('hidden');

        // Close all other entries
        document.querySelectorAll('.devlog-entry').forEach(otherEntry => {
            if (otherEntry !== this) {
                const otherDetails = otherEntry.querySelector('.devlog-details');
                const otherIcon = otherEntry.querySelector('.expand-icon');

                otherDetails.classList.add('hidden');
                otherIcon.style.transform = 'rotate(0deg)';
                otherEntry.classList.remove('ring-2', 'ring-blue-200');
            }
        });

        // Toggle current entry
        if (isExpanded) {
            details.classList.add('hidden');
            icon.style.transform = 'rotate(0deg)';
            this.classList.remove('ring-2', 'ring-blue-200');
        } else {
            details.classList.remove('hidden');
            icon.style.transform = 'rotate(180deg)';
            this.classList.add('ring-2', 'ring-blue-200');

            // Smooth scroll to show the expanded content
            setTimeout(() => {
                details.scrollIntoView({
                    behavior: 'smooth',
                    block: 'nearest'
                });
            }, 100);
        }
    });
});

//------------------ Tooltip Animation -----------------
// Setup tooltips
function setupTooltips() {
    const tooltipTriggers = document.querySelectorAll('.tooltip-trigger');
    const tooltip = document.getElementById('tooltip');
    const tooltipContent = document.getElementById('tooltip-content');
    const tooltipHeader = document.getElementById('tooltip-header');

    tooltipTriggers.forEach(trigger => {
        trigger.addEventListener('mouseenter', (e) => {
            const content = trigger.getAttribute('data-tooltip');
            const header = trigger.getAttribute('data-tooltip-header');

            tooltipContent.textContent = content;
            tooltipHeader.textContent = header;

            const rect = trigger.getBoundingClientRect();
            const tooltipHeight = tooltip.offsetHeight;

            tooltip.style.top = `${rect.top - tooltipHeight - 10}px`;
            tooltip.style.left = `${rect.left + (rect.width / 2) - (tooltip.offsetWidth / 2)}px`;
            tooltip.classList.add('show');
        });

        trigger.addEventListener('mouseleave', () => {
            tooltip.classList.remove('show');
        });
    });
}
// Reposition tooltips on scroll/resize
window.addEventListener('scroll', function() {
    const tooltip = document.getElementById('tooltip');
    if (tooltip) tooltip.classList.remove('show');
});

window.addEventListener('resize', function() {
    const tooltip = document.getElementById('tooltip');
    if (tooltip) tooltip.classList.remove('show');
});

// ----------------- Ram Bar Visualization -----------------
// Ram Bar Visualization
const colors = ['#a6cee3','#1f78b4','#b2df8a','#33a02c','#fb9a99','#e31a1c','#fdbf6f','#ff7f00','#cab2d6','#6a3d9a','#ffff99','#b15928']
const ramUsageElement = [1, 4, 2, 2, 1]; // Example RAM usage in GiB
function createRamBar(totalRam, ramUsageElements) {
    const ramBar = document.getElementById('ram-bar');
    let content = '';
    let sum = 0;
    for (let i = 0; i < ramUsageElements.length; i++) {
        sum += ramUsageElements[i];
        if (sum > totalRam) break;
        const percentage = (ramUsageElements[i] / totalRam) * 100;
        content += `<div class="ram-bar h-full transition-all duration-300" style="width: ${percentage}%; background-color: ${colors[i % colors.length]}"></div>`;
    }
    ramBar.innerHTML = content;
}

// ------------------- DOMContentLoaded-----------------
// Initialize DOMContentLoaded
document.addEventListener('DOMContentLoaded', () => {
    setupTooltips();
    createRamBar(10, ramUsageElement);
    _RamCalculator();
});