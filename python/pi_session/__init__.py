"""pi_session — Session persistence, compaction, and agent orchestration."""

from pi_session.agent_session import (
    AgentSession,
    AgentSessionConfig,
    AutoCompactionEndEvent,
    AutoCompactionStartEvent,
    AutoRetryEndEvent,
    AutoRetryStartEvent,
    RetrySettings,
    SessionEvent,
    SessionStats,
)
from pi_session.compaction import (
    CompactionPreparation,
    CompactionResult,
    CompactionSettings,
    CutPointResult,
    calculate_context_tokens,
    compact,
    estimate_tokens,
    find_cut_point,
    prepare_compaction,
    should_compact,
)
from pi_session.session_manager import SessionManager
from pi_session.types import (
    BranchSummaryEntry,
    CompactionEntry,
    ModelChangeEntry,
    SessionContext,
    SessionEntry,
    SessionHeader,
    SessionMessageEntry,
    SessionTreeNode,
    ThinkingLevelChangeEntry,
    deserialize_entry,
    deserialize_message,
    serialize_entry,
    serialize_message,
)
