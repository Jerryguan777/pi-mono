# pi_coding_agent — TypeScript → Python Mapping

| TS Function/Class | Python Equivalent | Status | Notes |
|-------------------|-------------------|--------|-------|
| `RpcCommand` (union type) | `RpcCommand` (union of dataclasses) | Done | Individual dataclass per variant with `Literal` type field |
| `RpcPromptCommand` | `RpcPromptCommand` | Done | |
| `RpcSteerCommand` | `RpcSteerCommand` | Done | |
| `RpcFollowUpCommand` | `RpcFollowUpCommand` | Done | |
| `RpcAbortCommand` | `RpcAbortCommand` | Done | |
| `RpcNewSessionCommand` | `RpcNewSessionCommand` | Done | `parentSession` → `parent_session` |
| `RpcGetStateCommand` | `RpcGetStateCommand` | Done | |
| `RpcSetModelCommand` | `RpcSetModelCommand` | Done | `modelId` → `model_id` |
| `RpcCycleModelCommand` | `RpcCycleModelCommand` | Done | |
| `RpcGetAvailableModelsCommand` | `RpcGetAvailableModelsCommand` | Done | |
| `RpcSetThinkingLevelCommand` | `RpcSetThinkingLevelCommand` | Done | |
| `RpcCycleThinkingLevelCommand` | `RpcCycleThinkingLevelCommand` | Done | |
| `RpcSetSteeringModeCommand` | `RpcSetSteeringModeCommand` | Done | |
| `RpcSetFollowUpModeCommand` | `RpcSetFollowUpModeCommand` | Done | |
| `RpcCompactCommand` | `RpcCompactCommand` | Done | `customInstructions` → `custom_instructions` |
| `RpcSetAutoCompactionCommand` | `RpcSetAutoCompactionCommand` | Done | |
| `RpcSetAutoRetryCommand` | `RpcSetAutoRetryCommand` | Done | |
| `RpcAbortRetryCommand` | `RpcAbortRetryCommand` | Done | |
| `RpcBashCommand` | `RpcBashCommand` | Done | |
| `RpcAbortBashCommand` | `RpcAbortBashCommand` | Done | |
| `RpcGetSessionStatsCommand` | `RpcGetSessionStatsCommand` | Done | |
| `RpcExportHtmlCommand` | `RpcExportHtmlCommand` | Done | `outputPath` → `output_path` |
| `RpcSwitchSessionCommand` | `RpcSwitchSessionCommand` | Done | `sessionPath` → `session_path` |
| `RpcForkCommand` | `RpcForkCommand` | Done | `entryId` → `entry_id` |
| `RpcGetForkMessagesCommand` | `RpcGetForkMessagesCommand` | Done | |
| `RpcGetLastAssistantTextCommand` | `RpcGetLastAssistantTextCommand` | Done | |
| `RpcSetSessionNameCommand` | `RpcSetSessionNameCommand` | Done | |
| `RpcGetMessagesCommand` | `RpcGetMessagesCommand` | Done | |
| `RpcGetCommandsCommand` | `RpcGetCommandsCommand` | Done | |
| `RpcCommandType` | `RpcCommandType` | Done | `Literal` union string |
| `RpcSlashCommand` | `RpcSlashCommand` | Done | `@dataclass` |
| `RpcSessionState` | `RpcSessionState` | Done | `@dataclass`; camelCase → snake_case |
| `RpcResponse` | `RpcResponse` | Done | `@dataclass` |
| `RpcExtensionUIRequest` | `RpcExtensionUIRequest` | Done | `@dataclass` |
| `RpcExtensionUIResponse` | `RpcExtensionUIResponse` | Done | `@dataclass` |
| `deserialize_rpc_command()` | `deserialize_rpc_command()` | Done | |
| `serialize_rpc_session_state()` | `serialize_rpc_session_state()` | Done | |
| `deserialize_rpc_session_state()` | `deserialize_rpc_session_state()` | Done | |
| `serialize_rpc_response()` | `serialize_rpc_response()` | Done | |
| `deserialize_rpc_response()` | `deserialize_rpc_response()` | Done | |
| `serialize_rpc_extension_ui_request()` | `serialize_rpc_extension_ui_request()` | Done | |
| `deserialize_rpc_extension_ui_response()` | `deserialize_rpc_extension_ui_response()` | Done | |
| `RpcClient` class | `RpcClient` class | Done | Uses `asyncio.subprocess`; `asyncio.Future` for pending |
| `RpcClient.start()` | `RpcClient.start()` | Done | |
| `RpcClient.stop()` | `RpcClient.stop()` | Done | |
| `RpcClient.onEvent()` | `RpcClient.on_event()` | Done | Returns unsubscribe callable |
| `RpcClient.getStderr()` | `RpcClient.get_stderr()` | Done | |
| `RpcClient.prompt()` | `RpcClient.prompt()` | Done | |
| `RpcClient.steer()` | `RpcClient.steer()` | Done | |
| `RpcClient.followUp()` | `RpcClient.follow_up()` | Done | |
| `RpcClient.abort()` | `RpcClient.abort()` | Done | |
| `RpcClient.newSession()` | `RpcClient.new_session()` | Done | |
| `RpcClient.getState()` | `RpcClient.get_state()` | Done | |
| `RpcClient.setModel()` | `RpcClient.set_model()` | Done | |
| `RpcClient.cycleModel()` | `RpcClient.cycle_model()` | Done | |
| `RpcClient.getAvailableModels()` | `RpcClient.get_available_models()` | Done | |
| `RpcClient.setThinkingLevel()` | `RpcClient.set_thinking_level()` | Done | |
| `RpcClient.cycleThinkingLevel()` | `RpcClient.cycle_thinking_level()` | Done | |
| `RpcClient.setSteeringMode()` | `RpcClient.set_steering_mode()` | Done | |
| `RpcClient.setFollowUpMode()` | `RpcClient.set_follow_up_mode()` | Done | |
| `RpcClient.compact()` | `RpcClient.compact()` | Done | |
| `RpcClient.setAutoCompaction()` | `RpcClient.set_auto_compaction()` | Done | |
| `RpcClient.setAutoRetry()` | `RpcClient.set_auto_retry()` | Done | |
| `RpcClient.abortRetry()` | `RpcClient.abort_retry()` | Done | |
| `RpcClient.bash()` | `RpcClient.bash()` | Done | |
| `RpcClient.abortBash()` | `RpcClient.abort_bash()` | Done | |
| `RpcClient.getSessionStats()` | `RpcClient.get_session_stats()` | Done | |
| `RpcClient.exportHtml()` | `RpcClient.export_html()` | Done | |
| `RpcClient.switchSession()` | `RpcClient.switch_session()` | Done | |
| `RpcClient.fork()` | `RpcClient.fork()` | Done | |
| `RpcClient.getForkMessages()` | `RpcClient.get_fork_messages()` | Done | |
| `RpcClient.getLastAssistantText()` | `RpcClient.get_last_assistant_text()` | Done | |
| `RpcClient.setSessionName()` | `RpcClient.set_session_name()` | Done | |
| `RpcClient.getMessages()` | `RpcClient.get_messages()` | Done | |
| `RpcClient.getCommands()` | `RpcClient.get_commands()` | Done | |
| `RpcClient.waitForIdle()` | `RpcClient.wait_for_idle()` | Done | `timeout` in seconds (TS: ms) |
| `RpcClient.collectEvents()` | `RpcClient.collect_events()` | Done | |
| `RpcClient.promptAndWait()` | `RpcClient.prompt_and_wait()` | Done | |
| `runRpcMode()` | `run_rpc_mode()` | Done | Uses `AgentSessionProtocol` (stub Protocol) |
| `getShellConfig()` | `get_shell_config()` | Done | Returns `dict` with `shell` and `args` |
| `getShellEnv()` | `get_shell_env()` | Done | Prepends pi bin dir to PATH |
| `sanitizeBinaryOutput()` | `sanitize_binary_output()` | Done | Regex-based Unicode stripping |
| `killProcessTree()` | `kill_process_tree()` | Done | POSIX `killpg`; fallback to `ps` + recursive |
| `GitSource` interface | `GitSource` dataclass | Done | |
| `parseGitUrl()` | `parse_git_url()` | Done | Pure Python, no external deps |
| `copyToClipboard()` | `copy_to_clipboard()` | Done | OSC 52 + wl-copy / xclip / pbcopy |
| `ClipboardImage` interface | `ClipboardImage` dataclass | Done | |
| `isWaylandSession()` | `is_wayland_session()` | Done | |
| `extensionForImageMimeType()` | `extension_for_image_mime_type()` | Done | |
| `readClipboardImage()` | `read_clipboard_image()` | Done | Linux/macOS only |
| `convertToPng()` | `convert_to_png()` | Done | Uses Pillow |
| `ImageResizeOptions` interface | `ImageResizeOptions` dataclass | Done | |
| `ResizedImage` interface | `ResizedImage` dataclass | Done | |
| `resizeImage()` | `resize_image()` | Done | Uses Pillow |
| `formatDimensionNote()` | `format_dimension_note()` | Done | |
| `getToolPath()` | `get_tool_path()` | Done | |
| `ensureTool()` | `ensure_tool()` | Done | `async`; uses `httpx` |
| `ToolHtmlRenderer` interface | `ToolHtmlRenderer` Protocol | Done | `@runtime_checkable` |
| `ExportOptions` interface | `ExportOptions` dataclass | Done | |
| `exportSessionToHtml()` | `export_session_to_html()` | Done | Uses `SessionManagerProtocol` stub |
| `exportFromFile()` | `export_from_file()` | Done | |
