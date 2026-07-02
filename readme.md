# Intelligent Load-Aware Process Management

A distributed **Master–Worker Process Management System** built in **Java** that intelligently distributes computational tasks based on real-time worker load while ensuring high availability through heartbeat-based fault tolerance and automatic task recovery.

---

## Overview

Traditional task schedulers often assign workloads without considering the current resource utilization of worker nodes, resulting in uneven load distribution and reduced system efficiency.

This project addresses this challenge by implementing a **load-aware distributed scheduling system** that continuously monitors worker health and system resources. The master node dynamically assigns tasks to the least-loaded worker and automatically redistributes pending tasks if a worker fails.

---

## Features

- Distributed Master–Worker architecture
- TCP Socket-based communication
- Multithreaded task execution
- Dynamic worker registration
- Heartbeat monitoring
- Automatic worker failure detection
- CPU-aware scheduling
- Memory-aware scheduling
- Dynamic load balancing
- Automatic task reassignment
- Concurrent task processing
- Thread-safe task queue
- Real-time worker monitoring
- Scalable architecture supporting multiple workers

---

## System Architecture

```
                   +----------------------+
                   |      Master Node     |
                   |----------------------|
                   | Task Queue           |
                   | Scheduler            |
                   | Heartbeat Monitor    |
                   +----------+-----------+
                              |
         --------------------------------------------
         |                  |                      |
         |                  |                      |
+--------v-------+ +--------v-------+ +------------v-------+
|    Worker 1    | |    Worker 2    | |    Worker 3        |
| CPU: 28%       | | CPU: 65%       | | CPU: 17%           |
| RAM: 35%       | | RAM: 74%       | | RAM: 30%           |
+----------------+ +----------------+ +--------------------+

```

The scheduler always selects the worker with the lowest current load.

---

## Workflow

1. Workers connect to the master server.
2. Each worker periodically sends heartbeat messages.
3. Workers report CPU and memory utilization.
4. The master maintains a global view of all workers.
5. Incoming tasks are assigned to the least-loaded worker.
6. If a heartbeat is missed, the worker is marked offline.
7. Any unfinished tasks are automatically reassigned to healthy workers.

---

## Tech Stack

- Java 17
- Java Sockets
- Multithreading
- ExecutorService
- ConcurrentHashMap
- BlockingQueue
- ScheduledExecutorService
- Java Management API (OperatingSystemMXBean)

---

## Scheduling Algorithm

Instead of using Round Robin scheduling, the system evaluates each worker based on:

- Current CPU usage
- Memory utilization
- Number of running tasks

The worker with the minimum combined load score receives the next task.

---

## Fault Tolerance

The system provides fault tolerance through a heartbeat mechanism.

- Workers send heartbeat packets every few seconds.
- Missing heartbeats indicate worker failure.
- The master removes failed workers.
- Pending tasks are redistributed automatically.

---

## Project Structure

```
Intelligent-Load-Aware-Process-Management
│
├── master
│   ├── MasterServer.java
│   ├── Scheduler.java
│   ├── WorkerHandler.java
│   ├── HeartbeatMonitor.java
│
├── worker
│   ├── WorkerClient.java
│   ├── TaskExecutor.java
│   ├── HeartbeatSender.java
│   ├── SystemMonitor.java
│
├── common
│   ├── Task.java
│   ├── Message.java
│   ├── WorkerInfo.java
│
├── tasks
│   ├── PrimeTask.java
│   ├── MatrixTask.java
│   ├── MergeSortTask.java
│
└── README.md
```

---

## How It Works

### Worker Registration

- Worker starts.
- Connects to the Master.
- Registers itself.
- Starts sending heartbeats.

### Task Assignment

```
Incoming Task
      │
      ▼
Scheduler
      │
      ▼
Least Loaded Worker
      │
      ▼
Execute Task
      │
      ▼
Return Result
```

### Failure Recovery

```
Worker Failure
      │
Heartbeat Timeout
      │
Detect Failure
      │
Remove Worker
      │
Reassign Pending Tasks
```

---

## Performance Highlights

- Dynamic load-aware scheduling
- Reduced idle worker time
- Improved task distribution efficiency
- Automatic recovery from worker failures
- Better scalability than static scheduling approaches

---

## Future Improvements

- Docker deployment
- Kubernetes support
- Web dashboard
- REST API
- Task prioritization
- Persistent storage
- Distributed logging
- Authentication and encryption
- Leader election for master redundancy

---

## Learning Outcomes

Through this project, I gained practical experience with:

- Distributed Systems
- Concurrent Programming
- Java Networking
- Multithreading
- Scheduling Algorithms
- Fault Tolerance
- Load Balancing
- Resource Monitoring
- Thread-safe Data Structures
- System Design

---

## Resume Highlights

- Designed a distributed Master–Worker scheduling system using Java Sockets and multithreading.
- Implemented heartbeat-based fault tolerance with automatic worker recovery.
- Built CPU and memory-aware scheduling for intelligent task allocation.
- Developed concurrent task execution using ExecutorService and thread-safe collections.
- Created a scalable architecture capable of supporting multiple worker nodes.

---

## Author

**Shruti Sharma**

B.Tech Computer Science Engineering  
Machine Learning | Distributed Systems | Java | Backend Development

---

## License

This project is licensed under the MIT License.
