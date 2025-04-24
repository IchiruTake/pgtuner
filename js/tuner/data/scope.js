import { APP_NAME_UPPER, __VERSION__ } from '../../static/vars.js';

/*
  PG_SCOPE: The applied scope for each of the tuning items.
*/
const PG_SCOPE = Object.freeze({
    VM: 'vm',
    CONNECTION: 'conn',
    FILESYSTEM: 'fs',
    MEMORY: 'memory',
    DISK_IOPS: 'iops',
    NETWORK: 'net',
    LOGGING: 'log',
    QUERY_TUNING: 'query',
    MAINTENANCE: 'maint',
    ARCHIVE_RECOVERY_BACKUP_RESTORE: 'backup',
    EXTRA: 'extra',
    OTHERS: 'others',
});

/*
  PGTUNER_SCOPE: The internal managed scope for the tuning items.
*/
class PGTUNER_SCOPE {
    constructor(value) {
        this.value = value;
    }

    disclaimer() {
        // For simplicity, use the local system time.
        // If GetTimezone is available, you can adjust the time accordingly.
        const dt = new Date().toLocaleString();
        if (this.value === 'kernel_sysctl') {
            return `# Read this disclaimer before applying the tuning result
# ============================================================
# ${APP_NAME_UPPER}-v${__VERSION__}: The tuning is started at ${dt} 
# -> Target Scope: ${this.value}
# DISCLAIMER: This kernel tuning options is based on our experience, and should not be 
# applied directly to the system. Please consult with your database administrator, system
# administrator, or software/system delivery manager before applying the tuning result.
# HOWTO: It is recommended to apply the tuning result by copying the file and pasting it 
# as the final configuration under the /etc/sysctl.d/* directory rather than overwrite 
# previous configuration. Please DO NOT apply the tuning result directly to the system 
# by any means, and ensure that the system is capable of rolling back the changes if the
# system is not working as expected.
# ============================================================
`;
        } else if (this.value === 'database_config') {
            return `# Read this disclaimer before applying the tuning result
# ============================================================
# ${APP_NAME_UPPER}-v${__VERSION__}: The tuning is started at ${dt} 
# -> Target Scope: ${this.value}
# DISCLAIMER: This database tuning options is based on our experience, and should not be 
# applied directly to the system. There is ZERO guarantee that this tuning guideline is 
# the best for your system, for every tables, indexes, workload, and queries. Please 
# consult with your database administrator or software/system delivery manager before
# applying the tuning result.
# HOWTO: It is recommended to apply the tuning result under the /etc/postgresql/* directory 
# or inside the $PGDATA/conf/* or $PGDATA/* directory depending on how you start your
# PostgreSQL server. Please double check the system from the SQL interactive sessions to 
# ensure things are working as expected. Whilst it is possible to start the PostgreSQL 
# server with the new configuration, it could result in lost of configuration (such as new 
# version update, unknown configuration changes, extension or external configuration from 
# 3rd-party tools, or no inherited configuration from the parent directory). It is not 
# recommended to apply the tuning result directly to the system without a proper backup, 
# and ensure the system is capable of rolling back the changes if the system is not working.
# ============================================================
`;
        }
        return "";
    }
}

// Define enum instances for PGTUNER_SCOPE
PGTUNER_SCOPE.KERNEL_SYSCTL = new PGTUNER_SCOPE('kernel_sysctl');
PGTUNER_SCOPE.KERNEL_BOOT = new PGTUNER_SCOPE('kernel_boot');
PGTUNER_SCOPE.DATABASE_CONFIG = new PGTUNER_SCOPE('database_config');

export { PGTUNER_SCOPE, PG_SCOPE };
