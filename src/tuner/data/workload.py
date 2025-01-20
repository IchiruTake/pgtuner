from enum import Enum

__all__ = ["PG_WORKLOAD"]


class PG_WORKLOAD(str, Enum):
    """
    This enum represents some typical workloads or usage patterns that can be used to tune the database.
    Options:
    -------

    # End-user Workload or Simple Workload
    SOLTP = 'soltp' (Single-User or Simple OLTP)
        - Transaction Lifespan: Short-lived transactions (milliseconds to seconds).
        - Read/Write Balance: Balanced; often read-heavy but includes frequent writes.
        - Query Complexity: Simple read and write queries, usually targeting single rows or small subsets. These
            queries are usually simple and straightforward, never make full table scan or transformation.
        - Data Access Pattern: Random access to small subsets of data.
        - Insertion Pattern: Constant insertion and updates, with high concurrency.
        - Typical Usage: Applications like banking, e-commerce, and CRM where data changes frequently.
        - Example: A simple e-commerce website that allows users to browse products, add items to a shopping cart,
            and check out.

    LOG = 'log' (Log Data Processing)
        - Transaction Lifespan: Varies based on log volume
        - Read/Write Balance: Heavy writes for log ingestion.
        - Query Complexity: Simple
        - Data Access Pattern: Sequential access to log entries, often with time-based filtering.
        - Insertion Pattern: Continuous or batch insertion of log entries.
        - Typical Usage: Log analysis, monitoring, anomaly detection, and security event correlation.

    TSR_IOT = 'tst' (Time-Series Data / Streaming)
        - Transaction Lifespan: Short-lived transactions optimized for high frequency for IoT data.
        - Read/Write Balance: Heavy-write with frequent time-stamped data points.
        - Query Complexity: Often simple reads with time-based filtering and aggregations.
        - Data Access Pattern: Sequential access to time-ordered data.
        - Insertion Pattern: Append-only; constant insertion of new, timestamped records.
        - Typical Usage: Monitoring IoT data, and system performance metrics.

    # Business Workload
    OLTP = 'oltp' (Online Transaction Processing)
        - Transaction Lifespan: Short-lived transactions (milliseconds to seconds).
        - Read/Write Balance: Balanced; often read-heavy but includes frequent writes.
        - Query Complexity: Simple read and write queries, usually targeting single rows or small subsets.
        - Data Access Pattern: Random access to small subsets of data.
        - Insertion Pattern: Constant insertion and updates, with high concurrency.
        - Typical Usage: Applications like banking, e-commerce, and CRM where data changes frequently.

    HTAP = 'htap' (Hybrid Transactional/Analytical Processing)
    TSR_HTAP = 'tsh' (Time-Series HTAP)
        - Transaction Lifespan: Mix of short transactional and long analytical queries.
        - Read/Write Balance: Balances frequent writes (OLTP) with complex reads (OLAP).
        - Query Complexity: Simple transactional queries along with complex analytical queries.
        - Data Access Pattern: Random access for OLTP and sequential access for OLAP.
        - Insertion Pattern: Real-time or near real-time inserts, often through streaming or continuous updates.
        - Typical Usage: Real-time dashboards, fraud detection where operational and historical data are combined.

    # Internal Management Workload
    OLAP = 'olap' (Online Analytical Processing)
    TSR_OLAP = 'tsa' (Time-Series Data Analytics)
        - Transaction Lifespan: Long-lived, complex queries (seconds to minutes).
        - Read/Write Balance: Read-heavy; few updates or inserts after initial loading.
        - Query Complexity: Complex read queries with aggregations, joins, and large scans.
        - Data Access Pattern: Sequential access to large data sets.
        - Insertion Pattern: Bulk insertion during ETL processes, usually at scheduled intervals.
        - Typical Usage: Business analytics and reporting where large data volumes are analyzed.

    DATA_WAREHOUSE = 'dw' (Data Warehouse)
        - Transaction Lifespan: Long-lived queries (minutes to hours).
        - Read/Write Balance: Primarily read-heavy; writes are usually batch-loaded.
        - Query Complexity: Very complex reads, aggregations, and data transformations.
        - Data Access Pattern: Sequential access to large data sets.
        - Insertion Pattern: Bulk insertion of data at regular intervals (daily, weekly, etc.).
        - Typical Usage: Historical data analysis and trend reporting across large datasets.

    DATA_LAKE = 'dl' (Data Lake)
        - Transaction Lifespan: N/A for structured transactions; often batch-oriented.
        - Read/Write Balance: Depends on analysis needs, but generally balanced.
        - Query Complexity: Varies; can support both complex and simple queries on raw data.
        - Data Access Pattern: Random or sequential access to raw or semi-structured data.
        - Insertion Pattern: Bulk insertion of raw, unstructured, or semi-structured data.
        - Typical Usage: Exploratory analysis, data science, and large-scale storage for machine learning pipelines.

    # Specific Workload such as Search, RAG, Geospatial. Whilst these workloads are different in query complexity,
    # and business requirements; they share some similar characteristics in terms of data access patterns and insertion
    # patterns. These workloads are not risked from data integrity since they inserted once and read *many* times.
    # If they are used by end-users, additional latency requirements should be considered.
    SEARCH = 'search' (Search and Indexing). Usually the text-based search engine.
        - Transaction Lifespan: Fast, low-latency queries (sub-second).
        - Read/Write Balance: Read-heavy; writes are mainly index updates.
        - Query Complexity: Primarily focused on text-based retrieval and keyword searches.
        - Data Access Pattern: Random access to indexed data.
        - Insertion Pattern: Frequent index updates; bulk indexing possible for data ingestion.
        - Typical Usage: Full-text search in e-commerce, knowledge bases, and document search engines.

    RAG = 'rag' (Deep-Learning of Retrieval-Augmented Generation). Usually the vector-based search engine.
        - Transaction Lifespan: Varies, with a mix of short-lived and long-running queries.
        - Read/Write Balance: Generally read-heavy; writes focus on storing feature vectors on initial load.
        - Query Complexity: Complex, sometimes using vector search and similarity queries.
        - Data Access Pattern: Random access to feature vectors and embeddings.
        - Insertion Pattern: Bulk insertions for training datasets, some real-time updates for live models.
        - Typical Usage: Model training, feature extraction, and serving models in recommendation systems.

    GEOSPATIAL = 'geo' (Geospatial Workloads)
        - Transaction Lifespan: Varies based on query complexity.
        - Read/Write Balance: Read-heavy, with occasional writes for updating spatial data.
        - Query Complexity: Complex, involving spatial filtering, range queries, and distance calculations.
        - Insertion Pattern: Bulk or periodic insertion of geographic datasets.
        - Typical Usage: Location-based services, mapping, geographic data analysis, proximity searches.

    """
    # End-user Workload or Simple Workload
    SOLTP = 'soltp'
    LOG = 'log'
    TSR_IOT = 'tst'

    # Business Workload
    OLTP = 'oltp'
    HTAP = 'htap'
    TSR_HTAP = 'tsh'

    # Internal Management Workload
    OLAP = 'olap'
    DATA_WAREHOUSE = 'dw'
    DATA_LAKE = 'dl'
    TSR_OLAP = 'tsa'

    # Specific Workload
    SEARCH = 'search'
    RAG = 'rag'
    GEOSPATIAL = 'geo'
