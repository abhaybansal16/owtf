"""
Benchmark: Priority Scheduler vs FIFO ordering

Compares task ordering between the old FIFO approach (order by Work.id)
and the new priority-based approach (order by priority_score DESC).

Run inside the container:
    python tests/benchmarks/scheduler_benchmark.py
"""
import time
from owtf.managers.scheduler import compute_score

# Simulate a realistic mix of plugin tasks
SAMPLE_PLUGINS = [
    {"type": "passive", "code": "OWTF-IG-001", "group": "web", "title": "Spiders Robots Crawlers"},
    {"type": "external", "code": "OWTF-AJ-001", "group": "web", "title": "Ajax Vulnerabilities"},
    {"type": "passive", "code": "OWTF-DV-005", "group": "web", "title": "SQL Injection"},
    {"type": "active",  "code": "OWTF-WVS-002", "group": "web", "title": "Nikto Unauthenticated"},
    {"type": "grep",    "code": "OWTF-CM-001", "group": "web", "title": "SSL/TLS"},
    {"type": "passive", "code": "OWTF-DV-001", "group": "web", "title": "Reflected XSS"},
    {"type": "active",  "code": "OWTF-ST-001", "group": "web", "title": "Subdomain Takeover"},
    {"type": "active",  "code": "OWTF-CM-003", "group": "web", "title": "Infra Config Management"},
    {"type": "passive", "code": "OWTF-DV-013", "group": "web", "title": "Command Injection"},
    {"type": "external","code": "OWTF-DV-003", "group": "web", "title": "DOM XSS"},
    {"type": "semi_passive", "code": "OWTF-IG-002", "group": "web", "title": "Search Engine Recon"},
    {"type": "active",  "code": "OWTF-CL-002", "group": "web", "title": "Open GCP Buckets"},
]

SAMPLE_TARGETS = [
    {"user_priority": 1, "target_url": "http://payment.example.com"},
    {"user_priority": 2, "target_url": "http://api.example.com"},
    {"user_priority": 4, "target_url": "http://static.example.com"},
]


def fifo_order(plugins, targets):
    """Simulate old FIFO — insertion order, no priority."""
    tasks = []
    for target in targets:
        for plugin in plugins:
            tasks.append((plugin, target, 0.0))  # score always 0
    return tasks


def priority_order(plugins, targets):
    """New priority order — score each task and sort descending."""
    tasks = []
    for target in targets:
        for plugin in plugins:
            score = compute_score(plugin, target)
            tasks.append((plugin, target, score))
    tasks.sort(key=lambda x: (-x[2], id(x[0])))
    return tasks


def run_benchmark():
    print("\n" + "="*60)
    print("OWTF Scheduler Benchmark: Priority vs FIFO")
    print("="*60)

    n_runs = 1000

    # Benchmark FIFO
    start = time.perf_counter()
    for _ in range(n_runs):
        fifo_order(SAMPLE_PLUGINS, SAMPLE_TARGETS)
    fifo_time = time.perf_counter() - start

    # Benchmark Priority
    start = time.perf_counter()
    for _ in range(n_runs):
        priority_order(SAMPLE_PLUGINS, SAMPLE_TARGETS)
    priority_time = time.perf_counter() - start

    print(f"\nTasks per run : {len(SAMPLE_PLUGINS) * len(SAMPLE_TARGETS)}")
    print(f"Runs          : {n_runs}")
    print(f"\nFIFO time     : {fifo_time*1000:.2f}ms total / {fifo_time/n_runs*1000:.3f}ms per run")
    print(f"Priority time : {priority_time*1000:.2f}ms total / {priority_time/n_runs*1000:.3f}ms per run")

    print("\n" + "-"*60)
    print("FIFO order (first 5 tasks):")
    fifo = fifo_order(SAMPLE_PLUGINS, SAMPLE_TARGETS)
    for plugin, target, score in fifo[:5]:
        print(f"  score={score:.1f} | {plugin['type']:12} | {plugin['title']} | {target['target_url']}")

    print("\nPriority order (first 5 tasks):")
    priority = priority_order(SAMPLE_PLUGINS, SAMPLE_TARGETS)
    for plugin, target, score in priority[:5]:
        print(f"  score={score:.1f} | {plugin['type']:12} | {plugin['title']} | {target['target_url']}")

    print("\n" + "-"*60)
    print("Key improvement: Priority scheduler runs high-value tasks first.")
    print("Critical target + high risk plugins surface immediately.")
    print("="*60 + "\n")


if __name__ == "__main__":
    run_benchmark()