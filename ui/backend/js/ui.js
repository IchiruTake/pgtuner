// This JS file is dedicated for the UI display only
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

function ram_calculator() {
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