# VoiceBridge AI Performance & Benchmark Report

## Executive Latency Summary

| Latency Metric | Execution Time (ms) |
| :--- | :--- |
| **Average E2E Latency** | 2032.00 ms |
| **Minimum Latency** | 982.00 ms |
| **Maximum Latency** | 5582.00 ms |
| **Median Latency** | 1752.00 ms |
| **95th Percentile (P95)** | 5582.00 ms |
| **Standard Deviation** | 1274.28 ms |

## Pipeline Stage Breakdown

| Pipeline Stage | Average Latency (ms) | Percentage |
| :--- | :--- | :--- |
| Audio Capture | 19.40 ms | 1.0% |
| VAD | 24.70 ms | 1.2% |
| STT | 655.50 ms | 32.3% |
| Sentence Buffer | 11.40 ms | 0.6% |
| Translation | 75.50 ms | 3.7% |
| TTS | 361.50 ms | 17.8% |
| Lip Sync | 869.00 ms | 42.8% |
| Playback | 15.00 ms | 0.7% |

## Throughput & Lip-Sync Metrics

- **Requests per Second (RPS)**: 10.000
- **Sentences Processed / Minute**: 600.00
- **Audio Minutes Processed / Minute**: 190.00
- **Average Lip-Sync FPS**: 25.00 FPS (Min: 25.0, Max: 25.0)

## Hardware Resource Utilization

- **CPU Usage**: Current 48.0% | Avg 24.0% | Peak 48.0%
- **RAM Usage**: Current 256.7 MB | Peak 256.7 MB | Growth 55.3 MB
- **VRAM Usage**: 0.0 MB
- **Disk Storage**: Temp 0.49 MB | Generated Speech 0.06 MB

## Bottleneck Analysis & Optimization Recommendations

> **Primary Bottleneck**: `Lip Sync` (869.0 ms, 42.8% of total pipeline latency)

### Recommendations:
- Total end-to-end latency exceeds 2.0s. Run VoiceBridge with GPU hardware or enable concurrent chunk processing.