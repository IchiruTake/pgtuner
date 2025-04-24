import { K10, BASE_WAL_SEGMENT_SIZE, Mi, Ki, Gi, Ti, M10  } from '../../static.js';

class PG_TUNE_USR_KWARGS {
    constructor(data) {
        data = data || {};
        this.user_max_connections = data.user_max_connections !== undefined ? data.user_max_connections : 0;
        this.superuser_reserved_connections_scale_ratio = data.superuser_reserved_connections_scale_ratio !== undefined ?
            data.superuser_reserved_connections_scale_ratio : 1.5;
        this.single_memory_connection_overhead = data.single_memory_connection_overhead !== undefined ?
            data.single_memory_connection_overhead : 5 * Mi;
        this.memory_connection_to_dedicated_os_ratio = data.memory_connection_to_dedicated_os_ratio !== undefined ?
            data.memory_connection_to_dedicated_os_ratio : 0.3;
        this.effective_cache_size_available_ratio = data.effective_cache_size_available_ratio !== undefined ?
            data.effective_cache_size_available_ratio : 0.985;
        this.shared_buffers_ratio = data.shared_buffers_ratio !== undefined ?
            data.shared_buffers_ratio : 0.25;
        this.max_work_buffer_ratio = data.max_work_buffer_ratio !== undefined ?
            data.max_work_buffer_ratio : 0.075;
        this.effective_connection_ratio = data.effective_connection_ratio !== undefined ?
            data.effective_connection_ratio : 0.75;
        this.temp_buffers_ratio = data.temp_buffers_ratio !== undefined ?
            data.temp_buffers_ratio : 0.25;
        this.max_normal_memory_usage = data.max_normal_memory_usage !== undefined ?
            data.max_normal_memory_usage : 0.45;
        this.mem_pool_tuning_ratio = data.mem_pool_tuning_ratio !== undefined ?
            data.mem_pool_tuning_ratio : 0.6;
        this.hash_mem_usage_level = data.hash_mem_usage_level !== undefined ?
            data.hash_mem_usage_level : -6;
        this.mem_pool_parallel_estimate = data.mem_pool_parallel_estimate !== undefined ?
            data.mem_pool_parallel_estimate : true;
        this.max_query_length_in_bytes = data.max_query_length_in_bytes !== undefined ?
            data.max_query_length_in_bytes : 2 * Ki;
        this.max_runtime_ms_to_log_slow_query = data.max_runtime_ms_to_log_slow_query !== undefined ?
            data.max_runtime_ms_to_log_slow_query : 2 * K10;
        this.max_runtime_ratio_to_explain_slow_query = data.max_runtime_ratio_to_explain_slow_query !== undefined ?
            data.max_runtime_ratio_to_explain_slow_query : 1.5;
        this.wal_segment_size = data.wal_segment_size !== undefined ?
            data.wal_segment_size : BASE_WAL_SEGMENT_SIZE;
        this.min_wal_size_ratio = data.min_wal_size_ratio !== undefined ?
            data.min_wal_size_ratio : 0.03;
        this.max_wal_size_ratio = data.max_wal_size_ratio !== undefined ?
            data.max_wal_size_ratio : 0.05;
        this.wal_keep_size_ratio = data.wal_keep_size_ratio !== undefined ?
            data.wal_keep_size_ratio : 0.05;
        this.autovacuum_utilization_ratio = data.autovacuum_utilization_ratio !== undefined ?
            data.autovacuum_utilization_ratio : 0.80;
        this.vacuum_safety_level = data.vacuum_safety_level !== undefined ?
            data.vacuum_safety_level : 2;
    }
}

export default PG_TUNE_USR_KWARGS;