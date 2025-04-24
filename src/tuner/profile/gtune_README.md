## General-Tuning Module

This module contains some instruction profiles for tuning the PostgreSQL server. For the networking management, whilst
the Linux server handles at maximum 2^16-1 connections, we capped our server to only serve at max 100 connections, and
probably at most 10-25 additional connections for other purposes. This is to prevent the server from being overwhelmed
by the number of connections, and to prevent the server from being a target of a DDoS attack. And the additional
connections are for the server to handle other services, administrative tasks, troubleshooting, and monitoring. But
during the tuning process, the maximum number of connections allowed is usually above the magic number and we keep
it by default. The magic number means that this is the average value and we used it for tuning.

Note that this file is capable of performing the general tuning without acknowledging the type of server workload.
For the specific tuning based on workload, please refer to the `stune`.py. The tuning is inspired which is
not limited to other types of database such as SQL Server

References for SYSCTL tuning:
[01] https://gitlab.melroy.org/-/snippets/609
[02] https://easyengine.io/tutorials/linux/sysctl-conf/
[03] https://www.kernel.org/doc/Documentation/sysctl/kernel.txt
[04] https://www.kernel.org/doc/Documentation/sysctl/net.txt
[05] https://www.kernel.org/doc/Documentation/sysctl/fs.txt
[06] https://portal.perforce.com/s/article/Tune-Linux-Kernel-TCP-IP-Settings
[07] https://blog.confirm.ch/sysctl-tuning-linux/
[08] https://enterprise-support.nvidia.com/s/article/linux-sysctl-tuning
[09] https://cloud.google.com/compute/docs/networking/tcp-optimization-for-network-performance-in-gcp-and-hybrid
[10] https://www.notion.so/blog/sharding-postgres-at-notion
[11] https://www.notion.so/blog/the-great-re-shard
[12] https://blog.cloudflare.com/optimizing-tcp-for-high-throughput-and-low-latency/
[13] https://lwn.net/Articles/560082/
[14] https://stackoverflow.com/questions/7880383/what-benefit-is-conferred-by-tcp-timestamp
[15] https://www.phoronix.com/review/linux-59-unfairness
[16] https://learn.microsoft.com/en-us/sql/linux/sql-server-linux-performance-best-practices?view=sql-server-ver16
[17] https://blog.cloudflare.com/unbounded-memory-usage-by-tcp-for-receive-buffers-and-how-we-fixed-it/ (Extended
of [12])
[18] https://access.redhat.com/solutions/29455

References for PostgreSQL tuning:
[01] https://gitlab.melroy.org/-/snippets/610
[02] https://vladmihalcea.com/postgresql-performance-tuning-settings/
[03] https://developer.radiantlogic.com/ia/descartes/best-practice/02-databases/01-postgres-recommendations/
[04] https://sematext.com/blog/postgresql-performance-tuning/
[05] https://www.timescale.com/learn/postgresql-performance-tuning-key-parameters
[06] https://github.com/brettwooldridge/HikariCP/wiki/About-Pool-Sizing
[07] https://www.enterprisedb.com/blog/autovacuum-tuning-basics
[08] https://www.postgresql.org/docs/17/runtime-config-autovacuum.html
[09] https://tembo.io/blog/optimizing-postgres-auto-vacuum
[10] https://www.percona.com/blog/tuning-autovacuum-in-postgresql-and-autovacuum-internals/
[11] https://www.percona.com/blog/importance-of-postgresql-vacuum-tuning-and-custom-scheduled-vacuum-job/
[12] https://postgresqlco.nf/doc/en/param/vacuum_cost_delay/
[13] https://www.postgresql.org/docs/current/wal-configuration.html
[14] https://www.postgresql.org/docs/current/runtime-config-wal.html
[15] https://www.cybertec-postgresql.com/en/lz4-zstd-pg_dump-compression-postgresql-16/
[16] https://demirhuseyinn-94.medium.com/optimizing-postgresql-performance-the-impact-of-adjusting-commit-delay-and-wal-writer-delay-0f4dd0402cca
[17] https://www.postgresql.org/docs/current/wal-async-commit.html
[18] https://www.postgresql.org/docs/17/warm-standby.html
[19] https://www.postgresql.org/docs/current/logical-replication.html
[20] https://www.enterprisedb.com/blog/basics-tuning-checkpoints
[21] https://www.youtube.com/watch?v=t8rAOgDdH1U at 14:30
[22] https://thewordtim5times.com/blog/7
[23] https://learn.microsoft.com/en-us/azure/postgresql/flexible-server/server-parameters-table-write-ahead-log-checkpoints?pivots=postgresql-16
[24] https://docs.aws.amazon.com/prescriptive-guidance/latest/tuning-postgresql-parameters/replication-parameters.html
[25] https://gist.github.com/LeonStoldt/e317d7c925ea612532c14d2dfdf956cc -> https://www.enterprisedb.com/postgres-tutorials/introduction-postgresql-performance-tuning-and-optimization
[26] https://www.youtube.com/watch?v=D832gi8Qrv4
[27] https://www.postgresql.org/message-id/flat/CA%2BTgmoZuay5Bjwau6ef_0ODGRUVGkFfgdBr_5hX9PZoD-F0Z%3DA%40mail.gmail.com#34eda5bdbcb23cdc85698b2303296075
tune for commit_delay and commit_siblings
[28] https://wiki.postgresql.org/wiki/Tuning_Your_PostgreSQL_Server#shared_buffers
[29] https://www.timescale.com/learn/best-practices-for-postgres-database-replication
[30] https://www.postgresql.org/message-id/flat/20190701233215.wdimoypumnshwbl5%40alap3.anarazel.de#665f7839875a7b58a2cb37a5434acd33
[31] https://www.postgresql.org/message-id/flat/20210422201506.GF7256%40telsasoft.com#93f4777070c9599b74e059ff7298e41c
[32] https://www.postgresql.org/message-id/flat/PR3PR07MB8243BF26FFD94590F30BAB92F6A59%40PR3PR07MB8243.eurprd07.prod.outlook.com#f7bfc61929bba8016e9c149c0f9a3e6f
[33] https://www.youtube.com/watch?v=i_91jNrRYWk
[34] https://www.youtube.com/watch?v=3v-cthowG10
[35] https://www.enterprisedb.com/postgres-tutorials/when-parallel-sequential-scan-does-not-improve-performance-postgres
[36] https://www.enterprisedb.com/postgres-tutorials/postgresql-replication-and-automatic-failover-tutorial
[37] https://www.timescale.com/forum/t/what-is-recommended-wal-segment-size-parameter-for-timescaledb/2712/3
[38] https://postgrespro.com/list/thread-id/1898949
[39] https://www.bytebase.com/blog/postgres-timeout/
[40] https://www.enterprisedb.com/blog/managing-freezing-postgresql

Questions:

1. Why you don't tune the hugepages?
   -> Not all workload are required hugepages to be performant, as it would load large amount of data into RAM, which
   can be a potential security for RAM scraping attacks. Also, there are several database strategies you can exploit
   outside such as partition/sharding, scaling, and caching. See
   here https://wiki.postgresql.org/images/7/7d/PostgreSQL_and_Huge_pages_-_PGConf.2019.pdf

2. How the TCP tuning is applied?
   -> We just follow the Cloudflare setting and re-work to suit the database instead of traffic handling. Reference
   at [12], [17], [18]

3. I heard that we use small value of max_connections for the database server (as an idle connection is costs 5-10 MiB).
   Why? Could we get better transaction throughput?
   -> See the [03], [04], and [06]; we rarely exceeded 100 maximum connections. By it means, we don't overload the CPU
   with too many active connections so we capped the maximum connections as 2 to 4 connections per physical CPU core (
   reserved connections is not mentioned in here) and capped at 250 connections. The idle connection is not free, it
   costs 5 - 10 MiB and if we limit the right way, not only we prevent deadlock on I/O (disk), network, CPU
   under-utilization, but also prevent the server from being a target of DDoS attack. The additional connections are for
   the server to handle

4. Why we tune temp_buffers differently?
   -> Some online documentation think of making the temp_buffers using default value (8 MiB) is enough, but it is not
   valid for most of the cases. Here is the document: "Sets the maximum amount of memory used for temporary buffers
   within each database session. These are session-local buffers used only for access to temporary tables. The default
   is eight megabytes (8MB). This setting can be changed within individual sessions, but only before the first use of
   temporary tables within the session; subsequent attempts to change the value will have no effect on that session."
   -> So by the definition, there are some temporary tables use-case for example, table minimization before joining,
   value re-calculation and temporary data storage. While most queries on OLTP does not require the use of temporary
   tables, some OLAP/HTAP queries and administrative/monitoring/management queries may require the use of temporary
   tables. So the stretch is more of the temp_buffers over work_mem.

5. How we tune the VACUUM/ANALYZE and AUTOVACUUM/AUTOANALYZE?
   -> We just follow the PostgreSQL documentation at [07] and [08]. Whilst the best setting could be applied based on
   your table sizing with custom setting, according to my experience and [08]: "In practice, we almost never use this
   feature, and we recommend not using it. It makes the cleanup behavior much harder to predict and reason about -
   having multiple workers that are sometimes throttled together and sometimes independently makes this very complex.
   You probably want to use a single global limit on the background cleanup."
   -> For the information, the cleanup is triggered whenever the number of dead rows for a table (which you can see as
   pg_stat_all_tables.n_dead_tup) exceeds 'threshold + pg_class.relrows * scale_factor'
   -> For INSERT and ANALYZE, the work is done less frequent than the UPDATE and DELETE. The tuning meant that cleaning
   dead tuples, but don't run pre-maturely. The good value is 1000 + 1% so that for small table the 1000 will dominate
   the decision, for large tables the 1% scale factor will matter more.

6. Why we prefer to use the ZSTD over LZ4 for pg_dump compression?
   -> The ZSTD is a modern compression algorithm that is faster than LZ4 and has a better compression ratio. The ZSTD
   compression algorithm is used on various workloads, and PostgreSQL starts to add its support on version 15, and it is
   added on multiple operations such as WAL archiving (full-page-write-8K), pg_dump, and pg_basebackup. However, the
   default of compression level is still under debate whether the level should be best (1, 3, 6, ...) as it has a
   trade-off between the compression ratio and the speed. For the easiest solution, we just use the default level 3.

7. Why you opt for asynchronous commit by adjusting the wal_writer_delay and commit_delay?
   -> Actually, by PostgreSQL docs (ref [17]) "asynchronous commit is a good way to improve the performance of the
   database server, at the cost that the most recent transactions may be lost if the database should crash. In many
   applications this is an acceptable trade-off. As described in the previous section, transaction commit is normally
   synchronous: the server waits for the transaction's WAL records to be flushed to permanent storage before returning a
   success indication to the client. The client is therefore guaranteed that a transaction reported to be committed will
   be preserved, even in the event of a server crash immediately after. However, for short transactions this delay is a
   major component of the total transaction time. Selecting asynchronous commit mode means that the server returns
   success as soon as the transaction is logically completed, before the WAL records it generated have actually made
   their way to disk. This can provide a significant boost in throughput for small transactions."
   -> Meanwhile, by PostgreSQL docs (ref [17]) ":var:`commit_delay` also sounds very similar to asynchronous commit, but
   it is actually a synchronous commit method (in fact, :var:`commit_delay` is ignored during an asynchronous commit).
   var:`commit_delay` causes a delay just before a transaction flushes WAL to disk, in the hope that a single flush
   executed by one such transaction can also serve other transactions committing at about the same time. The setting can
   be thought of as a way of increasing the time window in which transactions can join a group about to participate in a
   single flush, to amortize the cost of the flush among multiple transactions."
   -> Based on that we would addd a small amount of commit_delay in the hope of bringing batch of small transactions
   better throughput.

8. How we tune the checkpoint?
   -> Based on our learning, the PostgreSQL checkpoint is a time-based process rather than the WAL-size based process.
   For example, the :var:`checkpoint_timeout` is the maximum time between automatic WAL checkpoints (which meant that
   for the value of 5 minutes meant that any transaction attempt on the database is written on buffer rather than on WAL
   durable storage (flushed to disk) within 5 minutes). Whilst 5 minutes value is attempted to be a good value for
   critical database, it is not common as the normal RTO scenario (a more common value is typically 15 to 30 minutes, up
   to 1 hour). Maximum value is 1 day. Increasing this parameter can increase the amount of time needed for crash
   recovery.

9. Why the tuning of commit_delay and commit_sibling is different from default setting?
   -> To me, as in the PostgreSQL mailing list (ref [27]), the setting are nealy hard to achieve due to the use of
   WALWriteLock which is an exclusive lock that could prevent these primary advantages. Second of all, since version
   9.2-9.3 up till 17 as now there are probably some changes back and forth, but these values are intended to support
   burst write from multiple clients or multiple transactions at the time with little impact of data integrity and bring
   minor performance boost. Also, a lot of Lock and stuffs are involved in this process, making it rare to achieve the
   conditions. However, looking at the result even with a minor change of commit_delay (not commit_siblings) could bring
   a non-negligible performance boost. However, a too large value (even when commit_siblings=0) would impact the data
   integrity due to a large commit write are not flushed into WAL storage.
   -> Also, please note that the commit_delay is triggered when equal or more than :var:`commit_siblings` transactions
   are waiting to commit and/or in execution. This is to help with the system with high I/O write rate into the durable
   storage and not wanting to flush with unpredictable, small, and overflow transactions.

10. Why that tuning of the pair shared_buffers and effective_cache_size?
    -> From the [28] reference, we can see it in the official PostgreSQL documentation and the tuning guide mentioned
    as "effective_cache_size: The setting for shared_buffers is not taken into account here - only the
    effective_cache_size value is, so it should include memory dedicated to the database too. Setting
    effective_cache_size to 1/2 of total memory would be a normal conservative setting, and 3/4 of memory is a more
    aggressive but still reasonable amount". Thus, it meant that our 95% of the remaining is still a great default
    setting.

11. Why you don't tune the transaction age related settings?
    -> In fact, those are actually more depending on your daily and bursting database workload. However, our tuning
    guideline is to make less database workload, but making it useful and efficient. Also, those number are actually
    good in general, unless specific workload is required, which could be changed by your business logic and end-user
    behaviour. We cannot predict all the workload possibility and guarantee it works for everyone else. In general, you
    should corporate multiple strategies such as partitioning, sharding, caching, and scaling, to distribute the
    database rather believe in a single setting.

12. How you tune the parallelism?
    -> I watch the videos at [33] and [34], articles at [35], and the official PostgreSQL documentation. The tuning is
    being done under their recommendation and Azure-related setting if have any. However, we only turn them on under the
    good condition where a possible performance uplift is achieved. The parallelism is not always good, as it could
    increase un-necessary CPU usage, memory, I/O usage.

13. How we managed the timeout?
    -> We refer some of these settings from the [39]. The timeout is a good way to prevent the database from being
    stalled and held by un-necessary deadlock. The setting value is very loose and could be adjusted based on your
    workload. However, the default value is good enough for most of the cases. But this is what we thought about it.
    -> For the transaction timeout, a scenario that could trigger this even we attempt to set this value high is under
    the pg_dump/pg_restore that start the dump (backup) and restore in transaction mode. The timeout could be passed,
    especially when the database is extremely large and we want full data integrity during backup, so we disable this
    option. However, from the application perspective, it is recommended to set this value to prevent un-necessary
    deadlock and stall. A good default value is 5 minutes for OLTP and 20-30 minutes for OLAP, DW. For statement timeout
    and lock timeout, similarly as it is applied for the trigger query (SELECT, INSERT, ...) **individually**. In normal
    query (SELECT, INSERT, UPDATE, and DELETE), we believe a good default value is varied but ranged at most 15 minutes;
    but for non-standard change such as ALTER, CREATE, DROP, TRUNCATE, and VACUUM, we believe a good default value is 1
    hour. Similarly for the lock timeout, whilst we believe it should be shorter than statement timeout, a good default
    value is 5 minutes for OLTP and 15 minutes for OLAP, DW. The lock timeout is a good way to prevent the database from
    being stalled and held by un-necessary deadlock. The setting value is very loose and could be adjusted based on your
    workload. However, the default value is good enough for most of the cases. But this is what we thought about it.
    -> For the lock timeout, we believe a good default value is 5 minutes for OLTP and 15 minutes for OLAP, DW. The lock
    timeout is a good way to prevent the database from being stalled and held by un-necessary deadlock. The setting
    value is very loose and could be adjusted based on your workload. However, the default value is good enough for most
    of the cases. But this is what we thought about it. For the transaction timeout, a scenario that could trigger this
    even we attempt to set this value high is under the pg_dump/pg_restore that start the dump (backup) and restore in
    transaction mode. The timeout could be passed, especially when the database is extremely large and we want full data
    integrity during backup, so we disable this option. However, from the application perspective, it is recommended to
    set this value to prevent un-necessary deadlock and stall. A good default value is 5 minutes for OLTP and 20-30
    minutes for OLAP, DW. For statement timeout and lock timeout, similarly as it is applied for the trigger query (
    SELECT, INSERT, ...) **individually**. In normal query (SELECT, INSERT, UPDATE, and DELETE), we believe a good
    default value is varied but ranged at most 15 minutes; but for non-standard change such as ALTER, CREATE, DROP,
    TRUNCATE, and VACUUM, we believe a good default value is 1 hour. For the lock timeout, we believe a good default
    value is 5 minutes for OLTP and 15 minutes for OLAP, DW. The lock timeout is a good way to prevent the database from
    being stalled and held by un-necessary deadlock. The setting value is very loose and could be adjusted based on your
    workload. However, the default value is good enough for most of the cases. But this is what we thought about it. For
    the transaction timeout, a scenario that could trigger this even we attempt to set this value high is under the
    pg_dump/pg_restore that start the dump (backup) and restore in transaction mode. The timeout could be passed,
    especially when the database is extremely large and we want full data integrity during backup, so we disable this
    option. However, from the application perspective, it is recommended to set this value to prevent un-necessary
    deadlock and stall. A good default value is 