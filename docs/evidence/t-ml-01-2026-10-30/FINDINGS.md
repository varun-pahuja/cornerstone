# T-ML-01 diagnostic findings — 2026-10-30 (single bounded run)

Instrument: **gdb batch mode** (strace not installed and sudo unavailable — gdb
substituted to report the terminating signal; documented limitation). True exit
status captured with **no pipeline masking** (`exit_status.txt`). Exactly one run
was performed; it was not repeated after failure.

## Artifacts

| File | Contents |
|---|---|
| `probe_stream.py` | Reproduces the known-dying probe shape (stream frames → extract every 5th, flush per extraction) |
| `gdb_run.log` | Full gdb + probe output |
| `exit_status.txt` | `gdb_exit=1` (gdb batch return with `-return-child-result`) |

## Result

```
extract n=7 idx=30 hand=N rss_mb=389 elapsed_s=3.18
Program terminated with signal SIGKILL, Killed.
The program no longer exists.
=== AFTER RUN ===
The program being debugged is not being run.
No stack.
```

### Verdict

- **Failure mode: SIGKILL (signal 9) delivered to the process.** Not a native
  abort (no SIGABRT), not a segfault, not a Python exception. No stack exists
  because the process was killed outright.
- **Kernel OOM killer ruled out:**
  - `journalctl -k --since 2026-10-27 | grep -icE "oom|killed process"` → **0**
  - cgroup `memory.max = max`, `memory.events: oom_kill 0` (`app-code-1386.scope`)
  - RSS flat at death (389 MB this run; 563→566 MB in probe 4)
- **No core dump** (`coredumpctl` has no entry for today — expected for SIGKILL).
- **Timing pattern across all probes:** death occurs **~3.0–3.3 s after the
  extraction loop starts**, while the only surviving run (probe 1, 4 extractions)
  finished at 2.9 s. Extraction count at death varies (4 / 6 / 7 / 21–24) —
  inconsistent with a per-frame leak or fixed-count bug, consistent with a
  wall-clock-triggered **external** killer.
- Upstream MediaPipe GPU-leak issues (#5652 / #5626) do **not** match: RSS is
  flat, and the OOM path is excluded.

### What remains unknown

The **identity of the killer** (which process sends SIGKILL at ~3 s). Naming it
requires root-level tracing (`bpftrace`/`auditd`/`strace -f` on the whole scope),
which is not available in this environment without a sudo password.

### Constraints observed

- No speculative code or system changes were made.
- The experiment was not repeated after this run.

## Addendum 2026-10-30 23:5x — GPU delegate also killed (post-training)

With the trained model installed (`ae19271b2b19`) and the default GPU delegate
selected, extraction on a test clip produced:

```
I0000 gl_context_egl.cc:113] Successfully initialized EGL. Major: 1 Minor: 5
I0000 gl_context.cc:408] GL version: 3.2 (OpenGL ES 3.2 Mesa 26.2.5-arch1.1),
      renderer: Mesa Intel(R) Graphics (RPL-P)
... Killed          (shell exit 137)
```

So the kill is **not delegate-specific**: the GPU path boots fine (EGL + GL
context created) and the process is still SIGKILLed before the first frame.
Both CPU and GPU delegates are killed on this host.

Consequences:
- Local (laptop) inference is impossible until the killer is identified.
- Colab CPU delegate works (gate passed, 126/128 clips trained, held-out test
  accuracy 0.944). Colab is the only known-good extraction host.
- Root-cause work still requires root-level tracing (no sudo available).
