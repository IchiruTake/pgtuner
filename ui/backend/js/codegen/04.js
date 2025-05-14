// ==================================================================================
/**
 * Original Source File: ./src/tuner/data/options.py
 */
// PG_TUNE_USR_KWARGS stores tuning user/app-defined keywords to adjust the tuning phase.
class PG_TUNE_USR_KWARGS {
    constructor(options = {}) {
        // Connection
        this.user_max_connections = options.user_max_connections ?? 0;
        this.cpu_to_connection_scale_ratio = options.cpu_to_connection_scale_ratio ?? 4;
        this.superuser_reserved_connections_scale_ratio = options.superuser_reserved_connections_scale_ratio ?? 1.5;
        this.single_memory_connection_overhead = options.single_memory_connection_overhead ?? (5 * Mi);
        this.memory_connection_to_dedicated_os_ratio = options.memory_connection_to_dedicated_os_ratio ?? 0.7;
        // Memory Utilization (Basic)
        this.effective_cache_size_available_ratio = options.effective_cache_size_available_ratio ?? 0.985;
        this.shared_buffers_ratio = options.shared_buffers_ratio ?? 0.25;
        this.max_work_buffer_ratio = options.max_work_buffer_ratio ?? 0.075;
        this.effective_connection_ratio = options.effective_connection_ratio ?? 0.75;
        this.temp_buffers_ratio = options.temp_buffers_ratio ?? 0.25;
        // Memory Utilization (Advanced)
        this.max_normal_memory_usage = options.max_normal_memory_usage ?? 0.45;
        this.mem_pool_tuning_ratio = options.mem_pool_tuning_ratio ?? 0.4;
        this.hash_mem_usage_level = options.hash_mem_usage_level ?? -5;
        this.mem_pool_parallel_estimate = options.mem_pool_parallel_estimate ?? true;
        // Tune logging behaviour
        this.max_query_length_in_bytes = options.max_query_length_in_bytes ?? (2 * Ki);
        this.max_runtime_ms_to_log_slow_query = options.max_runtime_ms_to_log_slow_query ?? (2 * K10);
        this.max_runtime_ratio_to_explain_slow_query = options.max_runtime_ratio_to_explain_slow_query ?? 1.5;
        // WAL control parameters
        this.wal_segment_size = options.wal_segment_size ?? BASE_WAL_SEGMENT_SIZE;
        this.min_wal_size_ratio = options.min_wal_size_ratio ?? 0.05;
        this.max_wal_size_ratio = options.max_wal_size_ratio ?? 0.05;
        this.wal_keep_size_ratio = options.wal_keep_size_ratio ?? 0.05;
        // Vacuum Tuning
        this.autovacuum_utilization_ratio = options.autovacuum_utilization_ratio ?? 0.80;
        this.vacuum_safety_level = options.vacuum_safety_level ?? 2;
    }
}

// PG_TUNE_USR_OPTIONS defines the advanced tuning options.
class PG_TUNE_USR_OPTIONS {
    constructor(options = {}) {
        // Basic profile for system tuning
        this.workload_type = options.workload_type ?? PG_WORKLOAD.HTAP;
        this.workload_profile = options.workload_profile ?? PG_SIZING.LARGE;
        this.pgsql_version = options.pgsql_version ?? 17;

        // System parameters
        this.operating_system = options.operating_system ?? 'linux';
        this.vcpu = options.vcpu ?? 4;
        this.total_ram = options.total_ram ?? (16 * Gi);
        this.base_kernel_memory_usage = options.base_kernel_memory_usage ?? -1;
        this.base_monitoring_memory_usage = options.base_monitoring_memory_usage ?? -1;
        this.opt_mem_pool = options.opt_mem_pool ?? PG_PROFILE_OPTMODE.OPTIMUS_PRIME;

        // Disk options for data partitions (required)
        this.data_index_spec = options.data_index_spec; // Expected to be an instance of PG_DISK_PERF
        this.wal_spec = options.wal_spec; // Expected to be an instance of PG_DISK_PERF
        // Data Integrity, Transaction, Recovery, and Replication
        this.max_backup_replication_tool = options.max_backup_replication_tool ?? PG_BACKUP_TOOL.PG_BASEBACKUP;
        this.opt_transaction_lost = options.opt_transaction_lost ?? PG_PROFILE_OPTMODE.NONE;
        this.opt_wal_buffers = options.opt_wal_buffers ?? PG_PROFILE_OPTMODE.SPIDEY;
        this.max_time_transaction_loss_allow_in_millisecond = options.max_time_transaction_loss_allow_in_millisecond ?? 650;
        this.max_num_stream_replicas_on_primary = options.max_num_stream_replicas_on_primary ?? 0;
        this.max_num_logical_replicas_on_primary = options.max_num_logical_replicas_on_primary ?? 0;
        this.offshore_replication = options.offshore_replication ?? false;
        // Database tuning options

        this.tuning_kwargs = options.tuning_kwargs ?? new PG_TUNE_USR_KWARGS();
        // Anti-wraparound vacuum tuning options
        this.database_size_in_gib = options.database_size_in_gib ?? 0;
        this.num_write_transaction_per_hour_on_workload = options.num_write_transaction_per_hour_on_workload ?? (50 * K10);

        // System tuning flags
        this.enable_database_general_tuning = options.enable_database_general_tuning ?? true;
        this.enable_database_correction_tuning = options.enable_database_correction_tuning ?? true;
        this.align_index = options.align_index ?? 1;

        // Run post-initialization adjustments
        this.model_post_init();
    }

    /**
     * Adjust and validate tuning options.
     */
    model_post_init() {
        // Disable correction tuning if general tuning is off.
        if (!this.enable_database_general_tuning) {
            this.enable_database_correction_tuning = false;
        }

        // Set base monitoring memory usage if not provided.
        if (this.base_monitoring_memory_usage === -1) {
            this.base_monitoring_memory_usage = 256 * Mi;
            if (this.operating_system === 'containerd') {
                this.base_monitoring_memory_usage = 64 * Mi;
            } else if (this.operating_system === 'PaaS') {
                this.base_monitoring_memory_usage = 0;
            }
            console.debug(`Set the monitoring memory usage to ${bytesize_to_hr(this.base_monitoring_memory_usage, false, ' ')}`);
        }

        // Set base kernel memory usage if not provided.
        if (this.base_kernel_memory_usage === -1) {
            this.base_kernel_memory_usage = 768 * Mi;
            if (this.operating_system === 'containerd') {
                this.base_kernel_memory_usage = 64 * Mi;
            } else if (this.operating_system === 'windows') {
                this.base_kernel_memory_usage = 2 * Gi;
            } else if (this.operating_system === 'PaaS') {
                this.base_kernel_memory_usage = 0;
            }
            console.debug(`Set the kernel memory usage to ${bytesize_to_hr(this.base_kernel_memory_usage, false, ' ')}`);
        }

        // Check minimal usable RAM.
        this.usable_ram = this.total_ram - this.base_kernel_memory_usage - this.base_monitoring_memory_usage
        if (this.usable_ram < 4 * Gi) {
            const _sign = (this.usable_ram >= 0) ? '+' : '-';
            const _msg = `The usable RAM ${_sign}${bytesize_to_hr(this.usable_ram, false, ' ')} is less than 4 GiB. Tuning may not be accurate.`;
            console.warn(_msg);
        } else {
            console.debug(`The usable RAM is ${bytesize_to_hr(this.usable_ram)}`);
        }

        // Adjust database size based on data volume.
        const _database_limit = Math.ceil((this.data_index_spec.disk_usable_size / Gi) * 0.90);
        if (this.database_size_in_gib === 0) {
            console.warn('Database size is 0 GiB; estimating as 60% of data volume.');
            this.database_size_in_gib = Math.ceil((this.data_index_spec.disk_usable_size / Gi) * 0.60);
        }
        if (this.database_size_in_gib > _database_limit) {
            console.warn(`Database size ${this.database_size_in_gib} GiB exceeds 90% of data volume; capping to ${_database_limit} GiB.`);
            this.database_size_in_gib = _database_limit;
        }

        // Add the hardware_scope into dictionary format (a cache)
        this.hardware_scope = {
            'cpu': this.workload_profile,
            'mem': this.workload_profile,
            'net': this.workload_profile,
            'disk': this.workload_profile,
            'overall': this.workload_profile
        };
    }

    /**
     * Translates a term to its corresponding hardware scope.
     * @param {string|null} term - The term for hardware scope.
     * @returns {*} The corresponding workload profile.
     */
    translate_hardware_scope(term) {
        if (term !== null) {
            term = term.toLowerCase().trim();
            if (this.hardware_scope.hasOwnProperty(term)) {
                return this.hardware_scope[term];
            } else {
                console.debug(`Hardware scope ${term} not supported -> falling back to overall profile.`);
            }
        }
        return this.workload_profile;
    }
}