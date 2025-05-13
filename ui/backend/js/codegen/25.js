function _get_text_element(element) {
    let el = document.getElementById(element)
    // console.log(element, el);
    if (el.type === 'range' || el.type === 'number') {
        // parseFloat if element.step in string has dot, parseInt
        return el.step.includes('.') ? parseFloat(el.value) : parseInt(el.value);
    } else if (el.type === 'text') {
        return el.value;
    } else if (el.type === 'select-one') {
        return el.value;
    }
    return '';
}

function _get_checkbox_element(element) {
    let el = document.getElementById(element)
    // console.log(element, el);
    if (el.type === 'checkbox') {
        return el.checked;
    }
    return '';
}

// ---------------------------------------------------------------------------------
function _build_disk_from_backend(data) {
    return new PG_DISK_PERF(
        {
            'random_iops_spec': data.random_iops_spec,
            'random_iops_scale_factor': data.random_iops_scale_factor !== null ? data.random_iops_scale_factor : 1.0,
            'throughput_spec': data.throughput_spec,
            'throughput_scale_factor': data.throughput_scale_factor !== null ? data.throughput_scale_factor : 1.0,
            'disk_usable_size': data.disk_usable_size,
            'num_disks': data.num_disks !== null ? data.num_disks : 1,
            'per_scale_in_raid': data.per_scale_in_raid !== null ? data.per_scale_in_raid : 0.75
        }
    )
}

function _build_disk_from_html(name = 'data_index_spec') {
    return {
        'random_iops_spec': _get_text_element(`${name}.random_iops`),
        'throughput_spec': _get_text_element(`${name}.throughput`),
        'disk_usable_size': _get_text_element(`${name}.disk_usable_size_in_gib`) * Gi,
    };
}

// ---------------------------------------------------------------------------------
function _build_keywords_from_backend(data) {
    return new PG_TUNE_USR_KWARGS(
        {
            // Connection
            user_max_connections: data.user_max_connections,
            cpu_to_connection_scale_ratio: data.cpu_to_connection_scale_ratio,
            superuser_reserved_connections_scale_ratio: data.superuser_reserved_connections_scale_ratio,
            single_memory_connection_overhead: data.single_memory_connection_overhead,
            memory_connection_to_dedicated_os_ratio: data.memory_connection_to_dedicated_os_ratio,

            // Memory Utilization (Basic)
            effective_cache_size_available_ratio: data.effective_cache_size_available_ratio,
            shared_buffers_ratio: data.shared_buffers_ratio,
            max_work_buffer_ratio: data.max_work_buffer_ratio,
            effective_connection_ratio: data.effective_connection_ratio,
            temp_buffers_ratio: data.temp_buffers_ratio,

            // Memory Utilization (Advanced)
            max_normal_memory_usage: data.max_normal_memory_usage,
            mem_pool_tuning_ratio: data.mem_pool_tuning_ratio,
            hash_mem_usage_level: data.hash_mem_usage_level,
            mem_pool_parallel_estimate: data.mem_pool_parallel_estimate,

            // Logging behaviour (query size, and query runtime)
            max_query_length_in_bytes: data.max_query_length_in_bytes,
            max_runtime_ms_to_log_slow_query: data.max_runtime_ms_to_log_slow_query,
            max_runtime_ratio_to_explain_slow_query: data.max_runtime_ratio_to_explain_slow_query,

            // WAL control parameters -> Change this when you initdb with custom wal_segment_size (not recommended)
            wal_segment_size: BASE_WAL_SEGMENT_SIZE,
            min_wal_size_ratio: data.min_wal_size_ratio,
            max_wal_size_ratio: data.max_wal_size_ratio,
            wal_keep_size_ratio: data.wal_keep_size_ratio,
            // Vacuum Tuning
            autovacuum_utilization_ratio: data.autovacuum_utilization_ratio,
            vacuum_safety_level: data.vacuum_safety_level
        }
    )
}

function _build_keywords_from_html(name = 'keywords') {
    return {
        // Connection or ./tuner/adv.conn.html
        'user_max_connections': _get_text_element(`${name}.user_max_connections`),
        'cpu_to_connection_scale_ratio': _get_text_element(`${name}.cpu_to_connection_scale_ratio`),
        'superuser_reserved_connections_scale_ratio': _get_text_element(`${name}.superuser_reserved_connections_scale_ratio`),
        'single_memory_connection_overhead': _get_text_element(`${name}.single_memory_connection_overhead_in_kib`) * Ki,
        'memory_connection_to_dedicated_os_ratio': _get_text_element(`${name}.memory_connection_to_dedicated_os_ratio`),

        // Memory Utilization (Basic)
        'effective_cache_size_available_ratio': _get_text_element(`${name}.effective_cache_size_available_ratio`),
        'shared_buffers_ratio': _get_text_element(`${name}.shared_buffers_ratio`),
        'max_work_buffer_ratio': _get_text_element(`${name}.max_work_buffer_ratio`),
        'effective_connection_ratio': _get_text_element(`${name}.effective_connection_ratio`),
        'temp_buffers_ratio': _get_text_element(`${name}.temp_buffers_ratio`),

        // Memory Utilization (Advanced)
        'max_normal_memory_usage': _get_text_element(`${name}.max_normal_memory_usage`),
        'mem_pool_tuning_ratio': _get_text_element(`${name}.mem_pool_tuning_ratio`),
        'hash_mem_usage_level': _get_text_element(`${name}.hash_mem_usage_level`),
        'mem_pool_parallel_estimate': _get_checkbox_element(`${name}.mem_pool_parallel_estimate`) ?? true,

        // Logging behaviour (query size, and query runtime)
        'max_query_length_in_bytes': _get_text_element(`${name}.max_query_length_in_bytes`),
        'max_runtime_ms_to_log_slow_query': _get_text_element(`${name}.max_runtime_ms_to_log_slow_query`),
        'max_runtime_ratio_to_explain_slow_query': _get_text_element(`${name}.max_runtime_ratio_to_explain_slow_query`),

        // WAL control parameters -> Change this when you initdb with custom wal_segment_size (not recommended)
        // https://postgrespro.com/list/thread-id/1898949
        'wal_segment_size': BASE_WAL_SEGMENT_SIZE * Math.pow(2, (_get_text_element(`${name}.wal_segment_size_scale`))),
        'min_wal_size_ratio': _get_text_element(`${name}.min_wal_size_ratio`),
        'max_wal_size_ratio': _get_text_element(`${name}.max_wal_size_ratio`),
        'wal_keep_size_ratio': _get_text_element(`${name}.wal_keep_size_ratio`),

        // Vacuum Tuning & Others
        'autovacuum_utilization_ratio': _get_text_element(`${name}.autovacuum_utilization_ratio`),
        'vacuum_safety_level': _get_text_element(`${name}.vacuum_safety_level`),
    }
}

// ---------------------------------------------------------------------------------
function _build_options_from_backend(data) {
    return new PG_TUNE_USR_OPTIONS(
        {
            // Basic profile for system tuning
            'workload_type': data.workload_type,
            'workload_profile': data.workload_profile,
            'pgsql_version': data.pgsql_version,

            // System parameters
            'operating_system': data.operating_system,
            'vcpu': data.vcpu,
            'total_ram': data.total_ram,
            'base_kernel_memory_usage': data.base_kernel_memory_usage,
            'base_monitoring_memory_usage': data.base_monitoring_memory_usage,
            'opt_mem_pool': data.opt_mem_pool,

            // Disk options for data partitions (required)
            'data_index_spec': _build_disk_from_backend(data.data_index_spec),
            'wal_spec': _build_disk_from_backend(data.wal_spec),

            // Data Integrity, Transaction, Recovery, and Replication
            'max_backup_replication_tool': data.max_backup_replication_tool,
            'opt_transaction_lost': data.opt_transaction_lost,
            'opt_wal_buffers': data.opt_wal_buffers,
            'max_time_transaction_loss_allow_in_millisecond': data.max_time_transaction_loss_allow_in_millisecond,
            'max_num_stream_replicas_on_primary': data.max_num_stream_replicas_on_primary,
            'max_num_logical_replicas_on_primary': data.max_num_logical_replicas_on_primary,
            'offshore_replication': data.offshore_replication,

            // Database tuning options
            'tuning_kwargs': _build_keywords_from_backend(data.tuning_kwargs),

            // Anti-wraparound vacuum tuning options
            'database_size_in_gib': data.database_size_in_gib,
            'num_write_transaction_per_hour_on_workload': data.num_write_transaction_per_hour_on_workload,

            // System tuning flags
            'enable_database_general_tuning': data.enable_database_general_tuning,
            'enable_database_correction_tuning': data.enable_database_correction_tuning,
            'align_index': data.align_index ?? 1,
        }
    )
}

function _build_options_from_html() {
    // If -1 then output is -1, if larger than zero then multiply with MiB
    let monitoring_memory = parseInt(_get_text_element(`base_monitoring_memory_usage_in_mib`));
    monitoring_memory = Math.min(monitoring_memory, Math.max(monitoring_memory, monitoring_memory * Mi));
    let kernel_memory = parseInt(_get_text_element(`base_kernel_memory_usage_in_mib`));
    kernel_memory = Math.min(kernel_memory, Math.max(kernel_memory, kernel_memory * Mi));

    return {
        // Workload
        'workload_type': PG_WORKLOAD[_get_text_element(`workload_type`).toUpperCase()],
        'workload_profile': PG_SIZING.fromString(_get_text_element(`workload_profile`)),
        'pgsql_version': parseInt(_get_text_element(`pgsql_version`)),

        // System Parameters
        'operating_system': _get_text_element(`operating_system`),
        'vcpu': _get_text_element(`vcpu`),
        'total_ram': _get_text_element(`total_ram_in_gib`) * Gi,
        'base_kernel_memory_usage': kernel_memory,
        'base_monitoring_memory_usage': monitoring_memory,
        'opt_mem_pool': PG_PROFILE_OPTMODE[_get_text_element(`opt_mem_pool`).toUpperCase()],
        'tuning_kwargs': _build_keywords_from_html(`keywords`),

        // Disk options for data partitions (required)
        'data_index_spec': _build_disk_from_html(`data_index_spec`),
        'wal_spec': _build_disk_from_html(`wal_spec`),

        // Anti-wraparound vacuum tuning options
        'database_size_in_gib': parseInt(_get_text_element(`database_size_in_gib`)),
        'num_write_transaction_per_hour_on_workload': _get_text_element(`num_write_transaction_per_hour_on_workload`),

        // Data Integrity, Transaction, Recovery, and Replication
        'max_backup_replication_tool': PG_BACKUP_TOOL[_get_text_element(`max_backup_replication_tool`).toUpperCase()],
        'opt_transaction_lost': PG_PROFILE_OPTMODE[_get_text_element(`opt_transaction_lost`).toUpperCase()],
        'opt_wal_buffers': PG_PROFILE_OPTMODE[_get_text_element(`opt_wal_buffers`).toUpperCase()],
        'max_time_transaction_loss_allow_in_millisecond': parseInt(_get_text_element(`max_time_transaction_loss_allow_in_millisecond`)),
        'max_num_stream_replicas_on_primary': parseInt(_get_text_element(`max_num_stream_replicas_on_primary`)),
        'max_num_logical_replicas_on_primary': parseInt(_get_text_element(`max_num_logical_replicas_on_primary`)),
        'offshore_replication': _get_checkbox_element(`offshore_replication`) ?? false,

        // System tuning flags
        'enable_database_general_tuning': _get_checkbox_element(`enable_database_general_tuning`) ?? true,
        'enable_database_correction_tuning': _get_checkbox_element(`enable_database_correction_tuning`) ?? true,
        'align_index': 1,
    }
}

// ---------------------------------------------------------------------------------
function _build_request_from_backend(data) {
    return new PG_TUNE_REQUEST(
        {
            'options': _build_options_from_backend(data.options),
            'include_comment': data.include_comment ?? false,
            'custom_style': data.custom_style ?? null,
            'backup_settings': data.backup_settings ?? false,
            'analyze_with_full_connection_use': data.analyze_with_full_connection_use ?? false,
            'ignore_non_performance_setting': data.ignore_non_performance_setting ?? true,
            'output_format': data.output_format ?? 'file',
        }
    )
}

function _build_request_from_html() {
    let alter_style = _get_checkbox_element(`alter_style`) ?? false;
    let custom_style = !alter_style ? null : 'ALTER SYSTEM SET $1 = $2;'
    return {
        'options': _build_options_from_html(),
        'include_comment': _get_checkbox_element(`include_comment`) ?? false,
        'custom_style': custom_style,
        'backup_settings': _get_checkbox_element(`backup_settings`) ?? false,
        'analyze_with_full_connection_use': _get_checkbox_element(`analyze_with_full_connection_use`) ?? false,
        'ignore_non_performance_setting': _get_checkbox_element(`ignore_non_performance_setting`) ?? true,
        'output_format': _get_text_element(`output_format`) ?? 'file',
    }
}

// ---------------------------------------------------------------------------------
function web_optimize(request) {
    let response = new PG_TUNE_RESPONSE();
    // We assume the request must be the :class:`PG_TUNE_REQUEST` object
    let items = {
        13: DB13_CONFIG_PROFILE,
        14: DB14_CONFIG_PROFILE,
        15: DB15_CONFIG_PROFILE,
        16: DB16_CONFIG_PROFILE,
        17: DB17_CONFIG_PROFILE,
    }
    let tuning_items = items[parseInt(request.options.pgsql_version)];
    if (tuning_items === null || tuning_items === undefined) {
        tuning_items = DB13_CONFIG_PROFILE;
    }
    console.log(request);
    Optimize(request, response, PGTUNER_SCOPE.DATABASE_CONFIG, tuning_items);
    if (request.options.enable_database_correction_tuning) {
        correction_tune(request, response);
    }
    let exclude_names = [
        'archive_command', 'restore_command', 'archive_cleanup_command', 'recovery_end_command',
        'log_directory',
    ];
    if (request.ignore_non_performance_setting) {
        exclude_names.push(
            'deadlock_timeout', 'transaction_timeout', 'idle_session_timeout',
            'log_autovacuum_min_duration', 'log_checkpoints', 'log_connections', 'log_disconnections',
            'log_duration', 'log_error_verbosity', 'log_line_prefix', 'log_lock_waits', 'log_recovery_conflict_waits',
            'log_statement', 'log_replication_commands', 'log_min_error_statement', 'log_startup_progress_interval'
            )
    }
    if (request.options.operating_system === 'windows') {
        exclude_names.push('checkpoint_flush_after', 'bgwriter_flush_after', 'wal_writer_flush_after',
            'backend_flush_after');
    }
    const content = response.generate_content(
        PGTUNER_SCOPE.DATABASE_CONFIG, request, exclude_names, request.backup_settings, request.output_format
    );
    const mem_report = response.report(
        request.options, request.analyze_with_full_connection_use, false
    )[0];
    return {
        'content': content,
        'mem_report': mem_report,
        'response': response,
    }
}