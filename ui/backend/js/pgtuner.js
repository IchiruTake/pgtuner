// ----------------- Fetching API -----------------
const USE_PYTHON_BACKEND = true;
function update_response(id, value) {
    const response_box_block = document.getElementById(id);
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
    update_response('response-box', 'Loading...');
    update_response('mem-report', 'Loading...');

    const request_form = _build_request_from_html()
    if (USE_PYTHON_BACKEND) {
        // We use JS backend
        const body = JSON.stringify(request_form, null, 2);
        const response = await fetch('/tune', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: body
        });
        if (!response.ok) {
            const error = await response.json();
            update_response('response-box', JSON.stringify(error['detail'], null, 2));
            console.error('Error:', error);
        }
        const result = await response.json();
        update_response('mem-report', result['mem_report']);
        if (request_form.output_format === 'json') {
            update_response('response-box', JSON.stringify(result['content'], null, 2));
        } else {
            update_response('response-box', result['content']);
        }
        return response;
    } else {
        let request = _build_request_from_backend(request_form)
        const result = web_optimize(request);
        update_response('mem-report', result['mem_report']);
        if (request.output_format === 'json') {
            update_response('response-box', JSON.stringify(result['content'], null, 2));
        } else {
            update_response('response-box', result['content']);
        }
        return result['response']
    }
}

