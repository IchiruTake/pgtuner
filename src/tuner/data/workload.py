from enum import StrEnum, IntEnum

__all__ = ["PG_WORKLOAD", "PG_PROFILE_OPTMODE", "PG_BACKUP_TOOL", "PG_SIZING"]

# ==============================================================================
"""
This enum represents some typical workloads or usage patterns that can be used to tune the database.
Options:
-------
# Business Workload
TSR_IOT = 'tst' (Time-Series Data / Streaming)
    - Description: Database usually aggregated with timestamped data points.
    - Transaction Lifespan: Short-lived transactions optimized for high frequency for IoT data.
    - Read/Write Balance: Heavy writes with frequent time-stamped data points. Frequent READ operation (usually 
        after 1 - 5 minutes) for monitoring, dashboard display, and alerting.
    - Query Complexity: Often simple reads with time-based filtering and aggregations (non-complex data transformation,
        joins, and aggregations).
    - Data Access (READ) Pattern: Sequential access to time-ordered data, usually within neighboring page
    - Insertion (WRITE) Pattern: Append-only; Constant insertion of new, timestamped records or batch insertion 
        of log entries.
    - Typical Usage: Monitoring IoT data, and system performance metrics. Log analysis, monitoring, anomaly 
        detection, and security event correlation.

OLTP = 'oltp' (Online Transaction Processing)
    - Description: Traditional OLTP workload with frequent read and write operations.
    - Transaction Lifespan: Short-lived transactions (milliseconds to seconds).
    - Read/Write Balance: Balanced; often read-heavy but includes frequent writes.
    - Query Complexity: Simple read and write queries, usually targeting single rows or small subsets.
    - Data Access (READ) Pattern: Random access to small subsets of data.
    - Insertion (WRITE) Pattern: Constant insertion and updates, with high concurrency.
    - Typical Usage: Applications like banking, e-commerce, and CRM where data changes frequently.

HTAP = 'htap' (Hybrid Transactional/Analytical Processing) && TSR_HTAP = 'tsh' (Time-Series HTAP)
    - Description: Combines OLTP and OLAP workloads in a single database. Analytic workloads are usually financial
        reporting, real-time analytics.
    - Transaction Lifespan: Mix of short transactional and long analytical queries.
    - Read/Write Balance: Balances frequent writes (OLTP) with complex reads (OLAP).
    - Query Complexity: Simple transactional queries along with complex analytical queries.
    - Data Access (READ) Pattern: Random access for OLTP and sequential access for OLAP.
    - Insertion (WRITE) Pattern: Real-time or near real-time inserts, often through streaming or continuous updates.
    - Typical Usage: Real-time dashboards, fraud detection where operational and historical data are combined.

# Internal Management Workload
OLAP = 'olap' (Online Analytical Processing) && TSR_OLAP = 'tsa' (Time-Series Data Analytics)
    - Description: Analytical workload with complex queries and aggregations.
    - Transaction Lifespan: Long-lived, complex queries (seconds to minutes, even HOUR on large database).
    - Read/Write Balance: Read-heavy; few updates or inserts after initial loading.
    - Query Complexity: Complex read queries with aggregations, joins, and large scans.
    - Data Access (READ) Pattern: Sequential access to large data sets.
    - Insertion (WRITE) Pattern: Bulk insertion during ETL processes, usually at scheduled intervals.
    - Typical Usage: Business analytics and reporting where large data volumes are analyzed.

# Specific Workload such as Search, RAG, Geospatial
VECTOR = 'vector'
    - Description: Workload operates over vector-based data type such as SEARCH (search toolbar in Azure),
        INDEX (document indexing) and RAG (Retrieval-Augmented Generation), and GEOSPATIAL (Geospatial Workloads).
        Whilst data and query plans are not identical, they share similar characteristics in terms of Data Access.
    - Transaction Lifespan: Varies based on query complexity, usually fast and low-latency queries.
    - Read/Write Balance: Read-heavy with occasional writes in normal operation (ignore bulk load).
    - Query Complexity: Complex, involving vector search, similarity queries, and geospatial filtering.
    - Data Access (READ) Pattern: Random access to feature vectors, embeddings, and geospatial data.
    - Insertion (WRITE) Pattern: Bulk insertions for training datasets at beginning but some real-time
        and minor/small updates for live models.
    - Typical Usage: Full-text search in e-commerce, knowledge bases, and document search engines; Model training,
        feature extraction, and serving models in recommendation systems; Location-based services, mapping,
        geographic data analysis, proximity searches.

"""
class PG_WORKLOAD(StrEnum):
    # This enum is not comparable
    TSR_IOT = 'tst'
    OLTP = 'oltp'
    HTAP = 'htap'
    OLAP = 'olap'
    VECTOR = 'vector'

# =============================================================================
"""
The PostgreSQL optimization mode during workload, maintenance, logging experience for DEV/DBA, and probably other
options. Note that please do not rely on this tuning profile to be a single source of truth, but ignoring other
forms of allowing maximum performance and data integrity.

Parameters:
----------

NONE: str = "none"
    This mode would bypass the second phase of the tuning process and just apply the general tuning. Note that
    if set to this mode, if our preset turns out to be wrong and not suit with your server, no adjustment on the
    tuning is made.

SPIDEY: str = "lightweight"
    This mode is suitable for the server with limited resources, or you just want to apply the easiest basic
    workload optimization profile on your server that is expected to be safe for most cases. Please note that there
    is no guarantee that this mode is safe for all cases, and no guarantee that this mode brings the best
    performance as compared to the other modes.

OPTIMUS_PRIME: str = "general"
    This mode is suitable for the server with more resources, or you want to apply the general workload (which is
    also the default setting), where we would balance between the data integrity and the performance.

PRIMORDIAL: str = "aggressive"
    This mode is suitable for the server with more resources, or you want to apply the aggressive workload with
    more focused on the data integrity.

"""
class PG_PROFILE_OPTMODE(IntEnum):
    # This enum requires comparable
    NONE = 0
    SPIDEY = 1
    OPTIMUS_PRIME = 2
    PRIMORDIAL = 3

# =============================================================================
# This class contains the backup tool that is used to backup the database.
class PG_BACKUP_TOOL(IntEnum):
    DISK_SNAPSHOT = 0 # 'Backup by Disk Snapshot'
    PG_DUMP = 1 # 'pg_dump/pg_dumpall: Textual backup'
    PG_BASEBACKUP = 2 # 'pg_basebackup [--incremental] or streaming replication (byte-capture change)'
    PG_LOGICAL = 3 # 'pg_logical and alike: Logical replication'

# ==============================================================================
# This class determines the workload sizing
# The PostgreSQL sizing profile determines the workload sizing.
class PG_SIZING(IntEnum):
    MINI = 0
    MEDIUM = 1
    LARGE = 2
    MALL = 3
    BIGT = 4

