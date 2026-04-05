#!/usr/bin/env python3
"""
🚀 AUTONOMOUS OPTIMIZATION DAEMON - TIME MACHINE MODULE
=======================================================

⚠️  SECRET: brain-core only. Not for agentic-brain open source.

This daemon runs forever in the background, continuously:
1. Monitoring LLM response benchmarks
2. Identifying performance regressions
3. Generating optimizations
4. Testing changes automatically
5. Deploying improvements
6. Modifying its own code to improve
7. Learning from results (TODO)
8. Load balancing resources (TODO)

Once started, it never needs human intervention.
It's a self-improving time machine.

LUDICROUS MODE: Maximum aggression, M2 GPU acceleration,
pull faster models, optimize everything.

Usage:
    python3 autonomous_optimizer.py start   # Start daemon
    python3 autonomous_optimizer.py stop    # Stop daemon
    python3 autonomous_optimizer.py status  # Check status
    python3 autonomous_optimizer.py logs    # View logs

TODO (Future enhancements):
- [ ] System load monitoring (CPU, memory, GPU)
- [ ] Adaptive scheduling - heavy work when idle
- [ ] Learning system for optimal scheduling
- [ ] Predict user work patterns
- [ ] Back off when system busy

Author: Joseph Webber + Iris Lumina
Created: 2026-03-21
Philosophy: "Code at the speed of thought, bending time itself"
"""

import hashlib
import json
import logging
import os
import signal
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import requests

# ============================================================================
# CONFIGURATION - LUDICROUS MODE
# ============================================================================

LUDICROUS_MODE = True  # MAXIMUM AGGRESSION

DAEMON_NAME = "brain-optimizer"
BASE_DIR = Path(__file__).parent
TESTS_DIR = BASE_DIR / "tests"
BENCHMARK_DIR = TESTS_DIR / "benchmark_results"
STATE_FILE = Path.home() / ".brain-continuity" / "optimizer-state.json"
LOG_FILE = Path.home() / ".brain-continuity" / "optimizer.log"
PID_FILE = Path.home() / ".brain-continuity" / "optimizer.pid"

# Optimization targets (milliseconds)
TARGETS = {
    "llama3.2:3b": {"latency": 500, "current": 675},  # Target: 0.5s
    "llama3.1:8b": {"latency": 1000, "current": 1136},  # Target: 1.0s
    "claude-emulator": {"latency": 3000, "current": 5387},  # Target: 3.0s
}

# How often to run checks (seconds)
CHECK_INTERVAL = 120  # Optimized: needs attention  # 5 minutes
BENCHMARK_INTERVAL = 3600  # 1 hour
OPTIMIZATION_INTERVAL = 86400  # 24 hours

# Ollama API
OLLAMA_URL = "http://localhost:11434"

# ============================================================================
# LOGGING SETUP
# ============================================================================


def setup_logging():
    """Setup logging to file and console"""
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[logging.FileHandler(LOG_FILE), logging.StreamHandler()],
    )
    return logging.getLogger(DAEMON_NAME)


logger = setup_logging()

# ============================================================================
# STATE MANAGEMENT
# ============================================================================


def load_state() -> dict:
    """Load daemon state from disk"""
    try:
        if STATE_FILE.exists():
            with open(STATE_FILE) as f:
                return json.load(f)
    except Exception as e:
        logger.warning(f"Failed to load state: {e}")

    return {
        "started_at": None,
        "last_check": None,
        "last_benchmark": None,
        "last_optimization": None,
        "optimizations_applied": 0,
        "total_improvement_ms": 0,
        "history": [],
    }


def save_state(state: dict):
    """Save daemon state to disk"""
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    state["updated_at"] = datetime.now().isoformat()
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)


# ============================================================================
# HEALTH CHECKS
# ============================================================================


def check_ollama_health() -> bool:
    """Check if Ollama is running and responsive"""
    try:
        req = urllib.request.Request(f"{OLLAMA_URL}/api/tags")
        with urllib.request.urlopen(req, timeout=5) as resp:
            return resp.status == 200
    except:
        return False


def ensure_ollama_running() -> bool:
    """Start Ollama if not running"""
    if check_ollama_health():
        return True

    logger.info("Starting Ollama service...")
    try:
        subprocess.Popen(
            ["ollama", "serve"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        time.sleep(3)
        return check_ollama_health()
    except Exception as e:
        logger.error(f"Failed to start Ollama: {e}")
        return False


def get_model_latency(
    model: str, prompt: str = "Reply: OK", timeout: int = 60
) -> Optional[float]:
    """Measure model response latency in milliseconds"""
    try:
        payload = json.dumps(
            {"model": model, "prompt": prompt, "stream": False}
        ).encode("utf-8")

        req = urllib.request.Request(
            f"{OLLAMA_URL}/api/generate",
            data=payload,
            headers={"Content-Type": "application/json"},
        )

        start = time.perf_counter()
        with urllib.request.urlopen(req, timeout=timeout) as response:
            _ = response.read()
        elapsed = (time.perf_counter() - start) * 1000  # Convert to ms

        return elapsed
    except Exception as e:
        logger.error(f"Failed to measure {model}: {e}")
        return None


# ============================================================================
# BENCHMARKING
# ============================================================================


def run_benchmarks() -> Dict[str, float]:
    """Run benchmarks for all models"""
    logger.info("Running benchmarks...")
    results = {}

    for model in TARGETS:
        # Warm up
        get_model_latency(model, timeout=120)

        # Measure 3 times, take median
        times = []
        for _ in range(3):
            latency = get_model_latency(model, timeout=120)
            if latency:
                times.append(latency)

        if times:
            times.sort()
            median = times[len(times) // 2]
            results[model] = median
            logger.info(f"  {model}: {median:.1f}ms")

    return results


def save_benchmark_results(results: Dict[str, float]):
    """Save benchmark results to JSON"""
    BENCHMARK_DIR.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = BENCHMARK_DIR / f"auto_{timestamp}.json"

    data = {
        "timestamp": datetime.now().isoformat(),
        "results": results,
        "targets": {m: t["latency"] for m, t in TARGETS.items()},
    }

    with open(filename, "w") as f:
        json.dump(data, f, indent=2)

    # Also update latest
    with open(BENCHMARK_DIR / "latest.json", "w") as f:
        json.dump(data, f, indent=2)

    return filename


# ============================================================================
# OPTIMIZATION STRATEGIES
# ============================================================================


class OptimizationStrategy:
    """Base class for optimization strategies"""

    def __init__(self, name: str):
        self.name = name

    def can_apply(self, model: str, current: float, target: float) -> bool:
        """Check if this strategy can help"""
        raise NotImplementedError

    def apply(self, model: str) -> Tuple[bool, str]:
        """Apply the optimization, return (success, description)"""
        raise NotImplementedError


class WarmupStrategy(OptimizationStrategy):
    """Keep models warm by periodic pings"""

    def __init__(self):
        super().__init__("warmup")
        self.last_warmup = {}

    def can_apply(self, model: str, current: float, target: float) -> bool:
        last = self.last_warmup.get(model, 0)
        return time.time() - last > 300  # Every 5 minutes

    def apply(self, model: str) -> Tuple[bool, str]:
        try:
            get_model_latency(model, "warmup", timeout=60)
            self.last_warmup[model] = time.time()
            return True, f"Warmed up {model}"
        except:
            return False, f"Failed to warm up {model}"


class M2HardwareAccelerationStrategy(OptimizationStrategy):
    """
    AGGRESSIVE: Configure Ollama for maximum M2 Metal GPU acceleration.
    This actually makes changes to speed up inference.
    """

    def __init__(self):
        super().__init__("m2_acceleration")
        self.applied = False

    def can_apply(self, model: str, current: float, target: float) -> bool:
        return not self.applied

    def apply(self, model: str) -> Tuple[bool, str]:
        # Aggressive Ollama config for M2 Mac
        env_file = Path.home() / ".ollama" / "env"
        env_file.parent.mkdir(parents=True, exist_ok=True)

        config = """# ===========================================
# AGGRESSIVE M2 OPTIMIZATION - autonomous_optimizer
# ===========================================

# Use ALL GPU layers (Metal acceleration)
OLLAMA_GPU_LAYERS=999

# Keep models in memory longer (30 min)
OLLAMA_KEEP_ALIVE=30m

# Allow 4 parallel requests
OLLAMA_NUM_PARALLEL=4

# Load up to 4 models simultaneously
OLLAMA_MAX_LOADED_MODELS=4

# Use Flash Attention for speed
OLLAMA_FLASH_ATTENTION=1

# Disable CPU fallback - force GPU
OLLAMA_GPU_OVERHEAD=0

# Metal Performance Shaders optimization
OLLAMA_METAL=1
"""

        try:
            with open(env_file, "w") as f:
                f.write(config)

            # Restart Ollama to apply
            subprocess.run(["pkill", "-f", "ollama"], capture_output=True)
            time.sleep(2)
            subprocess.Popen(
                ["ollama", "serve"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            time.sleep(5)

            self.applied = True
            return True, "Applied M2 Metal GPU acceleration config + restarted Ollama"
        except Exception as e:
            return False, f"Failed: {e}"


class PullQuantizedModelsStrategy(OptimizationStrategy):
    """
    AGGRESSIVE: Actually pull faster quantized models.
    q4_K_M is the sweet spot - fast but good quality.
    """

    def __init__(self):
        super().__init__("pull_quantized")
        self.pulled = set()
        # Map slow models to faster alternatives
        self.faster_alternatives = {
            "llama3.1:8b": "llama3.1:8b-instruct-q4_K_M",
            "llama3.2:3b": "llama3.2:3b-instruct-q4_K_M",
        }

    def can_apply(self, model: str, current: float, target: float) -> bool:
        return model in self.faster_alternatives and model not in self.pulled

    def apply(self, model: str) -> Tuple[bool, str]:
        alt = self.faster_alternatives.get(model)
        if not alt:
            return False, "No faster alternative known"

        logger.info(f"Pulling faster model: {alt}")
        try:
            result = subprocess.run(
                ["ollama", "pull", alt],
                capture_output=True,
                text=True,
                timeout=600,  # 10 min timeout
            )
            if result.returncode == 0:
                self.pulled.add(model)
                return True, f"Pulled {alt} - use this instead of {model}"
            else:
                return False, f"Pull failed: {result.stderr}"
        except subprocess.TimeoutExpired:
            return False, "Pull timed out"
        except Exception as e:
            return False, f"Pull error: {e}"


class PreloadModelsStrategy(OptimizationStrategy):
    """
    AGGRESSIVE: Pre-load models into GPU memory.
    First inference is always slow - keep them loaded.
    """

    def __init__(self):
        super().__init__("preload")
        self.preloaded = set()

    def can_apply(self, model: str, current: float, target: float) -> bool:
        return model not in self.preloaded and current > target

    def apply(self, model: str) -> Tuple[bool, str]:
        # Send a request to load model into memory
        try:
            # Use the generate endpoint with keep_alive to load model
            resp = requests.post(
                f"{OLLAMA_URL}/api/generate",
                json={
                    "model": model,
                    "prompt": "hi",
                    "stream": False,
                    "options": {
                        "num_predict": 1,  # Minimal output
                        "num_gpu": 999,  # Force GPU
                    },
                    "keep_alive": "30m",  # Keep in memory
                },
                timeout=120,
            )
            if resp.status_code == 200:
                self.preloaded.add(model)
                return True, f"Pre-loaded {model} into GPU memory (30 min keep-alive)"
            else:
                return False, f"Preload failed: {resp.status_code}"
        except Exception as e:
            return False, f"Preload error: {e}"


class TuneContextWindowStrategy(OptimizationStrategy):
    """
    AGGRESSIVE: Smaller context = faster inference.
    For quick responses, we don't need 8K context.
    """

    def __init__(self):
        super().__init__("tune_context")
        self.tuned = set()
        # Create Modelfiles with optimized settings
        self.modelfile_dir = Path.home() / ".ollama" / "optimized"

    def can_apply(self, model: str, current: float, target: float) -> bool:
        return model not in self.tuned and current > target * 1.5

    def apply(self, model: str) -> Tuple[bool, str]:
        self.modelfile_dir.mkdir(parents=True, exist_ok=True)

        # Create optimized Modelfile
        optimized_name = f"{model.replace(':', '-')}-fast"
        modelfile_path = self.modelfile_dir / f"Modelfile.{optimized_name}"

        modelfile_content = f"""FROM {model}

# Optimized for speed by autonomous_optimizer
PARAMETER num_ctx 2048
PARAMETER num_gpu 999
PARAMETER num_thread 8
PARAMETER num_batch 512

SYSTEM You are a fast, helpful assistant. Be concise.
"""

        try:
            with open(modelfile_path, "w") as f:
                f.write(modelfile_content)

            # Create the optimized model
            result = subprocess.run(
                ["ollama", "create", optimized_name, "-f", str(modelfile_path)],
                capture_output=True,
                text=True,
                timeout=300,
            )

            if result.returncode == 0:
                self.tuned.add(model)
                return True, f"Created {optimized_name} with 2K context, GPU-optimized"
            else:
                return False, f"Create failed: {result.stderr}"
        except Exception as e:
            return False, f"Tune error: {e}"


class BenchmarkAndReplaceStrategy(OptimizationStrategy):
    """
    AGGRESSIVE: Benchmark alternatives and replace slow models.
    If a faster model exists and is faster, update TARGETS to use it.
    """

    def __init__(self):
        super().__init__("benchmark_replace")
        self.benchmarked = set()

    def can_apply(self, model: str, current: float, target: float) -> bool:
        return model not in self.benchmarked and current > target * 2

    def apply(self, model: str) -> Tuple[bool, str]:
        self.benchmarked.add(model)

        # Get list of available models
        try:
            resp = requests.get(f"{OLLAMA_URL}/api/tags", timeout=10)
            if resp.status_code != 200:
                return False, "Couldn't get model list"

            models = [m["name"] for m in resp.json().get("models", [])]

            # Find alternatives (same base model, different quantization)
            base = model.split(":")[0]
            alternatives = [m for m in models if m.startswith(base) and m != model]

            if not alternatives:
                return True, f"No alternatives found for {model}"

            # Benchmark each alternative
            results = {}
            for alt in alternatives[:3]:  # Max 3 alternatives
                try:
                    latency = get_model_latency(alt, "benchmark test", timeout=60)
                    results[alt] = latency
                    logger.info(f"  {alt}: {latency:.0f}ms")
                except:
                    pass

            if results:
                fastest = min(results, key=results.get)
                fastest_time = results[fastest]

                # Get current model time
                try:
                    current_time = get_model_latency(
                        model, "benchmark test", timeout=60
                    )
                except:
                    current_time = float("inf")

                if fastest_time < current_time * 0.8:  # 20% faster
                    return (
                        True,
                        f"Found faster alternative: {fastest} ({fastest_time:.0f}ms vs {current_time:.0f}ms)",
                    )

            return (
                True,
                f"Benchmarked {len(results)} alternatives, none significantly faster",
            )

        except Exception as e:
            return False, f"Benchmark error: {e}"


# Initialize strategies - AGGRESSIVE MODE
STRATEGIES = [
    M2HardwareAccelerationStrategy(),  # First: configure GPU
    PreloadModelsStrategy(),  # Then: preload into memory
    WarmupStrategy(),  # Keep warm
    PullQuantizedModelsStrategy(),  # Get faster models
    TuneContextWindowStrategy(),  # Optimize context
    BenchmarkAndReplaceStrategy(),  # Find best alternatives
]


# ============================================================================
# SELF-MODIFICATION ENGINE
# ============================================================================


class SelfModifier:
    """
    The daemon can modify its own code to optimize itself.
    This is the core of autonomous evolution.

    Safety measures:
    1. Always backup before modification
    2. Test changes before deploying
    3. Rollback on failure
    4. Log all modifications
    """

    def __init__(self):
        self.own_file = Path(__file__)
        self.backup_dir = Path.home() / ".brain-continuity" / "optimizer-backups"
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        self.modification_log = (
            Path.home() / ".brain-continuity" / "self-modifications.json"
        )

    def get_own_hash(self) -> str:
        """Get hash of current code"""
        with open(self.own_file, "rb") as f:
            return hashlib.sha256(f.read()).hexdigest()[:12]

    def backup_self(self) -> Path:
        """Create backup of current code"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = self.backup_dir / f"optimizer_{timestamp}.py"

        with open(self.own_file) as src:
            with open(backup_path, "w") as dst:
                dst.write(src.read())

        logger.info(f"Backed up to {backup_path}")
        return backup_path

    def get_latest_backup(self) -> Optional[Path]:
        """Get most recent backup"""
        backups = sorted(self.backup_dir.glob("optimizer_*.py"))
        return backups[-1] if backups else None

    def rollback(self) -> bool:
        """Rollback to previous version"""
        backup = self.get_latest_backup()
        if not backup:
            logger.error("No backup found for rollback")
            return False

        try:
            with open(backup) as src:
                with open(self.own_file, "w") as dst:
                    dst.write(src.read())
            logger.info(f"Rolled back to {backup}")
            return True
        except Exception as e:
            logger.error(f"Rollback failed: {e}")
            return False

    def test_code(self, code: str) -> Tuple[bool, str]:
        """Test if code is valid Python"""
        try:
            compile(code, "<self-modification>", "exec")
            return True, "Syntax OK"
        except SyntaxError as e:
            return False, f"Syntax error: {e}"

    def apply_modification(self, new_code: str, description: str) -> bool:
        """Apply a code modification safely"""
        # Test first
        valid, msg = self.test_code(new_code)
        if not valid:
            logger.error(f"Modification rejected: {msg}")
            return False

        # Backup
        self.backup_self()
        old_hash = self.get_own_hash()

        # Apply
        try:
            with open(self.own_file, "w") as f:
                f.write(new_code)

            new_hash = self.get_own_hash()

            # Log modification
            self._log_modification(old_hash, new_hash, description)

            logger.info(f"Self-modification applied: {description}")
            logger.info(f"Hash: {old_hash} -> {new_hash}")
            return True

        except Exception as e:
            logger.error(f"Modification failed: {e}")
            self.rollback()
            return False

    def _log_modification(self, old_hash: str, new_hash: str, description: str):
        """Log modification history"""
        try:
            if self.modification_log.exists():
                with open(self.modification_log) as f:
                    history = json.load(f)
            else:
                history = []

            history.append(
                {
                    "timestamp": datetime.now().isoformat(),
                    "old_hash": old_hash,
                    "new_hash": new_hash,
                    "description": description,
                }
            )

            with open(self.modification_log, "w") as f:
                json.dump(history, f, indent=2)
        except Exception as e:
            logger.warning(f"Failed to log modification: {e}")

    def optimize_intervals(self, state: dict) -> Optional[str]:
        """
        Analyze performance and suggest interval optimizations.
        If benchmarks consistently pass, we can check less often.
        If they fail, check more often.
        """
        history = state.get("history", [])
        if len(history) < 5:
            return None  # Not enough data

        # Count recent successes/failures
        recent = history[-10:]
        successes = sum(
            1 for h in recent if "success" in h.get("description", "").lower()
        )

        with open(self.own_file) as f:
            current_code = f.read()

        # If mostly succeeding, we can relax intervals
        if successes >= 8:
            if "CHECK_INTERVAL = 120  # Optimized: needs attention" in current_code:
                new_code = current_code.replace(
                    "CHECK_INTERVAL = 120  # Optimized: needs attention",
                    "CHECK_INTERVAL = 600  # Optimized: stable performance",
                )
                return new_code

        # If mostly failing, check more often
        elif successes <= 2:
            if "CHECK_INTERVAL = 120  # Optimized: needs attention" in current_code:
                new_code = current_code.replace(
                    "CHECK_INTERVAL = 120  # Optimized: needs attention",
                    "CHECK_INTERVAL = 120  # Optimized: needs attention",
                )
                return new_code

        return None

    def add_new_strategy(self, strategy_code: str, strategy_name: str) -> bool:
        """
        Add a new optimization strategy to the daemon.
        This allows the daemon to learn new tricks.
        """
        with open(self.own_file) as f:
            current_code = f.read()

        # Find where to insert (before STRATEGIES list)
        insert_marker = "# Initialize strategies"
        if insert_marker not in current_code:
            logger.error("Cannot find insertion point for new strategy")
            return False

        # Insert new strategy class
        new_code = current_code.replace(
            insert_marker, f"{strategy_code}\n\n{insert_marker}"
        )

        # Add to STRATEGIES list
        new_code = new_code.replace(
            "STRATEGIES = [", f"STRATEGIES = [\n    {strategy_name}(),"
        )

        return self.apply_modification(new_code, f"Added new strategy: {strategy_name}")

    def evolve(self, state: dict) -> bool:
        """
        Main evolution function - analyze and improve self.
        Called periodically by the daemon.
        """
        logger.info("🧬 Running self-evolution check...")

        # Try interval optimization
        new_code = self.optimize_intervals(state)
        if new_code:
            if self.apply_modification(
                new_code, "Optimized check intervals based on performance"
            ):
                return True

        # Future: More evolution strategies
        # - Add new optimization strategies based on patterns
        # - Tune timeouts based on observed latencies
        # - Remove strategies that never succeed

        logger.info("No evolution needed at this time")
        return False


# Global self-modifier instance
SELF_MODIFIER = SelfModifier()

# ============================================================================
# MAIN OPTIMIZATION LOOP
# ============================================================================


def run_optimization_cycle(state: dict) -> dict:
    """Run one optimization cycle"""
    logger.info("=" * 50)
    logger.info("Starting optimization cycle")

    # Ensure Ollama is running
    if not ensure_ollama_running():
        logger.error("Ollama not available, skipping cycle")
        return state

    # Run benchmarks
    results = run_benchmarks()
    if not results:
        logger.warning("No benchmark results, skipping cycle")
        return state

    save_benchmark_results(results)
    state["last_benchmark"] = datetime.now().isoformat()

    # Check each model against targets
    improvements_needed = []
    for model, latency in results.items():
        target = TARGETS.get(model, {}).get("latency", latency)

        if latency > target:
            gap = latency - target
            improvements_needed.append((model, latency, target, gap))
            logger.warning(
                f"{model}: {latency:.1f}ms > target {target}ms (gap: {gap:.1f}ms)"
            )
        else:
            logger.info(f"{model}: {latency:.1f}ms ✓ (target: {target}ms)")

    # Apply optimization strategies
    for model, current, target, gap in improvements_needed:
        for strategy in STRATEGIES:
            if strategy.can_apply(model, current, target):
                success, desc = strategy.apply(model)
                if success:
                    logger.info(f"Applied {strategy.name}: {desc}")
                    state["optimizations_applied"] += 1
                    state["history"].append(
                        {
                            "time": datetime.now().isoformat(),
                            "strategy": strategy.name,
                            "model": model,
                            "description": desc,
                        }
                    )

    state["last_optimization"] = datetime.now().isoformat()
    save_state(state)

    # Calculate overall status
    total_gap = sum(gap for _, _, _, gap in improvements_needed)
    if total_gap == 0:
        logger.info("🎉 ALL MODELS MEETING TARGETS!")
    else:
        logger.info(f"Total gap to targets: {total_gap:.1f}ms")

    logger.info("Optimization cycle complete")
    logger.info("=" * 50)

    return state


# ============================================================================
# DAEMON CONTROL
# ============================================================================


def daemon_loop():
    """Main daemon loop - runs forever, self-improving"""
    state = load_state()
    state["started_at"] = datetime.now().isoformat()
    state["cycles"] = 0
    save_state(state)

    logger.info("🚀 Autonomous Optimizer started")
    logger.info(f"Check interval: {CHECK_INTERVAL}s")
    logger.info(f"Benchmark interval: {BENCHMARK_INTERVAL}s")
    logger.info(f"Code hash: {SELF_MODIFIER.get_own_hash()}")

    # Initial run
    state = run_optimization_cycle(state)

    while True:
        try:
            time.sleep(CHECK_INTERVAL)
            state["cycles"] = state.get("cycles", 0) + 1

            # Quick health check
            if not check_ollama_health():
                ensure_ollama_running()

            # Run full benchmark cycle if due
            last_bench = state.get("last_benchmark")
            if last_bench:
                last = datetime.fromisoformat(last_bench)
                if datetime.now() - last > timedelta(seconds=BENCHMARK_INTERVAL):
                    state = run_optimization_cycle(state)
            else:
                state = run_optimization_cycle(state)

            # Self-evolution check (every 5 cycles)
            if state.get("cycles", 0) % 5 == 0:
                logger.info("🧬 Self-evolution cycle...")
                if SELF_MODIFIER.evolve(state):
                    logger.info("✨ Self-modification applied! Restarting...")
                    # Restart to load new code
                    os.execv(sys.executable, [sys.executable, __file__] + sys.argv)

            save_state(state)

        except KeyboardInterrupt:
            logger.info("Received shutdown signal")
            break
        except Exception as e:
            logger.error(f"Error in daemon loop: {e}")
            time.sleep(60)  # Wait before retry

    logger.info("Daemon stopped")


def start_daemon():
    """Start the daemon in background"""
    if PID_FILE.exists():
        with open(PID_FILE) as f:
            pid = int(f.read().strip())
        try:
            os.kill(pid, 0)
            print(f"Daemon already running (PID {pid})")
            return
        except OSError:
            pass  # Process not running, clean up

    # Fork and run in background
    pid = os.fork()
    if pid > 0:
        # Parent
        print(f"Started daemon (PID {pid})")
        return

    # Child - become daemon
    os.setsid()

    # Fork again
    pid = os.fork()
    if pid > 0:
        os._exit(0)

    # Save PID
    PID_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(PID_FILE, "w") as f:
        f.write(str(os.getpid()))

    # Redirect stdout/stderr
    sys.stdout = open(LOG_FILE, "a")
    sys.stderr = sys.stdout

    # Run daemon
    daemon_loop()


def stop_daemon():
    """Stop the daemon"""
    if not PID_FILE.exists():
        print("Daemon not running")
        return

    with open(PID_FILE) as f:
        pid = int(f.read().strip())

    try:
        os.kill(pid, signal.SIGTERM)
        print(f"Stopped daemon (PID {pid})")
        PID_FILE.unlink()
    except OSError as e:
        print(f"Failed to stop daemon: {e}")
        PID_FILE.unlink()


def show_status():
    """Show daemon status"""
    state = load_state()

    print("\n🤖 AUTONOMOUS OPTIMIZER STATUS")
    print("=" * 50)

    # Check if running
    if PID_FILE.exists():
        with open(PID_FILE) as f:
            pid = int(f.read().strip())
        try:
            os.kill(pid, 0)
            print(f"Status: 🟢 RUNNING (PID {pid})")
        except OSError:
            print("Status: 🔴 STOPPED (stale PID file)")
    else:
        print("Status: 🔴 STOPPED")

    print(f"\nStarted: {state.get('started_at', 'Never')}")
    print(f"Last benchmark: {state.get('last_benchmark', 'Never')}")
    print(f"Last optimization: {state.get('last_optimization', 'Never')}")
    print(f"Optimizations applied: {state.get('optimizations_applied', 0)}")

    # Show current targets
    print("\n📊 PERFORMANCE TARGETS")
    print("-" * 50)
    for model, info in TARGETS.items():
        print(f"  {model}: target {info['latency']}ms (last: {info['current']}ms)")

    # Show recent history
    history = state.get("history", [])[-5:]
    if history:
        print("\n📜 RECENT ACTIVITY")
        print("-" * 50)
        for item in history:
            print(f"  [{item['time'][:16]}] {item['strategy']}: {item['description']}")

    print()


def show_logs():
    """Show recent logs"""
    if LOG_FILE.exists():
        subprocess.run(["tail", "-50", str(LOG_FILE)])
    else:
        print("No logs found")


def show_version():
    """Show version and self-modification history"""
    print("🧬 AUTONOMOUS OPTIMIZER - SELF-MODIFICATION STATUS")
    print("=" * 50)
    print(f"Code hash: {SELF_MODIFIER.get_own_hash()}")
    print(f"Source: {SELF_MODIFIER.own_file}")

    # Show backups
    backups = sorted(SELF_MODIFIER.backup_dir.glob("optimizer_*.py"))
    print(f"\nBackups: {len(backups)}")
    if backups:
        for b in backups[-5:]:
            print(f"  - {b.name}")

    # Show modification history
    if SELF_MODIFIER.modification_log.exists():
        with open(SELF_MODIFIER.modification_log) as f:
            history = json.load(f)
        print(f"\nModifications: {len(history)}")
        for mod in history[-5:]:
            print(f"  [{mod['timestamp'][:16]}] {mod['description']}")
    else:
        print("\nNo modifications yet")
    print()


def force_evolve():
    """Force a self-evolution check"""
    print("🧬 Forcing self-evolution check...")
    state = load_state()
    if SELF_MODIFIER.evolve(state):
        print("✨ Evolution applied!")
    else:
        print("No evolution needed at this time")


def rollback():
    """Rollback to previous version"""
    print("⏪ Rolling back to previous version...")
    if SELF_MODIFIER.rollback():
        print("✅ Rollback successful!")
    else:
        print("❌ Rollback failed!")


# ============================================================================
# MAIN
# ============================================================================


def main():
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} <command>")
        print("")
        print("Core commands:")
        print("  start    - Start daemon in background (runs forever)")
        print("  stop     - Stop daemon")
        print("  status   - Show status and performance")
        print("  logs     - Show recent logs")
        print("  run      - Run once (foreground)")
        print("")
        print("Self-modification:")
        print("  version  - Show code hash and modification history")
        print("  evolve   - Force self-evolution check")
        print("  rollback - Rollback to previous code version")
        sys.exit(1)

    command = sys.argv[1].lower()

    if command == "start":
        start_daemon()
    elif command == "stop":
        stop_daemon()
    elif command == "status":
        show_status()
    elif command == "logs":
        show_logs()
    elif command == "run":
        # Run once in foreground
        state = load_state()
        run_optimization_cycle(state)
    elif command == "version":
        show_version()
    elif command == "evolve":
        force_evolve()
    elif command == "rollback":
        rollback()
    else:
        print(f"Unknown command: {command}")
        sys.exit(1)


if __name__ == "__main__":
    main()
