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

function _get_kernel_memory() {
    // Ensure these part synchronized with Python code
    const operating_system = document.getElementById("operating_system").value;
    const kernel_memory_block = document.getElementById("base_kernel_memory_usage_in_mib");
    let kernel_memory = kernel_memory_block.value * 1; // To get a copy
    if (kernel_memory === -1) {
        if (operating_system === "linux") {
            kernel_memory = 768;
        } else if (operating_system === "windows") {
            kernel_memory = 2048;
        } else {
            kernel_memory = 64;
        }
    }
    return kernel_memory;
}

function _get_monitoring_memory() {
    // Ensure these part synchronized with Python code
    const operating_system = document.getElementById("operating_system").value;
    const monitoring_memory_block = document.getElementById("base_monitoring_memory_usage_in_mib");
    let monitoring_memory = monitoring_memory_block.value * 1;  // To get a copy
    if (monitoring_memory === -1) {
        monitoring_memory = 256;
        if (operating_system === "containerd") {
            monitoring_memory = 64;
        } else if (operating_system === "PaaS") {
            monitoring_memory = 0;
        }
    }
    return monitoring_memory;
}
function _get_total_ram() {
    // Ensure these part synchronized with Python code
    const operating_system = document.getElementById("operating_system").value;
    const add_reserved_ram_block = document.getElementById("add_system_reserved_memory_into_ram");
    let total_ram = document.getElementById("ram_sample_in_gib").value * 1024;
    if (add_reserved_ram_block.checked) {
        if (operating_system === "linux") {
            total_ram += 128;
        } else if (operating_system === "windows") {
            total_ram += 256;
        } else if (operating_system === "containerd") {
            total_ram += 32;
        }
    }
    return total_ram;
}

function ram_calculator() {
    let kernel_memory = _get_kernel_memory()
    let monitoring_memory = _get_monitoring_memory()
    let total_ram = _get_total_ram()

    const final_ram = total_ram - kernel_memory - monitoring_memory;
    const postgresql_ram_available_block = document.getElementById("total_usable_ram");
    postgresql_ram_available_block.value = final_ram;
    if (final_ram < 1536) {
        // Set it to 1.5 GiB limit
        alert('The remaining memory is less than 1.5 GiB. Please consider to increase the total RAM of your server, or switch to a more lightweight monitoring system, kernel usage, or even the operating system');
    }
    // We already have a stronger backend validation with Pydantic so we don't need to check it here
    return final_ram;
}
ram_calculator();
document.querySelectorAll('.form-check-input').forEach(checkbox => {
    syncLabelFromCheckbox(checkbox.id, 'Yes', 'No');
});

// ----------------- Fetching API -----------------
function preprocessParameters(params) {
    const nestedParams = {};

    for (const [key, value] of Object.entries(params)) {
        if (key.includes('.')) {
            const keys = key.split('.');
            let current = nestedParams;

            for (let i = 0; i < keys.length; i++) {
                const part = keys[i];

                if (i === keys.length - 1) {
                    current[part] = value;
                } else {
                    current[part] = current[part] || {};
                    current = current[part];
                }
            }
        } else {
            nestedParams[key] = value;
        }
    }
    return nestedParams;
}

function gatherFormValues() {
    const params = {};
    document.querySelectorAll('[name]').forEach(el => {
        if (el.type === 'range' || el.type === 'number') {
            // parseFloat if element.step in string has dot, parseInt
            params[el.name] = el.step.includes('.') ? parseFloat(el.value) : parseInt(el.value);
        } else if (el.type === 'text') {
            params[el.name] = el.value;
        } else if (el.type === 'select-one') {
            params[el.name] = el.value;
        }
    });

    // Add checkbox and select values
    document.querySelectorAll('input[type="checkbox"]').forEach(checkbox => {
        params[checkbox.id] = checkbox.checked;
    });
    return params;
}

function update_response(id, value) {
    const response_box_block = document.getElementById(id);
    console.log(response_box_block);
    if (response_box_block.readOnly) {
        response_box_block.readOnly = false;
        response_box_block.innerHTML = '';
        response_box_block.innerHTML = value;
        response_box_block.readOnly = true;
    } else {
        response_box_block.innerHTML = value;
    }
}

async function submitConfiguration() {
    const rawParams = gatherFormValues();
    const processedParams = preprocessParameters(rawParams);
    let body = {
        'user_options': processedParams,
        'alter_style': document.getElementById('alter_style').checked,
        'backup_settings': document.getElementById('backup_settings').checked,
        'analyze_with_full_connection_use': document.getElementById('analyze_with_full_connection_use').checked,
        'output_format': document.getElementById('output_format').value,
    };
    body = JSON.stringify(body, null, 2);
    console.log(body)

    try {
        const response = await fetch('/tune', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: body
        });
        const output_format = document.getElementById('output_format').value;
        if (response.ok) {
            // If the response is successful, show the result based on its content-type
            if (response.headers.get('content-type').includes('application/json')) {
                const result = await response.json();
                // Set the response box to be editable, then set the response to the result
                if (output_format === 'json') {
                    update_response('response-box', JSON.stringify(result['config'], null, 2));
                } else {
                    update_response('response-box', result['config']);
                }

                // Set the memory report box to be editable, then set the response to the result
                update_response('mem-report', result['mem_report']);

            } else if (response.headers.get('content-type').includes('text/plain')) {
                const result = await response.text();
                // Set the response box to be editable, then set the response to the result
                update_response('response-box', result);
            }
        } else {
            const error = await response.json();
            update_response('response-box', JSON.stringify(error['detail'], null, 2));
            console.error('Error:', error);
        }
    } catch (err) {
        update_response('response-box', err);
        console.error('Request failed:', err);
    }
}

function copyToClipboard() {
    const responseBox = document.getElementById('response-box');
    responseBox.select();
    document.execCommand('copy');
    alert('Response copied to clipboard!');
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