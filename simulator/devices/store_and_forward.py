import uuid
import json
from enum import Enum
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional

class MessageState(Enum):
    GENERATED = "GENERATED"
    QUEUED = "QUEUED"
    SENDING = "SENDING"
    DELIVERED = "DELIVERED"
    FAILED = "FAILED"
    RETRY_SCHEDULED = "RETRY_SCHEDULED"
    ARCHIVED = "ARCHIVED"

class OverflowPolicy(Enum):
    DROP_OLDEST = "DROP_OLDEST"
    DROP_NEWEST = "DROP_NEWEST"
    STOP_SIMULATION = "STOP_SIMULATION"

@dataclass
class BufferedRecord:
    record_id: str
    sequence_number: int
    payload: Dict[str, Any]
    state: MessageState = MessageState.GENERATED
    created_at_sim_time: int = 0

@dataclass
class BufferMetrics:
    queue_size: int = 0
    oldest_record_age_seconds: int = 0
    replay_count: int = 0
    dropped_records: int = 0
    replay_duration_seconds: int = 0

class BatchBuilder:
    """Responsible for constructing batches within size limits."""
    def __init__(self, max_batch_size: int = 100, max_request_size_bytes: int = 1024 * 1024):
        self.max_batch_size = max_batch_size
        self.max_request_size_bytes = max_request_size_bytes

    def build_batch(self, records: List[BufferedRecord]) -> List[BufferedRecord]:
        batch = []
        current_size = 0
        
        for record in records:
            if len(batch) >= self.max_batch_size:
                break
                
            # Naive size estimation via JSON serialization
            serialized = json.dumps(record.payload)
            record_size = len(serialized.encode("utf-8"))
            
            if current_size + record_size > self.max_request_size_bytes and len(batch) > 0:
                break
                
            batch.append(record)
            current_size += record_size
            
        return batch

class StoreAndForwardEngine:
    """
    In-memory store-and-forward engine for telemetry payloads.
    Provides an abstraction layer for future persistence mechanisms.
    """
    def __init__(self, max_capacity: int = 10000, overflow_policy: OverflowPolicy = OverflowPolicy.DROP_OLDEST):
        self._queue: List[BufferedRecord] = []
        self.metrics = BufferMetrics()
        self.max_capacity = max_capacity
        self.overflow_policy = overflow_policy
        self._batch_builder = BatchBuilder()

    def enqueue(self, sequence_number: int, payload: Dict[str, Any], sim_time: int) -> BufferedRecord:
        if len(self._queue) >= self.max_capacity:
            if self.overflow_policy == OverflowPolicy.DROP_OLDEST:
                self._queue.pop(0)
                self.metrics.dropped_records += 1
            elif self.overflow_policy == OverflowPolicy.DROP_NEWEST:
                self.metrics.dropped_records += 1
                # Return a dummy failed record
                return BufferedRecord(str(uuid.uuid4()), sequence_number, payload, MessageState.FAILED, sim_time)
            elif self.overflow_policy == OverflowPolicy.STOP_SIMULATION:
                raise RuntimeError("Buffer capacity exceeded and overflow policy is STOP_SIMULATION")

        record = BufferedRecord(
            record_id=str(uuid.uuid4()),
            sequence_number=sequence_number,
            payload=payload,
            state=MessageState.QUEUED,
            created_at_sim_time=sim_time
        )
        self._queue.append(record)
        self.metrics.queue_size = len(self._queue)
        return record

    def build_next_batch(self) -> List[BufferedRecord]:
        """Returns the next batch of records to send."""
        queued_records = [r for r in self._queue if r.state in (MessageState.QUEUED, MessageState.RETRY_SCHEDULED)]
        
        # We sort by sequence number to ensure ordering is maintained
        queued_records.sort(key=lambda x: x.sequence_number)
        
        batch = self._batch_builder.build_batch(queued_records)
        for record in batch:
            record.state = MessageState.SENDING
            
        return batch

    def acknowledge_batch(self, record_ids: List[str], success: bool):
        """Acknowledge delivery success or failure."""
        if success:
            # Remove from queue, conceptually moving to ARCHIVED
            self._queue = [r for r in self._queue if r.record_id not in record_ids]
            self.metrics.replay_count += 1
        else:
            # Mark for retry
            for record in self._queue:
                if record.record_id in record_ids:
                    record.state = MessageState.RETRY_SCHEDULED
                    
        self.metrics.queue_size = len(self._queue)

    def update_metrics(self, current_sim_time: int):
        self.metrics.queue_size = len(self._queue)
        if self._queue:
            oldest = min((r.created_at_sim_time for r in self._queue), default=current_sim_time)
            self.metrics.oldest_record_age_seconds = current_sim_time - oldest
        else:
            self.metrics.oldest_record_age_seconds = 0

    def save_state(self):
        """Prepare for future persistence."""
        pass
        
    def restore_state(self):
        """Prepare for future persistence."""
        pass
        
    def statistics(self) -> BufferMetrics:
        return self.metrics

    def peek(self) -> Optional[BufferedRecord]:
        return self._queue[0] if self._queue else None
        
    def oldest(self) -> Optional[BufferedRecord]:
        if not self._queue:
            return None
        return min(self._queue, key=lambda x: x.sequence_number)

    def newest(self) -> Optional[BufferedRecord]:
        if not self._queue:
            return None
        return max(self._queue, key=lambda x: x.sequence_number)
