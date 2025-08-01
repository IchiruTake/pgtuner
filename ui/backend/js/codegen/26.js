
const _CalibrationProfile = {
    [PG_WORKLOAD.OLAP]: {
        'cpu_to_connection_scale_ratio': 2.5,
        'hash_mem_usage_level': -2.0,
        'shared_buffers_ratio': 0.33,
        'max_work_buffer_ratio': 0.175,
        'max_normal_memory_usage': 0.60,
    },
    [PG_WORKLOAD.HTAP]: {
        'cpu_to_connection_scale_ratio': 4.0,
        'hash_mem_usage_level': -2.5,
        'shared_buffers_ratio': 0.30,
        'max_work_buffer_ratio': 0.15,
        'max_normal_memory_usage': 0.60,
    },
    [PG_WORKLOAD.VECTOR]: {
        'shared_buffers_ratio': 0.33,
        'temp_buffers_ratio': 0.125,
    },
    [PG_WORKLOAD.TSR_IOT]: {
        'cpu_to_connection_scale_ratio': 6.0,
        'temp_buffers_ratio': 0.20,
        'hash_mem_usage_level': -4.0,
    },
}

function _AutoCalibrateProfile() {
    const workload_type = PG_WORKLOAD[_get_text_element(`workload_type`).toUpperCase()];
    if (_CalibrationProfile.hasOwnProperty(workload_type)) {
        for (const [key, value] of Object.entries(_CalibrationProfile[workload_type])) {
            _set_text_element(`keywords.${key}`, value);
        }
    }
}
