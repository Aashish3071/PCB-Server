import pytest
from devices.store_and_forward import StoreAndForwardEngine, OverflowPolicy, MessageState

def test_store_and_forward_enqueue():
    engine = StoreAndForwardEngine()
    
    record1 = engine.enqueue(1, {"temp": 25.0}, sim_time=100)
    record2 = engine.enqueue(2, {"temp": 26.0}, sim_time=200)
    
    assert record1.state == MessageState.QUEUED
    assert engine.metrics.queue_size == 2
    
    stats = engine.statistics()
    assert stats.queue_size == 2

def test_batch_builder_limits():
    # Batch limit 2, size limit very high
    engine = StoreAndForwardEngine()
    engine._batch_builder.max_batch_size = 2
    
    engine.enqueue(1, {"val": 1}, 100)
    engine.enqueue(2, {"val": 2}, 200)
    engine.enqueue(3, {"val": 3}, 300)
    
    batch = engine.build_next_batch()
    
    assert len(batch) == 2
    assert batch[0].sequence_number == 1
    assert batch[1].sequence_number == 2
    assert batch[0].state == MessageState.SENDING

def test_batch_builder_byte_size_limits():
    # Very small byte size limit
    engine = StoreAndForwardEngine()
    engine._batch_builder.max_request_size_bytes = 20 # Barely fits one payload
    
    engine.enqueue(1, {"v": 1}, 100) # {"v": 1} is ~8 bytes
    engine.enqueue(2, {"v": 2}, 200)
    engine.enqueue(3, {"v": 3}, 300)
    
    # Should only pull records until size limit is hit
    batch = engine.build_next_batch()
    
    assert len(batch) > 0 
    assert len(batch) < 3

def test_overflow_policy_drop_oldest():
    engine = StoreAndForwardEngine(max_capacity=2, overflow_policy=OverflowPolicy.DROP_OLDEST)
    
    engine.enqueue(1, {"v": 1}, 100)
    engine.enqueue(2, {"v": 2}, 200)
    engine.enqueue(3, {"v": 3}, 300) # This should evict 1
    
    assert engine.metrics.queue_size == 2
    assert engine.metrics.dropped_records == 1
    
    batch = engine.build_next_batch()
    assert len(batch) == 2
    assert batch[0].sequence_number == 2
    assert batch[1].sequence_number == 3

def test_acknowledge_success():
    engine = StoreAndForwardEngine()
    
    engine.enqueue(1, {"v": 1}, 100)
    batch = engine.build_next_batch()
    
    ids = [r.record_id for r in batch]
    engine.acknowledge_batch(ids, success=True)
    
    assert engine.metrics.queue_size == 0
    assert engine.metrics.replay_count == 1

def test_acknowledge_failure_retry():
    engine = StoreAndForwardEngine()
    
    engine.enqueue(1, {"v": 1}, 100)
    batch = engine.build_next_batch()
    
    ids = [r.record_id for r in batch]
    engine.acknowledge_batch(ids, success=False)
    
    assert engine.metrics.queue_size == 1
    
    # Peek should show it's scheduled for retry
    record = engine.peek()
    assert record.state == MessageState.RETRY_SCHEDULED
    
    # Should be included in next batch
    batch2 = engine.build_next_batch()
    assert len(batch2) == 1
    assert batch2[0].record_id == ids[0]

def test_metrics_oldest_record_age():
    engine = StoreAndForwardEngine()
    
    engine.enqueue(1, {"v": 1}, 100)
    engine.enqueue(2, {"v": 2}, 200)
    
    engine.update_metrics(current_sim_time=300)
    assert engine.metrics.oldest_record_age_seconds == 200 # 300 - 100
