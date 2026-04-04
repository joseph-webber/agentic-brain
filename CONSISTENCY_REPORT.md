# Agentic Brain Consistency Report

- Generated: 2026-04-04 08:22 UTC
- Scope scanned: `545` core Python files, `53` BrainChat Swift source files, `7` SDK Python files, `0` SDK Swift files, `5` SDK TypeScript files.
- Exclusions: generated `.build` output and duplicated Swift test-source mirrors were excluded to reduce duplicate noise.

## Executive Summary

| Area | Result |
| --- | --- |
| Naming | 5 high-confidence naming inconsistencies |
| Import organization | 437 import-order/alphabetization issues across `367` files |
| Error handling | `1438` generic `except Exception` blocks in Python and `53` bare `catch {}` blocks in Swift source |
| Type hints | `294` missing Python type-hint items across `108` files |
| Docstrings | `1441` missing Python docstrings across `208` files |
| Configuration | No high-confidence hardcoded secret findings |
| Async/await | `4` actionable async consistency findings |

## 1. Naming Conventions

- `src/agentic_brain/audio/__init__.py:115` — Python method `Voice.KAREN` should use snake_case.
- `src/agentic_brain/audio/__init__.py:119` — Python method `Voice.SAMANTHA` should use snake_case.
- `src/agentic_brain/audio/__init__.py:123` — Python method `Voice.DANIEL` should use snake_case.
- `src/agentic_brain/audio/__init__.py:127` — Python method `Voice.MOIRA` should use snake_case.
- `src/agentic_brain/rag/loaders/icloud.py:44` — Python class `iCloudLoader` should use PascalCase.

## 2. Import Organization

### Python hotspots

- `src/agentic_brain/benchmark/runner.py:20, 25, 33` — Reorder import groups to standard library, third-party, then local imports.; Alphabetize imports within the stdlib group.; Alphabetize imports within the local group. (3 issue(s) in this file).
- `src/agentic_brain/audio/__init__.py:34, 36, 43` — Reorder import groups to standard library, third-party, then local imports.; Alphabetize imports within the stdlib group.; Alphabetize imports within the local group. (3 issue(s) in this file).
- `src/agentic_brain/router/routing.py:37, 37, 45` — Reorder import groups to standard library, third-party, then local imports.; Alphabetize imports within the stdlib group.; Alphabetize imports within the local group. (3 issue(s) in this file).
- `src/agentic_brain/installer_enhanced.py:33, 37` — Reorder import groups to standard library, third-party, then local imports.; Alphabetize imports within the stdlib group. (2 issue(s) in this file).
- `src/agentic_brain/commerce/payments.py:27, 29` — Reorder import groups to standard library, third-party, then local imports.; Alphabetize imports within the stdlib group. (2 issue(s) in this file).
- `src/agentic_brain/commerce/hub.py:46, 46` — Reorder import groups to standard library, third-party, then local imports.; Alphabetize imports within the stdlib group. (2 issue(s) in this file).
- `src/agentic_brain/commerce/shipping.py:26, 26` — Reorder import groups to standard library, third-party, then local imports.; Alphabetize imports within the stdlib group. (2 issue(s) in this file).
- `src/agentic_brain/commerce/analytics.py:32, 32` — Reorder import groups to standard library, third-party, then local imports.; Alphabetize imports within the stdlib group. (2 issue(s) in this file).
- `src/agentic_brain/commerce/webhooks.py:23, 26` — Reorder import groups to standard library, third-party, then local imports.; Alphabetize imports within the stdlib group. (2 issue(s) in this file).
- `src/agentic_brain/infra/health_monitor.py:18, 26` — Alphabetize imports within the stdlib group.; Alphabetize imports within the third-party group. (2 issue(s) in this file).
- `src/agentic_brain/infra/event_bridge.py:35, 44` — Alphabetize imports within the stdlib group.; Alphabetize imports within the third-party group. (2 issue(s) in this file).
- `src/agentic_brain/llm/router.py:14, 14` — Reorder import groups to standard library, third-party, then local imports.; Alphabetize imports within the stdlib group. (2 issue(s) in this file).
- `src/agentic_brain/core/startup.py:20, 21` — Reorder import groups to standard library, third-party, then local imports.; Alphabetize imports within the stdlib group. (2 issue(s) in this file).
- `src/agentic_brain/core/cache_manager.py:8, 8` — Reorder import groups to standard library, third-party, then local imports.; Alphabetize imports within the stdlib group. (2 issue(s) in this file).
- `src/agentic_brain/core/neo4j_pool.py:14, 15` — Reorder import groups to standard library, third-party, then local imports.; Alphabetize imports within the stdlib group. (2 issue(s) in this file).
- `src/agentic_brain/modes/manager.py:34, 41` — Alphabetize imports within the stdlib group.; Alphabetize imports within the local group. (2 issue(s) in this file).
- `src/agentic_brain/durability/worker_pool.py:30, 30` — Reorder import groups to standard library, third-party, then local imports.; Alphabetize imports within the stdlib group. (2 issue(s) in this file).
- `src/agentic_brain/durability/checkpoints.py:46, 48` — Reorder import groups to standard library, third-party, then local imports.; Alphabetize imports within the stdlib group. (2 issue(s) in this file).
- `src/agentic_brain/durability/event_store.py:57, 59` — Reorder import groups to standard library, third-party, then local imports.; Alphabetize imports within the stdlib group. (2 issue(s) in this file).
- `src/agentic_brain/durability/async_completion.py:58, 61` — Reorder import groups to standard library, third-party, then local imports.; Alphabetize imports within the stdlib group. (2 issue(s) in this file).
- `src/agentic_brain/auth/providers.py:41, 44` — Reorder import groups to standard library, third-party, then local imports.; Alphabetize imports within the stdlib group. (2 issue(s) in this file).
- `src/agentic_brain/auth/enterprise_providers.py:29, 32` — Reorder import groups to standard library, third-party, then local imports.; Alphabetize imports within the stdlib group. (2 issue(s) in this file).
- `src/agentic_brain/plugins/address_validation.py:39, 39` — Reorder import groups to standard library, third-party, then local imports.; Alphabetize imports within the stdlib group. (2 issue(s) in this file).
- `src/agentic_brain/plugins/base.py:23, 24` — Reorder import groups to standard library, third-party, then local imports.; Alphabetize imports within the stdlib group. (2 issue(s) in this file).
- `src/agentic_brain/graph/topic_hub.py:8, 8` — Reorder import groups to standard library, third-party, then local imports.; Alphabetize imports within the stdlib group. (2 issue(s) in this file).

### Swift hotspots

- `apps/BrainChat/AudioPlayer.swift:1` — Alphabetize imports within the framework group. (1 issue(s) in this file).
- `apps/BrainChat/SpatialAudio.swift:1` — Alphabetize imports within the framework group. (1 issue(s) in this file).
- `apps/BrainChat/AIManager.swift:1` — Alphabetize imports within the framework group. (1 issue(s) in this file).
- `apps/BrainChat/YoloMode.swift:1` — Alphabetize imports within the framework group. (1 issue(s) in this file).
- `apps/BrainChat/LLMRouter.swift:1` — Alphabetize imports within the framework group. (1 issue(s) in this file).
- `apps/BrainChat/AudioSession.swift:1` — Alphabetize imports within the framework group. (1 issue(s) in this file).
- `apps/BrainChat/BrainChat.swift:1` — Alphabetize imports within the framework group. (1 issue(s) in this file).
- `apps/BrainChat/AirPodsManager.swift:1` — Alphabetize imports within the framework group. (1 issue(s) in this file).

## 3. Error Handling

### Python: generic `except Exception` hotspots

- `src/agentic_brain/secrets/backends.py:435, 456, 473, 506, 523, 542` — Replace broad `except Exception` blocks with narrower exceptions and keep structured logging/context (31 occurrence(s)).
- `src/agentic_brain/rag/loaders/nosql.py:179, 265, 280, 289, 334, 386` — Replace broad `except Exception` blocks with narrower exceptions and keep structured logging/context (29 occurrence(s)).
- `src/agentic_brain/voice/live_session.py:97, 219, 278, 341, 410, 435` — Replace broad `except Exception` blocks with narrower exceptions and keep structured logging/context (27 occurrence(s)).
- `src/agentic_brain/rag/loaders/vector_db.py:125, 134, 169, 215, 255, 310` — Replace broad `except Exception` blocks with narrower exceptions and keep structured logging/context (23 occurrence(s)).
- `src/agentic_brain/voice/conversation_loop.py:229, 249, 268, 282, 295, 310` — Replace broad `except Exception` blocks with narrower exceptions and keep structured logging/context (21 occurrence(s)).
- `src/agentic_brain/cli/commands.py:384, 432, 504, 519, 546, 646` — Replace broad `except Exception` blocks with narrower exceptions and keep structured logging/context (19 occurrence(s)).
- `src/agentic_brain/mcp/tools.py:133, 177, 261, 310, 365, 400` — Replace broad `except Exception` blocks with narrower exceptions and keep structured logging/context (19 occurrence(s)).
- `src/agentic_brain/rag/loaders/support.py:132, 192, 247, 280, 372, 432` — Replace broad `except Exception` blocks with narrower exceptions and keep structured logging/context (18 occurrence(s)).
- `src/agentic_brain/transport/firebase.py:458, 467, 500, 521, 525, 583` — Replace broad `except Exception` blocks with narrower exceptions and keep structured logging/context (18 occurrence(s)).
- `src/agentic_brain/rag/community_detection.py:104, 113, 161, 363, 442, 516` — Replace broad `except Exception` blocks with narrower exceptions and keep structured logging/context (17 occurrence(s)).
- `src/agentic_brain/rag/loaders/project_management.py:119, 166, 213, 236, 256, 315` — Replace broad `except Exception` blocks with narrower exceptions and keep structured logging/context (17 occurrence(s)).
- `src/agentic_brain/rag/loaders/saas.py:84, 113, 152, 179, 216, 242` — Replace broad `except Exception` blocks with narrower exceptions and keep structured logging/context (17 occurrence(s)).
- `src/agentic_brain/voice/serializer.py:404, 419, 429, 500, 587, 663` — Replace broad `except Exception` blocks with narrower exceptions and keep structured logging/context (17 occurrence(s)).
- `src/agentic_brain/rag/loaders/australian.py:98, 127, 170, 198, 263, 289` — Replace broad `except Exception` blocks with narrower exceptions and keep structured logging/context (16 occurrence(s)).
- `src/agentic_brain/rag/loaders/enterprise.py:105, 137, 181, 208, 266, 289` — Replace broad `except Exception` blocks with narrower exceptions and keep structured logging/context (16 occurrence(s)).
- `src/agentic_brain/voice/redpanda_queue.py:45, 51, 192, 197, 202, 222` — Replace broad `except Exception` blocks with narrower exceptions and keep structured logging/context (16 occurrence(s)).
- `src/agentic_brain/voice/tts_fallback.py:189, 232, 451, 492, 534, 579` — Replace broad `except Exception` blocks with narrower exceptions and keep structured logging/context (16 occurrence(s)).
- `src/agentic_brain/documents/services/office/word.py:171, 457, 870, 917, 935, 1310` — Replace broad `except Exception` blocks with narrower exceptions and keep structured logging/context (15 occurrence(s)).
- `src/agentic_brain/rag/loaders/cloud.py:198, 278, 317, 349, 374, 403` — Replace broad `except Exception` blocks with narrower exceptions and keep structured logging/context (15 occurrence(s)).
- `src/agentic_brain/infra/event_bridge.py:235, 240, 288, 292, 322, 345` — Replace broad `except Exception` blocks with narrower exceptions and keep structured logging/context (13 occurrence(s)).
- `src/agentic_brain/voice/memory.py:214, 276, 285, 312, 414, 530` — Replace broad `except Exception` blocks with narrower exceptions and keep structured logging/context (13 occurrence(s)).
- `src/agentic_brain/voice/resilient.py:97, 223, 258, 298, 336, 366` — Replace broad `except Exception` blocks with narrower exceptions and keep structured logging/context (13 occurrence(s)).
- `src/agentic_brain/health/__init__.py:108, 167, 199, 223, 254, 294` — Replace broad `except Exception` blocks with narrower exceptions and keep structured logging/context (12 occurrence(s)).
- `src/agentic_brain/router/routing.py:255, 287, 289, 324, 326, 384` — Replace broad `except Exception` blocks with narrower exceptions and keep structured logging/context (12 occurrence(s)).
- `src/agentic_brain/transport/websocket.py:146, 195, 229, 247, 310, 335` — Replace broad `except Exception` blocks with narrower exceptions and keep structured logging/context (12 occurrence(s)).

### Swift: bare `catch {}` blocks to review

- `apps/BrainChat/YoloExecutor.swift:355, 395, 449, 494, 544, 594` — Review bare `catch {}` handling for consistency; prefer typed catches or preserve the original error details.
- `apps/BrainChat/ChatViewModel.swift:365, 385, 413, 461` — Review bare `catch {}` handling for consistency; prefer typed catches or preserve the original error details.
- `apps/BrainChat/SpeechManager.swift:218, 480, 574, 653` — Review bare `catch {}` handling for consistency; prefer typed catches or preserve the original error details.
- `apps/BrainChat/YoloSession.swift:223, 237, 348, 362` — Review bare `catch {}` handling for consistency; prefer typed catches or preserve the original error details.
- `apps/BrainChat/CartesiaVoice.swift:243, 293, 347` — Review bare `catch {}` handling for consistency; prefer typed catches or preserve the original error details.
- `apps/BrainChat/CopilotBridge.swift:302, 403, 684` — Review bare `catch {}` handling for consistency; prefer typed catches or preserve the original error details.
- `apps/BrainChat/LLMRouter.swift:249, 270, 344` — Review bare `catch {}` handling for consistency; prefer typed catches or preserve the original error details.
- `apps/BrainChat/Models.swift:246, 259, 277` — Review bare `catch {}` handling for consistency; prefer typed catches or preserve the original error details.
- `apps/BrainChat/FasterWhisperBridge.swift:30, 67` — Review bare `catch {}` handling for consistency; prefer typed catches or preserve the original error details.
- `apps/BrainChat/PandaproxyClient.swift:190, 280` — Review bare `catch {}` handling for consistency; prefer typed catches or preserve the original error details.
- `apps/BrainChat/RedpandaBridge.swift:91, 120` — Review bare `catch {}` handling for consistency; prefer typed catches or preserve the original error details.
- `apps/BrainChat/AIManager.swift:105` — Review bare `catch {}` handling for consistency; prefer typed catches or preserve the original error details.
- `apps/BrainChat/AudioSession.swift:75` — Review bare `catch {}` handling for consistency; prefer typed catches or preserve the original error details.
- `apps/BrainChat/BridgeDaemon.swift:21` — Review bare `catch {}` handling for consistency; prefer typed catches or preserve the original error details.
- `apps/BrainChat/ClaudeAPI.swift:79` — Review bare `catch {}` handling for consistency; prefer typed catches or preserve the original error details.
- `apps/BrainChat/CodeAssistant.swift:233` — Review bare `catch {}` handling for consistency; prefer typed catches or preserve the original error details.
- `apps/BrainChat/CopilotClient.swift:118` — Review bare `catch {}` handling for consistency; prefer typed catches or preserve the original error details.
- `apps/BrainChat/CopilotVoiceRouter.swift:39` — Review bare `catch {}` handling for consistency; prefer typed catches or preserve the original error details.
- `apps/BrainChat/GeminiClient.swift:131` — Review bare `catch {}` handling for consistency; prefer typed catches or preserve the original error details.
- `apps/BrainChat/GroqClient.swift:42` — Review bare `catch {}` handling for consistency; prefer typed catches or preserve the original error details.

## 4. Type Hints (Python)

- `src/agentic_brain/router/redis_cache.py` — 91: Add missing type hints for `RedisInterBotComm.client`: return type.; 95: Add missing type hints for `RedisInterBotComm.pubsub`: return type.; 100: Add missing type hints for `RedisInterBotComm.send_to_bot`: return type.; 116: Add missing type hints for `RedisInterBotComm.broadcast`: return type. (12 missing type-hint item(s)).
- `src/agentic_brain/installer.py` — 404: Add missing type hints for `print_banner`: return type.; 478: Add missing type hints for `create_project_structure`: return type.; 499: Add missing type hints for `create_config_file`: return type.; 520: Add missing type hints for `create_env_file`: return type. (11 missing type-hint item(s)).
- `src/agentic_brain/audio/__init__.py` — 220: Add missing type hints for `VoiceQueue.add`: parameter `**kwargs`, return type.; 225: Add missing type hints for `VoiceQueue.clear`: return type.; 562: Add missing type hints for `get_earcon_player`: return type.; 575: Add missing type hints for `speak`: parameter `**kwargs`. (10 missing type-hint item(s)).
- `src/agentic_brain/core/neo4j_pool.py` — 148: Add missing type hints for `get_session`: return type.; 172: Add missing type hints for `query`: parameter `**params`.; 180: Add missing type hints for `query_single`: parameter `**params`.; 189: Add missing type hints for `query_value`: parameter `**params`. (10 missing type-hint item(s)).
- `src/agentic_brain/cli/region_commands.py` — 27: Add missing type hints for `region_set_command`: parameter `args`, return type.; 55: Add missing type hints for `region_show_command`: parameter `args`, return type.; 89: Add missing type hints for `region_add_command`: parameter `args`, return type.; 108: Add missing type hints for `region_learn_command`: parameter `args`, return type. (9 missing type-hint item(s)).
- `src/agentic_brain/smart_router/workers.py` — 35: Add missing type hints for `BaseWorker.execute`: parameter `**kwargs`.; 49: Add missing type hints for `OpenAIWorker.execute`: parameter `**kwargs`.; 91: Add missing type hints for `AzureOpenAIWorker.execute`: parameter `**kwargs`.; 143: Add missing type hints for `GroqWorker.execute`: parameter `**kwargs`. (9 missing type-hint item(s)).
- `src/agentic_brain/infra/event_bridge.py` — 95: Add missing type hints for `EventBridge.start`: return type.; 99: Add missing type hints for `EventBridge.stop`: return type.; 169: Add missing type hints for `RedisRedpandaBridge.initialize`: return type.; 245: Add missing type hints for `RedisRedpandaBridge.start`: return type. (7 missing type-hint item(s)).
- `src/agentic_brain/installer_persona.py` — 35: Add missing type hints for `clear_screen`: return type.; 40: Add missing type hints for `print_header`: return type.; 47: Add missing type hints for `print_step`: return type.; 94: Add missing type hints for `run_simple_install`: return type. (7 missing type-hint item(s)).
- `src/agentic_brain/api/audit.py` — 224: Add missing type hints for `AuditLogger.log`: return type.; 235: Add missing type hints for `AuditLogger.log_request`: return type.; 284: Add missing type hints for `AuditLogger.log_auth`: return type.; 315: Add missing type hints for `AuditLogger.log_session`: return type. (6 missing type-hint item(s)).
- `src/agentic_brain/api/models.py` — 51: Add missing type hints for `ChatRequest.message_not_empty`: parameter `v`, return type.; 59: Add missing type hints for `ChatRequest.session_id_format`: parameter `v`, return type.; 71: Add missing type hints for `ChatRequest.user_id_format`: parameter `v`, return type.; 83: Add missing type hints for `ChatRequest.validate_metadata`: parameter `v`, return type. (6 missing type-hint item(s)).
- `src/agentic_brain/infra/health_monitor.py` — 180: Add missing type hints for `HealthMonitor.initialize`: return type.; 426: Add missing type hints for `HealthMonitor.register_restart_callback`: return type.; 441: Add missing type hints for `HealthMonitor.health_check_loop`: return type.; 466: Add missing type hints for `HealthMonitor.start_monitoring`: return type. (6 missing type-hint item(s)).
- `src/agentic_brain/voice/user_regions.py` — 87: Add missing type hints for `UserRegionStorage.set_region`: return type.; 110: Add missing type hints for `UserRegionStorage.add_expression`: return type.; 116: Add missing type hints for `UserRegionStorage.learn_expression`: return type.; 174: Add missing type hints for `UserRegionStorage.add_local_knowledge`: return type. (6 missing type-hint item(s)).
- `src/agentic_brain/durability/cancellation.py` — 222: Add missing type hints for `CancellationScopeManager.scope`: return type.; 266: Add missing type hints for `CancellationScopeManager.shield`: return type.; 278: Add missing type hints for `CancellationScopeManager.timeout_scope`: return type.; 302: Add missing type hints for `cancellation_scope`: return type. (5 missing type-hint item(s)).
- `src/agentic_brain/explainability/lime_explainer.py` — 178: Add missing type hints for `LIMEExplainer.explain_prediction`: parameter `**kwargs`.; 199: Add missing type hints for `LIMEExplainer.explain_instance`: parameter `**kwargs`.; 439: Add missing type hints for `LIMEExplainer.get_explanation_html`: parameter `**kwargs`.; 497: Add missing type hints for `LIMEExplainer.feature_importance`: parameter `**kwargs`. (5 missing type-hint item(s)).
- `src/agentic_brain/explainability/shap_explainer.py` — 187: Add missing type hints for `SHAPExplainer.explain_prediction`: parameter `**kwargs`.; 293: Add missing type hints for `SHAPExplainer.feature_importance`: parameter `**kwargs`.; 346: Add missing type hints for `SHAPExplainer.summary_plot_data`: parameter `**kwargs`.; 400: Add missing type hints for `SHAPExplainer.waterfall_plot_data`: parameter `**kwargs`. (5 missing type-hint item(s)).
- `src/agentic_brain/hooks/hooks.py` — 209: Add missing type hints for `HooksManager.on_session_start`: parameter `**kwargs`.; 221: Add missing type hints for `HooksManager.on_session_end`: parameter `**kwargs`.; 233: Add missing type hints for `HooksManager.on_message`: parameter `**kwargs`.; 246: Add missing type hints for `HooksManager.on_response`: parameter `**kwargs`. (5 missing type-hint item(s)).
- `src/agentic_brain/installer_enhanced.py` — 60: Add missing type hints for `Colors.disable`: return type.; 798: Add missing type hints for `show_status_dashboard`: return type.; 891: Add missing type hints for `print_welcome_banner`: return type.; 911: Add missing type hints for `run_enhanced_installer`: return type. (5 missing type-hint item(s)).
- `src/agentic_brain/observability/metrics.py` — 124: Add missing type hints for `setup_metrics`: parameter `**kwargs`.; 363: Add missing type hints for `_NoOpMeter.create_counter`: parameter `**kwargs`.; 366: Add missing type hints for `_NoOpMeter.create_histogram`: parameter `**kwargs`.; 369: Add missing type hints for `_NoOpMeter.create_up_down_counter`: parameter `**kwargs`. (5 missing type-hint item(s)).
- `src/agentic_brain/voice/conversation.py` — 83: Add missing type hints for `ConversationConfig.save_mode`: return type.; 412: Add missing type hints for `ConversationalVoice.set_mode`: return type.; 448: Add missing type hints for `ConversationalVoice.demo`: return type.; 532: Add missing type hints for `set_mode`: return type. (5 missing type-hint item(s)).
- `src/agentic_brain/voice/voiceover.py` — 331: Add missing type hints for `VoiceOverCoordinator.send_notification`: return type.; 352: Add missing type hints for `VoiceOverCoordinator.announce`: return type.; 412: Add missing type hints for `VoiceOverAwareVoice.announce`: return type.; 448: Add missing type hints for `announce_vo`: return type. (5 missing type-hint item(s)).
- `src/agentic_brain/documents/services/office/rag_loaders.py` — 533: Add missing type hints for `register_office_loaders`: return type.; 575: Add missing type hints for `load_office_document`: parameter `**kwargs`.; 590: Add missing type hints for `load_office_directory`: parameter `**kwargs`.; 608: Add missing type hints for `load_and_chunk_office`: parameter `**kwargs`. (4 missing type-hint item(s)).
- `src/agentic_brain/durability/child_workflows.py` — 141: Add missing type hints for `ChildWorkflowManager.start_child_workflow`: parameter `*args`, parameter `**kwargs`.; 331: Add missing type hints for `child_workflow`: return type.; 355: Add missing type hints for `execute_child_workflow`: parameter `*args`, parameter `**kwargs`.; 379: Add missing type hints for `start_child_workflow_async`: parameter `*args`, parameter `**kwargs`. (4 missing type-hint item(s)).
- `src/agentic_brain/interbot/coordinator.py` — 50: Add missing type hints for `BotCoordinator.send`: return type.; 55: Add missing type hints for `BotCoordinator.request_help`: return type.; 68: Add missing type hints for `BotCoordinator.vote`: return type.; 83: Add missing type hints for `BotCoordinator.heartbeat`: return type. (4 missing type-hint item(s)).
- `src/agentic_brain/plugins/base.py` — 112: Add missing type hints for `Plugin.on_message`: parameter `**kwargs`.; 125: Add missing type hints for `Plugin.on_response`: parameter `**kwargs`.; 150: Add missing type hints for `Plugin.trigger_hooks`: parameter `*args`, parameter `**kwargs`.; 400: Add missing type hints for `PluginManager.trigger`: parameter `*args`, parameter `**kwargs`. (4 missing type-hint item(s)).
- `src/agentic_brain/rag/rate_limiter.py` — 281: Add missing type hints for `SmartRateLimiter.release`: return type.; 292: Add missing type hints for `SmartRateLimiter.record_success`: return type.; 303: Add missing type hints for `SmartRateLimiter.record_failure`: return type.; 430: Add missing type hints for `rate_limited`: return type. (4 missing type-hint item(s)).

## 5. Docstrings (Python)

- `src/agentic_brain/commerce/shipping.py` — 80: Add a Google-style docstring to `Dimensions.weight_decimal`.; 84: Add a Google-style docstring to `Dimensions.volume_cm3`.; 143: Add a Google-style docstring to class `TrackingEvent`.; 151: Add a Google-style docstring to class `TrackingInfo`.; 160: Add a Google-style docstring to class `ShipmentLabel`. (46 missing docstring(s)).
- `src/agentic_brain/commerce/wordpress/client.py` — 212: Add a Google-style docstring to `WordPressConfig.normalize_base_url`.; 220: Add a Google-style docstring to `WordPressConfig.normalize_namespace`.; 225: Add a Google-style docstring to `WordPressConfig.normalize_endpoint`.; 231: Add a Google-style docstring to `WordPressConfig.validate_credentials`.; 330: Add a Google-style docstring to `WordPressClient.close`. (40 missing docstring(s)).
- `src/agentic_brain/agi/causal_reasoning.py` — 39: Add a Google-style docstring to class `CausalRelationType`.; 47: Add a Google-style docstring to class `EvidenceType`.; 56: Add a Google-style docstring to class `CausalStrength`.; 64: Add a Google-style docstring to class `Evidence`.; 72: Add a Google-style docstring to `Evidence.to_dict`. (37 missing docstring(s)).
- `src/agentic_brain/benchmark/metrics.py` — 53: Add a Google-style docstring to `MetricDefinition.lower_is_better`.; 146: Add a Google-style docstring to `HardwareInfo.to_dict`.; 159: Add a Google-style docstring to `HardwareInfo.from_dict`.; 206: Add a Google-style docstring to `BenchmarkConfig.to_dict`.; 234: Add a Google-style docstring to `BenchmarkConfig.from_dict`. (33 missing docstring(s)).
- `src/agentic_brain/commerce/woo_api/products.py` — 43: Add a Google-style docstring to `ProductsAPI.retrieve`.; 48: Add a Google-style docstring to `ProductsAPI.create`.; 51: Add a Google-style docstring to `ProductsAPI.update`.; 58: Add a Google-style docstring to `ProductsAPI.delete`.; 65: Add a Google-style docstring to `ProductsAPI.batch`. (33 missing docstring(s)).
- `src/agentic_brain/audio/__init__.py` — 115: Add a Google-style docstring to `Voice.KAREN`.; 119: Add a Google-style docstring to `Voice.SAMANTHA`.; 123: Add a Google-style docstring to `Voice.DANIEL`.; 127: Add a Google-style docstring to `Voice.MOIRA`.; 147: Add a Google-style docstring to `VoiceRegistry.list_voices`. (31 missing docstring(s)).
- `src/agentic_brain/audio/airpods.py` — 61: Add a Google-style docstring to `BatteryLevels.minimum_level`.; 71: Add a Google-style docstring to `BatteryLevels.as_dict`.; 102: Add a Google-style docstring to `SpatialVoicePosition.to_native_payload`.; 121: Add a Google-style docstring to `SpatialAudioScene.to_native_payload`.; 156: Add a Google-style docstring to `AirPodsStatus.connected`. (29 missing docstring(s)).
- `src/agentic_brain/secrets/backends.py` — 212: Add a Google-style docstring to `EnvVarBackend.get_secret`.; 220: Add a Google-style docstring to `EnvVarBackend.set_secret`.; 225: Add a Google-style docstring to `EnvVarBackend.delete_secret`.; 232: Add a Google-style docstring to `EnvVarBackend.list_secrets`.; 339: Add a Google-style docstring to `DotEnvBackend.get_secret`. (29 missing docstring(s)).
- `src/agentic_brain/audio/earcons.py` — 133: Add a Google-style docstring to `generate_success`.; 145: Add a Google-style docstring to `generate_error`.; 155: Add a Google-style docstring to `generate_waiting`.; 168: Add a Google-style docstring to `generate_mode_switch`.; 177: Add a Google-style docstring to `generate_attention_needed`. (28 missing docstring(s)).
- `src/agentic_brain/commerce/analytics.py` — 70: Add a Google-style docstring to class `ProductPerformance`.; 78: Add a Google-style docstring to class `CustomerLifetimeValue`.; 89: Add a Google-style docstring to class `InventoryAlert`.; 99: Add a Google-style docstring to class `FunnelReport`.; 118: Add a Google-style docstring to class `ConversionRateReport`. (27 missing docstring(s)).
- `src/agentic_brain/durability/payload_converters.py` — 94: Add a Google-style docstring to `Payload.to_dict`.; 102: Add a Google-style docstring to `Payload.from_dict`.; 176: Add a Google-style docstring to `JSONConverter.name`.; 180: Add a Google-style docstring to `JSONConverter.encoding`.; 183: Add a Google-style docstring to `JSONConverter.to_payload`. (24 missing docstring(s)).
- `src/agentic_brain/commerce/payments.py` — 328: Add a Google-style docstring to `PaymentGateway.create_subscription`.; 333: Add a Google-style docstring to `PaymentGateway.create_checkout`.; 344: Add a Google-style docstring to `PaymentGateway.verify_webhook`.; 364: Add a Google-style docstring to `StripeGateway.name`.; 367: Add a Google-style docstring to `StripeGateway.create_payment`. (23 missing docstring(s)).
- `src/agentic_brain/cache/semantic_cache.py` — 756: Add a Google-style docstring to `VectorCacheEntry.is_expired`.; 759: Add a Google-style docstring to `VectorCacheEntry.touch`.; 763: Add a Google-style docstring to `VectorCacheEntry.to_dict`.; 779: Add a Google-style docstring to `VectorCacheEntry.from_dict`.; 804: Add a Google-style docstring to `VectorMemoryBackend.add`. (20 missing docstring(s)).
- `src/agentic_brain/documents/services/office/api.py` — 279: Add a Google-style docstring to `process_office_document`.; 296: Add a Google-style docstring to `extract_text`.; 302: Add a Google-style docstring to `extract_tables`.; 306: Add a Google-style docstring to `extract_images`.; 325: Add a Google-style docstring to `process_word`. (20 missing docstring(s)).
- `src/agentic_brain/voice/voice_library.py` — 75: Add a Google-style docstring to `resolve_voice_storage_dir`.; 87: Add a Google-style docstring to class `VoiceProfile`.; 100: Add a Google-style docstring to `VoiceProfile.reference_audio`.; 103: Add a Google-style docstring to `VoiceProfile.to_dict`.; 107: Add a Google-style docstring to `VoiceProfile.from_dict`. (19 missing docstring(s)).
- `src/agentic_brain/api/sessions.py` — 233: Add a Google-style docstring to `InMemorySessionBackend.get`.; 236: Add a Google-style docstring to `InMemorySessionBackend.create`.; 250: Add a Google-style docstring to `InMemorySessionBackend.update`.; 266: Add a Google-style docstring to `InMemorySessionBackend.delete`.; 273: Add a Google-style docstring to `InMemorySessionBackend.list_all`. (17 missing docstring(s)).
- `src/agentic_brain/commerce/wp_api/categories.py` — 37: Add a Google-style docstring to `CategoriesAPI.list`.; 40: Add a Google-style docstring to `CategoriesAPI.get`.; 45: Add a Google-style docstring to `CategoriesAPI.create`.; 48: Add a Google-style docstring to `CategoriesAPI.update`.; 51: Add a Google-style docstring to `CategoriesAPI.delete`. (17 missing docstring(s)).
- `src/agentic_brain/rag/loaders/firestore.py` — 88: Add a Google-style docstring to `FirestoreOfflineCache.save_collection`.; 94: Add a Google-style docstring to `FirestoreOfflineCache.load_collection`.; 136: Add a Google-style docstring to `FirestoreLoader.source_name`.; 139: Add a Google-style docstring to `FirestoreLoader.authenticate`.; 272: Add a Google-style docstring to `FirestoreLoader.load_document`. (17 missing docstring(s)).
- `src/agentic_brain/utils/clock.py` — 129: Add a Google-style docstring to `AgentClock.set_local_timezone`.; 132: Add a Google-style docstring to `AgentClock.now`.; 135: Add a Google-style docstring to `AgentClock.now_dt`.; 138: Add a Google-style docstring to `AgentClock.local_now`.; 141: Add a Google-style docstring to `AgentClock.stamp`. (17 missing docstring(s)).
- `src/agentic_brain/core/redis_pool.py` — 41: Add a Google-style docstring to class `RedisConfig`.; 50: Add a Google-style docstring to `RedisConfig.from_env`.; 121: Add a Google-style docstring to `RedisPoolManager.client`.; 142: Add a Google-style docstring to `RedisPoolManager.publish`.; 146: Add a Google-style docstring to `RedisPoolManager.pubsub`. (15 missing docstring(s)).
- `src/agentic_brain/voice/serializer.py` — 311: Add a Google-style docstring to `VoiceSerializer.pause_between`.; 315: Add a Google-style docstring to `VoiceSerializer.startup_silence_seconds`.; 324: Add a Google-style docstring to `VoiceSerializer.current_message`.; 329: Add a Google-style docstring to `VoiceSerializer.current_process`.; 337: Add a Google-style docstring to `VoiceSerializer.is_speaking`. (15 missing docstring(s)).
- `src/agentic_brain/commerce/woocommerce/agent.py` — 292: Add a Google-style docstring to `WooCommerceAgent.get_products_sync`.; 297: Add a Google-style docstring to `WooCommerceAgent.get_product_sync`.; 300: Add a Google-style docstring to `WooCommerceAgent.create_product_sync`.; 303: Add a Google-style docstring to `WooCommerceAgent.update_product_sync`.; 308: Add a Google-style docstring to `WooCommerceAgent.delete_product_sync`. (14 missing docstring(s)).
- `src/agentic_brain/events/voice_events.py` — 114: Add a Google-style docstring to `VoiceRequest.to_payload`.; 120: Add a Google-style docstring to `VoiceRequest.from_payload`.; 154: Add a Google-style docstring to `VoiceStatus.to_payload`.; 158: Add a Google-style docstring to `VoiceStatus.from_payload`.; 199: Add a Google-style docstring to `VoiceEventProducer.enabled`. (14 missing docstring(s)).
- `src/agentic_brain/rag/embeddings.py` — 303: Add a Google-style docstring to `OllamaEmbeddings.dimensions`.; 307: Add a Google-style docstring to `OllamaEmbeddings.model_name`.; 363: Add a Google-style docstring to `OpenAIEmbeddings.dimensions`.; 367: Add a Google-style docstring to `OpenAIEmbeddings.model_name`.; 562: Add a Google-style docstring to `SentenceTransformerEmbeddings.dimensions`. (14 missing docstring(s)).
- `src/agentic_brain/rag/store.py` — 45: Add a Google-style docstring to `Document.to_dict`.; 56: Add a Google-style docstring to `Document.from_dict`.; 168: Add a Google-style docstring to `InMemoryDocumentStore.get`.; 171: Add a Google-style docstring to `InMemoryDocumentStore.delete`.; 178: Add a Google-style docstring to `InMemoryDocumentStore.list`. (14 missing docstring(s)).

## 6. Configuration

- No high-confidence hardcoded secrets were detected in `src/agentic_brain`, `apps/BrainChat`, or the SDK source trees.
- Environment-based configuration appears to be the standard pattern (`os.getenv`, `process.env`, and injected config objects show up consistently).
- The raw string scan produced low-signal matches around placeholder/example values, so those were intentionally excluded from the final inconsistency list.

## 7. Async/Await

- `apps/BrainChat/LayeredResponseManager.swift:261` — Avoid `try? await Task.sleep(...)` when cancellation should propagate; handle `CancellationError` explicitly.
- `apps/BrainChat/ResponseWeavingCoordinator.swift:121` — Avoid `try? await Task.sleep(...)` when cancellation should propagate; handle `CancellationError` explicitly.
- `src/agentic_brain/infra/health_monitor.py:417, 419` — `_restart_native_service()` does blocking `subprocess.run(...)` / `subprocess.Popen(...)` inside async code; move this work to an executor or asyncio subprocess API.
- `src/agentic_brain/mcp/client.py:141, 160` — `connect()`/`disconnect()` use blocking `subprocess.Popen(...)` and `wait(...)` inside async methods; switch to asyncio subprocess primitives or an executor-backed transport.

## Recommended Fix Order

1. Fix the small number of naming issues first (`iCloudLoader`, uppercase `Voice` factory methods).
2. Standardize async subprocess handling in `health_monitor.py` and `mcp/client.py` before adding more async features.
3. Tackle broad `except Exception` hotspots in `secrets/`, `rag/loaders/`, `voice/`, and `transport/` modules.
4. Sweep import ordering with an auto-formatter/isort-equivalent policy for Python and a simple alphabetical import rule for Swift.
5. Add Google-style docstrings and missing type hints to hotspot files first (`commerce/`, `benchmark/`, `audio/`, `cli/`, `api/`).
