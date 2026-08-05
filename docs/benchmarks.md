# VoiceBridge AI — Performance Benchmarking & Load Testing Guide

## Overview

VoiceBridge AI includes automated CLI and programmatic benchmarking tools to measure latency percentiles (P50, P95, P99), throughput (requests/sec), token generation speed, and real-time factors (RTF).

---

## Running Benchmarks

### Automated Benchmark Suite
```bash
python -m voicebridge benchmark
```
Outputs report files in `logs/reports/` (`.md`, `.json`, `.csv`).

---

## Load Testing

Use `ConcurrentLoadTester` to simulate high-concurrency user streams:

```python
from voicebridge.benchmarks.load_tester import ConcurrentLoadTester

tester = ConcurrentLoadTester()
results = tester.run_load_test(num_concurrent_users=20, requests_per_user=10)
print("P95 Latency:", results["latency_p95_ms"])
print("Throughput:", results["throughput_req_per_sec"])
```

---

## Key Performance Indicators (KPIs)

- **End-to-End Latency P95**: Target ≤ 1000 ms in Fast tier, ≤ 1500 ms in Balanced tier.
- **Throughput**: Target ≥ 50 requests/sec under burst capacity.
- **Error Rate**: Target < 0.1% with automatic fallback enabled.
