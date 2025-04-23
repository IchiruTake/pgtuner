/**
This enum represents some typical workloads or usage patterns that can be used to tune the database.
Options:
-------

# P
TSR_IOT = 'tst' (Time-Series Data / Streaming)
    - Description: Database usually aggregated with timestamped data points.
    - Transaction Lifespan: Short-lived transactions optimized for high frequency for IoT data.
    - Read/Write Balance: Heavy writes with frequent time-stamped data points. Frequent READ operation (
        usually after 1 - 5 minutes) for monitoring, dashboard display, and alerting.
    - Query Complexity: Often simple reads with time-based filtering and aggregations (non-complex data 
        transformation, joins, and aggregations).
    - Data Access (READ) Pattern: Sequential access to time-ordered data.
    - Insertion (WRITE) Pattern: Append-only; constant insertion of new, timestamped records; Continuous 
        or batch insertion of log entries.
    - Typical Usage: Monitoring IoT data, and system performance metrics. Log analysis, monitoring, 
        anomaly detection, and security event correlation.


# Business Workload
OLTP = 'oltp' (Online Transaction Processing)
    - Description: Traditional OLTP workload with frequent read and write operations.
    - Transaction Lifespan: Short-lived transactions (milliseconds to seconds).
    - Read/Write Balance: Balanced; often read-heavy but includes frequent writes.
    - Query Complexity: Simple read and write queries, usually targeting single rows or small subsets.
    - Data Access (READ) Pattern: Random access to small subsets of data.
    - Insertion (WRITE) Pattern: Constant insertion and updates, with high concurrency.
    - Typical Usage: Applications like banking, e-commerce, and CRM where data changes frequently.

HTAP = 'htap' (Hybrid Transactional/Analytical Processing)
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

# Specific Workload such as Search, RAG, Geospatial, and Document Indexing
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

 */
const PG_WORKLOAD = Object.freeze({
    TSR_IOT: "tst",
    OLTP: "oltp",
    HTAP: "htap",
    OLAP: "olap",
    VECTOR: "vector",
});

export default PG_WORKLOAD;