// ================================================================================
/**
 * Original Source File: ./src/tuner/data/sizing.py
 */
// --------------------------------------------------------------------------
// ENUM choices
/**
 * Enumeration of PostgreSQL workloads to having some typical workloads or usage patterns.
 * Available values:
 * - TSR_IOT: 'tst' (Time-Series Data / Streaming)
 * - OLTP: 'oltp' (Online Transaction Processing)
 * - HTAP: 'htap' (Hybrid Transactional/Analytical Processing)
 * - OLAP: 'olap' (Online Analytical Processing)
 * - VECTOR: 'vector' (Vector-based workloads such as SEARCH, INDEX, RAG, and GEOSPATIAL)
 */
const PG_WORKLOAD = Object.freeze({
    TSR_IOT: "tst",
    OLTP: "oltp",
    HTAP: "htap",
    OLAP: "olap",
    VECTOR: "vector",
});

// PG_SIZING: Represents a PostgreSQL sizing profile
class PG_SIZING {
    constructor(value) {
        if (typeof value === 'string') {
            if (!PG_SIZING.values.includes(value)) {
                throw new Error(`Invalid value: ${value}`);
            }
        }  else if (typeof value === 'number') {
            value = PG_SIZING.values[value];
        } else {
            throw new Error(`Invalid value: ${value}`);
        }
        this.value = value;
    }

    static values = ['mini', 'medium', 'large', 'mall', 'bigt'];
    static MINI = new PG_SIZING('mini');
    static MEDIUM = new PG_SIZING('medium');
    static LARGE = new PG_SIZING('large');
    static MALL = new PG_SIZING('mall');
    static BIGT = new PG_SIZING('bigt');

    static fromString(str) {
        return new PG_SIZING(str)
    }

    num() {
        return PG_SIZING.values.findIndex(t => t === this.value);
    }

    equals(otherEnum) {
        return this.num() === otherEnum.num();
    }

    toString() {
        return this.value;
    }

    valueOf() {
        return this.value;
    }

    [Symbol.toPrimitive](hint) {
        if (hint === "number") {
            return this.num();
        }
        if (hint === "string") {
            return this.value;
        }
        return this.value;
    }
}

/**
 * Enumeration of PostgreSQL backup tools.
 * Available values:
 *  - DISK_SNAPSHOT: 'Backup by Disk Snapshot'
 *  - PG_DUMP: 'pg_dump/pg_dumpall: Textual backup'
 *  - PG_BASEBACKUP: 'pg_basebackup [--incremental] or streaming replication (byte-capture change): Byte-level backup'
 *  - PG_LOGICAL: 'pg_logical and alike: Logical replication'
 */
const PG_BACKUP_TOOL = Object.freeze({
    DISK_SNAPSHOT: 0,
    PG_DUMP: 1,
    PG_BASEBACKUP: 2,
    PG_LOGICAL: 3,
})

/**
 * The PostgreSQL optimization enumeration during workload, maintenance, logging experience for DEV/DBA,
 * and possibly other options. Note that this tuning profile should not be relied on as a single source
 * of truth.
 * Available values:
 * - NONE: This mode bypasses the second phase of the tuning process and applies general tuning only.
 * - SPIDEY: Suitable for servers with limited resources, applying an easy, basic workload optimization profile.
 * - OPTIMUS_PRIME: Suitable for servers with more resources, balancing between data integrity and performance.
 * - PRIMORDIAL: Suitable for servers with more resources, applying an aggressive workload configuration with a focus on data integrity.
 */
const PG_PROFILE_OPTMODE = Object.freeze({
    NONE: 0,
    SPIDEY: 1,
    OPTIMUS_PRIME: 2,
    PRIMORDIAL: 3,
})

// =================================================================================
/**
 * Original Source File: ./src/tuner/data/scope.py
 */

// PG_SCOPE: The applied scope for each of the tuning items.
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

// PGTUNER_SCOPE: The internal managed scope for the tuning items.
class PGTUNER_SCOPE {
    constructor(value) {
        this.value = value;
    }

    valueOf() {
        return this.value;
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
# as the final configuration under the /etc/sysctl.d/ directory rather than overwrite
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
# HOWTO: It is recommended to apply the tuning result under the /etc/postgresql/ directory
# or inside the $PGDATA/conf/ or $PGDATA/ directory depending on how you start your
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
PGTUNER_SCOPE.DATABASE_CONFIG = new PGTUNER_SCOPE('database_config');


// ==================================================================================
/**
 * Original Source File: ./src/tuner/data/items.py
 */
const _FLOAT_PRECISION = 4; // Default float precision for PG_TUNE_ITEM
// The string punctuation characters
const _STRING_PUNCTUATION = `"!"#$%&'()*+,-./:;<=>?@[\]^_{}|`;

class PG_TUNE_ITEM {
    constructor(data) {
        // Required fields
        this.key = data.key;
        this.before = data.before;
        this.after = data.after;
        this.comment = data.comment || null;

        // Custom-reserved variables for developers
        this.style = data.style ?? "$1 = $2";
        this.trigger = data.trigger;
        this.partial_func = data.partial_func || null;
        this.hardware_scope = data.hardware_scope; // Expected as a tuple [hardware type, sizing value]
    }

    out(include_comment = false, custom_style = null) {
        let texts = [];
        if (include_comment && this.comment !== null && this.comment.trim() !== '') {
            // Transform the comment by prefixing each line with "# "
            const format_comment = String(this.comment).replace('\n', '\n# ');
            texts.push(`# ${format_comment}`);
            texts.push('\n');
        }
        const style = (custom_style ?? this.style) ?? "$1 = $2";
        if (!style.includes("$1") || !style.includes("$2")) {
            throw new Error(`Invalid style configuration: ${style} due to missing $1 and $2`);
        }
        // Remove duplicated spaces if present
        const cleanedStyle = style.replace(/\s\s+/g, ' ');
        const afterDisplay = this.out_display();
        const resultStyle = cleanedStyle.replace("$1", this.key).replace("$2", afterDisplay).trim();

        texts.push(resultStyle);
        return texts.join('');
    }

    out_display(override_value = null) {
        let value = override_value ?? this.after;

        if (this.partial_func && typeof this.partial_func === 'function') {
            value = this.partial_func(value);
        } else if (typeof value === 'number') {
            // Rounding and converting to a fixed point string
            value = value.toFixed(_FLOAT_PRECISION);
            // Remove trailing zeros and possible trailing dot
            value = value.replace(/(\.\d*?[1-9])0+$/,'$1').replace(/\.0+$/,'').replace(/\.$/, '.0');
        }
        if (typeof value !== 'string') {
            value = String(value);
        }
        // Trim whitespace if value contains a decimal point and remove trailing zeros
        if (value.includes('.')) {
            value = value.trim().replace(/(\.\d*?)0+$/, '$1');
            if (value.endsWith('.')) {
                value += '0';
            }
        }
        // If the original after value is a string that contains whitespace or punctuation, wrap it in single quotes.
        if (typeof this.after === 'string' &&
            (this.after.includes(' ') || _STRING_PUNCTUATION.split('').some(p => this.after.includes(p)))) {
            value = `'${value}'`;
        }
        return value;
    }

    transform_keyname() {
        return this.key.split('_').map(part => part.charAt(0).toUpperCase() + part.slice(1)).join(' ');
    }
}