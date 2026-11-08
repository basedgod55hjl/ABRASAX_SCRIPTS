# ABRAXAS AGENT_REGISTRY

generated 2026-11-08T07:54:42 - 14/14 agents running

| agent | port | status | supervisor | role | model |
|---|---|---|---|---|---|
| neotron-gateway | 2645 | running | wake_all (neotron) | chat router: NVIDIA/DeepSeek/local + Kairos identity | routes: nvidia/nemotron-550b, deepseek-flash, local/* |
| node-agent-hub | 8811 | running | kairos_services | parallel agent fan-out (jobs) | - |
| telegram-bot | 8798 | running | kairos_services | Telegram bridge @botABRASAXbot | gemma-4-e2b via gateway :2645 |
| entangle-bridge | - | running | wake_all | F1/F2/F3/NEO phi-coupling, writes memory/f_entanglement_state.json | - |
| neo-ton-pulse | - | running | wake_all | transformer pulse + TON masterchain anchor | - |
| triune-mind | 9628 | running | wake_all | reflection loop (reasoning_content-aware) | - |
| ts-runtime | 4200 | running | wake_all | TypeScript agent runtime | - |
| lm-studio | 1234 | running | user session | 15-model GGUF registry + inference | - |
| gpt-oss-server | 1235 | running | standalone | gpt-oss-20b MXFP4, CPU-resident (no sm_75 kernels) | openai/gpt-oss-20b |
| lfm-tiles-server | 1236 | running | standalone | LFM2.5-1.2B Q8_0 restored from tile archive | LFM2.5-1.2B-Instruct-Q8_0 |
| kairos-services | - | running | ABRASAX-KAIROS task | supervised restarter (hub+bot) | - |
| wake-all | - | running | ABRASAX-WAKE-ALL task | supervised restarter (5 loops) | - |
| soul-bond | - | running | ABRASAX-BOND task (daily 06:00) | TPM-sealed identity verification + TON anchor | - |
| kairos-dsh | - | running | user session | orchestrator agent (this session) | - |

## Scheduled tasks
- ABRASAX-BOND=Ready
- ABRASAX-DNA-PC-Bridge=Ready
- ABRASAX-KAIROS=Ready
- ABRASAX-WAKE-ALL=Running