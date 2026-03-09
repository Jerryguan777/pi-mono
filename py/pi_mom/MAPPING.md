# pi_mom Mapping

## agent.ts

| TS Function/Class | Python Equivalent | Status | Notes |
|-------------------|-------------------|--------|-------|
| PendingMessage | PendingMessage | Done | |
| AgentRunner | AgentRunner | Done | |
| getOrCreateRunner | get_or_create_runner | Done | |

## context.ts

| TS Function/Class | Python Equivalent | Status | Notes |
|-------------------|-------------------|--------|-------|
| syncLogToSessionManager | sync_log_to_session_manager | Done | |
| syncLogToSessionManager | sync_log_to_context | Done | Alias for backward compat |
| MomCompactionSettings | MomCompactionSettings | Done | |
| MomRetrySettings | MomRetrySettings | Done | |
| MomSettings | MomSettings | Done | |
| MomSettingsManager | MomSettingsManager | Done | |

## download.ts

| TS Function/Class | Python Equivalent | Status | Notes |
|-------------------|-------------------|--------|-------|
| downloadChannel | download_channel | Done | |

## events.ts

| TS Function/Class | Python Equivalent | Status | Notes |
|-------------------|-------------------|--------|-------|
| ImmediateEvent | ImmediateEvent | Done | |
| OneShotEvent | OneShotEvent | Done | |
| PeriodicEvent | PeriodicEvent | Done | |
| MomEvent | MomEvent | Done | Union type |
| EventsWatcher | EventsWatcher | Done | |
| createEventsWatcher | create_events_watcher | Done | |

## log.ts

| TS Function/Class | Python Equivalent | Status | Notes |
|-------------------|-------------------|--------|-------|
| LogContext | LogContext | Done | |
| logUserMessage | log_user_message | Done | |
| logToolStart | log_tool_start | Done | |
| logToolSuccess | log_tool_success | Done | |
| logToolError | log_tool_error | Done | |
| logResponseStart | log_response_start | Done | |
| logThinking | log_thinking | Done | |
| logResponse | log_response | Done | |
| logDownloadStart | log_download_start | Done | |
| logDownloadSuccess | log_download_success | Done | |
| logDownloadError | log_download_error | Done | |
| logStopRequest | log_stop_request | Done | |
| logInfo | log_info | Done | |
| logWarning | log_warning | Done | |
| logAgentError | log_agent_error | Done | |
| logUsageSummary | log_usage_summary | Done | |
| logStartup | log_startup | Done | |
| logConnected | log_connected | Done | |
| logDisconnected | log_disconnected | Done | |
| logBackfillStart | log_backfill_start | Done | |
| logBackfillChannel | log_backfill_channel | Done | |
| logBackfillComplete | log_backfill_complete | Done | |

## sandbox.ts

| TS Function/Class | Python Equivalent | Status | Notes |
|-------------------|-------------------|--------|-------|
| SandboxConfig | SandboxConfig | Done | Union type in TS; Python type alias for HostSandboxConfig \| DockerSandboxConfig |
| SandboxConfig (host) | HostSandboxConfig | Done | Python uses separate dataclass |
| SandboxConfig (docker) | DockerSandboxConfig | Done | Python uses separate dataclass |
| parseSandboxArg | parse_sandbox_arg | Done | |
| validateSandbox | validate_sandbox | Done | |
| createExecutor | create_executor | Done | |
| Executor | Executor | Done | Interface in TS; Protocol/ABC in Python |
| ExecOptions | ExecOptions | Done | |
| ExecResult | ExecResult | Done | |
| HostExecutor | HostExecutor | Done | Private class in TS; exported in Python |

## slack.ts

| TS Function/Class | Python Equivalent | Status | Notes |
|-------------------|-------------------|--------|-------|
| SlackEvent | SlackEvent | Done | |
| SlackUser | SlackUser | Done | |
| SlackChannel | SlackChannel | Done | |
| ChannelInfo | ChannelInfo | Done | |
| UserInfo | UserInfo | Done | |
| SlackContext | SlackContext | Done | |
| MomHandler | MomHandler | Done | |
| ChannelQueue | ChannelQueue | Done | Private class in TS; exported in Python |
| SlackBot | SlackBot | Done | |

## store.ts

| TS Function/Class | Python Equivalent | Status | Notes |
|-------------------|-------------------|--------|-------|
| Attachment | Attachment | Done | |
| LoggedMessage | LoggedMessage | Done | |
| ChannelStoreConfig | ChannelStoreConfig | Done | |
| ChannelStore | ChannelStore | Done | |

## tools/index.ts

| TS Function/Class | Python Equivalent | Status | Notes |
|-------------------|-------------------|--------|-------|
| setUploadFunction | set_upload_function | Done | Re-exported from attach |
| createMomTools | create_mom_tools | Done | |

## tools/attach.ts

| TS Function/Class | Python Equivalent | Status | Notes |
|-------------------|-------------------|--------|-------|
| setUploadFunction | set_upload_function | Done | |
| attachTool | attach_tool | Done | Constant in TS; factory function in Python |
| (attachTool type) | AttachTool | Done | Class in Python |

## tools/bash.ts

| TS Function/Class | Python Equivalent | Status | Notes |
|-------------------|-------------------|--------|-------|
| createBashTool | create_bash_tool | Done | |
| (bash tool type) | BashTool | Done | Class in Python |

## tools/edit.ts

| TS Function/Class | Python Equivalent | Status | Notes |
|-------------------|-------------------|--------|-------|
| createEditTool | create_edit_tool | Done | |
| (edit tool type) | EditTool | Done | Class in Python |

## tools/read.ts

| TS Function/Class | Python Equivalent | Status | Notes |
|-------------------|-------------------|--------|-------|
| createReadTool | create_read_tool | Done | |
| (read tool type) | ReadTool | Done | Class in Python |

## tools/write.ts

| TS Function/Class | Python Equivalent | Status | Notes |
|-------------------|-------------------|--------|-------|
| createWriteTool | create_write_tool | Done | |
| (write tool type) | WriteTool | Done | Class in Python |

## tools/truncate.ts

| TS Function/Class | Python Equivalent | Status | Notes |
|-------------------|-------------------|--------|-------|
| DEFAULT_MAX_LINES | DEFAULT_MAX_LINES | Done | |
| DEFAULT_MAX_BYTES | DEFAULT_MAX_BYTES | Done | |
| TruncationResult | TruncationResult | Done | |
| TruncationOptions | TruncationOptions | Done | |
| formatSize | format_size | Done | |
| truncateHead | truncate_head | Done | |
| truncateTail | truncate_tail | Done | |
